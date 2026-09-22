from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import require_tenant
from app.modules.m03_grant_writer.routes import router
from app.modules.m03_grant_writer.service import Service
from app.modules.m03_grant_writer.schemas import ExportRequest


class ApprovalSpy:
    def __init__(self): self.items = []
    def put(self, item): self.items.append(item); return item


def test_export_approval_is_bound_to_service_tenant():
    spy = ApprovalSpy()
    service = Service(spy, tenant_id="tenant-a")
    service.propose_export(ExportRequest(title="Proposal", proposal="A sufficiently long proposal body for review."))
    assert spy.items[0].payload["tenant_id"] == "tenant-a"


def test_empty_tenant_fails_closed():
    try:
        Service(ApprovalSpy(), tenant_id="   ")
    except ValueError as exc:
        assert "tenant_id" in str(exc)
    else:
        raise AssertionError("empty tenant must fail")


def test_core_route_requires_authenticated_tenant_in_production(monkeypatch):
    monkeypatch.setenv("ATLAS_ENV", "production")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.post("/grant-writer/budgets", json={
        "currency": "USD",
        "items": [{"category": "Compute", "description": "GPU", "quantity": 1, "unit_cost": 10}],
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "OIDC bearer token required"
