"""Phase 2 slice 1: legacy /claire/goals routes through the mounted app with real signed identities.

Limits: SQLite only; realize() owner path not exercised here (needs a configured model); the
legacy Service keeps its goals in process memory (now per tenant, owner-checked), it is not durable.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.modules.m00_approval_center import service as m00_service

from app.main import app
from app.modules.m20_general_cognitive_worker import routes as m20
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
from app.modules.m21_claire import routes as claire_routes

BASE = "/api/v1/claire/goals"


@pytest.fixture(autouse=True)
def isolated_approval_center(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/approvals.db", connect_args={"check_same_thread": False})
    m00_service.Base.metadata.create_all(engine)
    monkeypatch.setattr(m00_service, "_default_service", m00_service.Service(session_factory=sessionmaker(bind=engine, expire_on_commit=False)))
    yield
    engine.dispose()


@pytest.fixture
def two_tenants(monkeypatch):
    monkeypatch.setenv("ATLAS_ENV", "production")
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    monkeypatch.setattr(m20, "_services", {})
    monkeypatch.setattr(m20, "_service", None)
    monkeypatch.setattr(claire_routes, "_services", {}, raising=False)
    m20.bind_service(CognitiveWorkerService(), tenant_id="tenant-a")
    m20.bind_service(CognitiveWorkerService(), tenant_id="tenant-b")
    return TestClient(app)


def test_mounted_intake_works_and_is_authenticated(two_tenants, oidc_auth_headers):
    c = two_tenants
    assert c.post(BASE, json={"goal": "plan my trip", "acceptance": ["x"]}).status_code == 401
    r = c.post(BASE, json={"goal": "plan my trip", "acceptance": ["x"]}, headers=oidc_auth_headers("tenant-a", "alice"))
    assert r.status_code == 201
    assert set(r.json()) >= {"goal", "acceptance", "limits", "id", "status", "artifacts", "evidence"}  # shape kept
    assert "tenant_id" not in r.json() and "actor_id" not in r.json()


def test_other_tenant_and_other_actor_cannot_touch_a_goal(two_tenants, oidc_auth_headers):
    c = two_tenants
    gid = c.post(BASE, json={"goal": "plan my trip"}, headers=oidc_auth_headers("tenant-a", "alice")).json()["id"]
    body = {"operation": "read_file", "preview": {}}
    for tenant, actor in (("tenant-b", "alice"), ("tenant-a", "bob")):
        h = oidc_auth_headers(tenant, actor)
        assert c.post(f"{BASE}/{gid}/environment-changes", json=body, headers=h).status_code == 404
        assert c.post(f"{BASE}/{gid}/realize", headers=h).status_code == 404
    ok = c.post(f"{BASE}/{gid}/environment-changes", json=body, headers=oidc_auth_headers("tenant-a", "alice"))
    assert ok.status_code == 201 and ok.json()["payload"]["tenant_id"] == "tenant-a"  # approval is tenant-keyed


def test_unbound_tenant_fails_closed(two_tenants, oidc_auth_headers):
    r = two_tenants.post(BASE, json={"goal": "plan my trip"}, headers=oidc_auth_headers("tenant-zzz", "alice"))
    assert r.status_code == 503
