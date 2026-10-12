"""Opt-in per-tenant service binding on the mounted application."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.context import require_tenant
from app.modules.m20_general_cognitive_worker import spec as gcw_spec
from app.modules.m20_general_cognitive_worker import routes
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService

# Same mount as app.main uses for each implemented module spec (the full registry
# needs optional packages absent from the minimal test interpreter).
app = FastAPI()
app.include_router(gcw_spec.router, prefix="/api/v1", dependencies=[Depends(require_tenant)])

URL = "/api/v1/api/modules/20/meta/meta-learning/transfer"
BODY = {"goal": "draft an outreach email", "episodes": []}
BOUND = "GCW service not bound for authenticated tenant"


@pytest.fixture()
def prod(monkeypatch, oidc_auth_headers):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    monkeypatch.setenv("ATLAS_ENV", "production")
    monkeypatch.delenv("ATLAS_GCW_AUTOBIND", raising=False)
    monkeypatch.setattr(routes, "_services", {})
    monkeypatch.setattr(routes, "_service", None)
    return TestClient(app), oidc_auth_headers


def post(c, headers=None):
    return c.post(URL, json=BODY, headers=headers or {})


def test_default_unbound_tenant_still_503(prod):
    c, h = prod
    r = post(c, h("tenant-a"))
    assert r.status_code == 503 and r.json()["detail"] == BOUND
    assert routes._services == {}


def test_unauthenticated_stays_401_even_when_opted_in(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    assert post(c).status_code == 401
    assert routes._services == {}


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "1 ", "01", "on"])
def test_only_exact_one_opts_in(prod, monkeypatch, value):
    c, h = prod
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", value)
    assert post(c, h("tenant-a")).status_code == 503
    assert routes._services == {}


def test_opted_in_authenticated_tenant_gets_live_response(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    r = post(c, h("tenant-a"))
    assert r.status_code == 200, r.text
    assert set(r.json()) >= {"transfers"}
    assert set(routes._services) == {"tenant-a"}
    assert type(routes._services["tenant-a"]) is CognitiveWorkerService


def test_tenants_get_distinct_services_and_same_tenant_reuses(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    for t in ("tenant-a", "tenant-b", "tenant-a"):
        assert post(c, h(t)).status_code < 500
    a, b = routes._services["tenant-a"], routes._services["tenant-b"]
    assert a is not b
    assert a.episodic is not b.episodic and a.tools is not b.tools
    assert set(routes._services) == {"tenant-a", "tenant-b"}


def test_explicit_binding_wins_over_autobind(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    mine = CognitiveWorkerService()
    routes.bind_service(mine, tenant_id="tenant-a")
    assert post(c, h("tenant-a")).status_code < 500
    assert routes._services["tenant-a"] is mine


def test_local_tenant_stays_403_without_dev_auth(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    r = post(c, h("local"))
    assert r.status_code == 403
    assert routes._services == {} and routes._service is None


def test_local_never_autobound_even_with_dev_auth(monkeypatch):
    from fastapi import HTTPException
    from app.auth.context import TenantContext
    monkeypatch.setenv("ATLAS_DEV_NO_AUTH", "1")
    monkeypatch.setenv("ATLAS_ENV", "development")
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    monkeypatch.setattr(routes, "_services", {})
    monkeypatch.setattr(routes, "_service", None)
    with pytest.raises(HTTPException) as e:
        routes.get_service(TenantContext("local", "dev"))
    assert e.value.status_code == 503 and routes._services == {}


def test_tenant_count_is_capped(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    monkeypatch.setattr(routes, "AUTOBIND_MAX_TENANTS", 2)
    assert post(c, h("t1")).status_code < 500
    assert post(c, h("t2")).status_code < 500
    r = post(c, h("t3"))
    assert r.status_code == 503 and r.json()["detail"] == BOUND
    assert set(routes._services) == {"t1", "t2"}
    assert post(c, h("t1")).status_code < 500


def test_overlong_tenant_id_not_bound(prod, monkeypatch):
    c, h = prod
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    r = post(c, h("x" * 129))
    assert r.status_code == 503 and routes._services == {}
    assert post(c, h("x" * 128)).status_code < 500


def test_autobind_refuses_non_str_empty_and_local_ids(monkeypatch):
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    monkeypatch.setattr(routes, "_services", {})
    class S(str):
        pass
    for bad in (None, 1, b"t", ["t"], "", "local", S("t")):
        assert routes._autobind(bad) is None
    assert routes._services == {}
    assert routes._autobind("ok") is routes._services["ok"]


def test_explicit_bind_during_autobind_construction_wins(monkeypatch):
    import threading
    from app.modules.m20_general_cognitive_worker import service as svc_mod
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    monkeypatch.setattr(routes, "_services", {})
    monkeypatch.setattr(routes, "_service", None)
    explicit = CognitiveWorkerService()
    threads = []
    real = svc_mod.CognitiveWorkerService

    class Hooked(real):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            t = threading.Thread(target=routes.bind_service, args=(explicit,), kwargs={"tenant_id": "tenant-a"})
            t.start()
            t.join(0.3)
            threads.append(t)

    monkeypatch.setattr(svc_mod, "CognitiveWorkerService", Hooked)
    routes._autobind("tenant-a")
    threads[0].join(5)
    assert not threads[0].is_alive()
    assert routes._services["tenant-a"] is explicit
    assert routes._autobind("tenant-a") is explicit


def test_explicit_bind_after_autobind_replaces_it(monkeypatch):
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    monkeypatch.setattr(routes, "_services", {})
    auto = routes._autobind("tenant-a")
    mine = CognitiveWorkerService()
    routes.bind_service(mine, tenant_id="tenant-a")
    assert routes._services["tenant-a"] is mine and mine is not auto
    assert routes._autobind("tenant-a") is mine


def test_doc_scope_wording_matches_tested_behaviour():
    from pathlib import Path
    doc = (Path(routes.__file__).parent / "INTEGRATION.md").read_text()
    sec = doc.split("## Opt-in per-tenant service binding", 1)[1].split("\n## ", 1)[0]
    assert "only verified authenticated tenants" not in sec.lower()
    assert "insecure development auth" in sec and "header-selected" in sec
    assert "explicit `bind_service()`" in sec


def test_same_thread_explicit_bind_inside_constructor_wins(monkeypatch):
    from app.modules.m20_general_cognitive_worker import service as svc_mod
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    monkeypatch.setattr(routes, "_services", {})
    monkeypatch.setattr(routes, "_service", None)
    explicit = CognitiveWorkerService()
    real = svc_mod.CognitiveWorkerService

    class Hooked(real):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            routes.bind_service(explicit, tenant_id="tenant-a")

    monkeypatch.setattr(svc_mod, "CognitiveWorkerService", Hooked)
    assert routes._autobind("tenant-a") is explicit
    assert routes._services["tenant-a"] is explicit
