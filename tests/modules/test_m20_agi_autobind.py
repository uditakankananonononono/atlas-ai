"""Opt-in per-tenant AGI runtime binding on the mounted application."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.context import require_tenant
from app.modules.m20_general_cognitive_worker import agi_routes
from app.modules.m20_general_cognitive_worker.agi_service import AGIRuntimeService

# Isolated authenticated router harness; full registry coverage is separate.
app = FastAPI()
app.include_router(agi_routes.router, prefix="/api/v1", dependencies=[Depends(require_tenant)])

URL = "/api/v1/agi-runtime/world/snapshots"
BOUND = "AGI runtime service not bound for authenticated tenant"


@pytest.fixture()
def prod(monkeypatch, oidc_auth_headers, tmp_path):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    monkeypatch.setenv("ATLAS_ENV", "production")
    monkeypatch.delenv("ATLAS_AGI_RUNTIME_AUTOBIND", raising=False)
    monkeypatch.setenv("ATLAS_AGI_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(agi_routes, "_services", {})
    return TestClient(app), oidc_auth_headers


def post(c, headers=None):
    return c.post(URL, headers=headers or {})


def test_default_unbound_tenant_still_503(prod):
    c, h = prod
    r = post(c, h("tenant-a"))
    assert r.status_code == 503 and r.json()["detail"] == BOUND
    assert agi_routes._services == {}


def test_unauthenticated_stays_401_even_when_opted_in(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    assert post(c).status_code == 401
    assert agi_routes._services == {}


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "1 ", "01", "on"])
def test_only_exact_one_opts_in(prod, monkeypatch, value):
    c, h = prod
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", value)
    assert post(c, h("tenant-a")).status_code == 503
    assert agi_routes._services == {}


def test_opted_in_authenticated_tenant_is_bound(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    r = post(c, h("tenant-a"))
    assert r.status_code == 201, r.text
    assert set(agi_routes._services) == {"tenant-a"}
    assert type(agi_routes._services["tenant-a"]) is AGIRuntimeService


def test_tenants_get_distinct_services_and_same_tenant_reuses(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    for t in ("tenant-a", "tenant-b", "tenant-a"):
        assert post(c, h(t)).status_code < 500
    a, b = agi_routes._services["tenant-a"], agi_routes._services["tenant-b"]
    assert a is not b and a.world is not b.world
    assert set(agi_routes._services) == {"tenant-a", "tenant-b"}


def test_explicit_binding_wins_over_autobind(prod, monkeypatch, tmp_path):
    c, h = prod
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    mine = AGIRuntimeService("tenant-a", data_dir=str(tmp_path / "explicit"))
    agi_routes.bind_agi_service(mine, tenant_id="tenant-a")
    assert post(c, h("tenant-a")).status_code == 201
    assert agi_routes._services["tenant-a"] is mine


def test_tenant_count_is_capped(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    monkeypatch.setattr(agi_routes, "AGI_AUTOBIND_MAX_TENANTS", 2)
    assert post(c, h("t1")).status_code < 500
    assert post(c, h("t2")).status_code < 500
    r = post(c, h("t3"))
    assert r.status_code == 503 and r.json()["detail"] == BOUND
    assert set(agi_routes._services) == {"t1", "t2"}
    assert post(c, h("t1")).status_code < 500


def test_overlong_tenant_id_not_bound(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    r = post(c, h("x" * 129))
    assert r.status_code == 503 and agi_routes._services == {}
    assert post(c, h("x" * 128)).status_code < 500


def test_autobind_refuses_non_str_empty_and_local_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    monkeypatch.setenv("ATLAS_AGI_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(agi_routes, "_services", {})
    class S(str):
        pass
    for bad in (None, 1, b"t", ["t"], "", "local", S("t")):
        assert agi_routes._autobind_agi(bad) is None
    assert agi_routes._services == {}
    assert agi_routes._autobind_agi("ok") is agi_routes._services["ok"]


def test_explicit_bind_after_autobind_replaces_it(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    monkeypatch.setenv("ATLAS_AGI_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(agi_routes, "_services", {})
    auto = agi_routes._autobind_agi("tenant-a")
    mine = AGIRuntimeService("tenant-a", data_dir=str(tmp_path / "explicit"))
    agi_routes.bind_agi_service(mine, tenant_id="tenant-a")
    assert agi_routes._services["tenant-a"] is mine and mine is not auto
    assert agi_routes._autobind_agi("tenant-a") is mine

def test_cap_holds_under_concurrent_autobind(monkeypatch, tmp_path):
    # Pins the RLock: without it the len check and the insert race, and
    # concurrent first-touches of distinct tenants exceed the cap.
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    monkeypatch.setenv("ATLAS_AGI_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(agi_routes, "_services", {})
    monkeypatch.setattr(agi_routes, "AGI_AUTOBIND_MAX_TENANTS", 4)
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(agi_routes._autobind_agi, ["t%d" % i for i in range(16)]))
    assert len(agi_routes._services) <= 4
    assert len([r for r in results if r is not None]) <= 4


def test_same_thread_explicit_bind_inside_constructor_wins(monkeypatch, tmp_path):
    # The re-entrant branch in _autobind_agi: a same-thread explicit bind
    # landing inside construction is never overwritten by the automatic bind.
    from app.modules.m20_general_cognitive_worker import agi_service as svc_mod
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    monkeypatch.setattr(agi_routes, "_services", {})
    explicit = AGIRuntimeService("tenant-a", data_dir=str(tmp_path / "explicit"))
    real = svc_mod.AGIRuntimeService

    class Hooked(real):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            agi_routes.bind_agi_service(explicit, tenant_id="tenant-a")

    monkeypatch.setattr(agi_routes, "AGIRuntimeService", Hooked)
    monkeypatch.setenv("ATLAS_AGI_DATA_DIR", str(tmp_path / "auto"))
    assert agi_routes._autobind_agi("tenant-a") is explicit
    assert agi_routes._services["tenant-a"] is explicit

def test_one_construction_per_tenant_under_concurrent_autobind(monkeypatch, tmp_path):
    # Pins the double-build avoidance the RLock provides: concurrent first-touches
    # of one tenant construct exactly one service. Without the lock every thread
    # builds its own (count equals the thread count).
    import threading
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setenv("ATLAS_AGI_RUNTIME_AUTOBIND", "1")
    monkeypatch.setenv("ATLAS_AGI_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(agi_routes, "_services", {})
    count = {"n": 0}
    counter_lock = threading.Lock()
    real = AGIRuntimeService

    class Counting(real):
        def __init__(self, *a, **k):
            with counter_lock:
                count["n"] += 1
            super().__init__(*a, **k)

    monkeypatch.setattr(agi_routes, "AGIRuntimeService", Counting)
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: agi_routes._autobind_agi("tenant-a"), range(16)))
    assert count["n"] == 1
    assert len(set(map(id, results))) == 1
    assert results[0] is agi_routes._services["tenant-a"]


def test_production_cap_is_64():
    assert agi_routes.AGI_AUTOBIND_MAX_TENANTS == 64


def test_bind_agi_service_tenant_id_is_keyword_only():
    with pytest.raises(TypeError):
        agi_routes.bind_agi_service(AGIRuntimeService.__new__(AGIRuntimeService), "tenant-a")
