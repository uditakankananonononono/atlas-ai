"""Mounted dedicated legal computation surfaces over caller-supplied records only."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker import legal_billing1305 as engine

PATH = "/api/v1/api/modules/20/legal/1305/run"

@pytest.fixture(autouse=True)
def production_identity(monkeypatch):
    monkeypatch.setenv("ATLAS_DEV_NO_AUTH", "0")
    monkeypatch.setenv("ATLAS_ENV", "production")


@pytest.fixture
def packet():
    return {'batch_id': 'sample', 'entries': [{'entry_id': 'entry-1', 'matter_id': 'matter-A', 'hours': '1.5', 'rate': '20'}]}


def test_mounted_value_and_actual_engine(packet, oidc_auth_headers):
    expected = engine.prepare_invoices(packet)
    with TestClient(app) as client:
        response = client.post(PATH, json={"data": packet}, headers=oidc_auth_headers())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {**expected, "tenant_id": "tenant-a", "actor_id": "tester"}
    assert body["grand_total"] == "30"
    assert body["total_hours"] == "1.5"
    assert body["payment_executed"] is False


def test_malformed_engine_input_is_422(oidc_auth_headers):
    with TestClient(app) as client:
        response = client.post(PATH, json={"data": {}}, headers=oidc_auth_headers())
    assert response.status_code == 422


@pytest.mark.parametrize("claims", [{"tenant_id": "other"}, {"actor_id": "other"},
    {"resource_refs": [{"tenant_id": "other"}]}])
def test_owner_boundary(packet, oidc_auth_headers, claims):
    with TestClient(app) as client:
        response = client.post(PATH, json={"data": packet, **claims}, headers=oidc_auth_headers())
    assert response.status_code == 403


def test_production_requires_auth(packet, monkeypatch):
    monkeypatch.setenv("ATLAS_DEV_NO_AUTH", "0")
    monkeypatch.setenv("ATLAS_ENV", "production")
    with TestClient(app) as client:
        response = client.post(PATH, json={"data": packet})
    assert response.status_code == 401


def test_invalid_unicode_is_422(packet, oidc_auth_headers):
    with TestClient(app) as client:
        response = client.post(PATH, content='{"data":{"bad":"\\ud800"}}',
            headers={**oidc_auth_headers(), "Content-Type": "application/json"})
    assert response.status_code == 422


def test_route_calls_dedicated_callable(packet, oidc_auth_headers, monkeypatch):
    from app.modules.m20_general_cognitive_worker import legal_billing1305_routes as adapter
    seen = []
    def computation(data):
        seen.append(data)
        return {"dedicated_call": True}
    monkeypatch.setattr(adapter, "compute", computation)
    with TestClient(app) as client:
        response = client.post(PATH, json={"data": packet}, headers=oidc_auth_headers())
    assert response.status_code == 200
    assert response.json()["dedicated_call"] is True
    assert seen == [packet]
