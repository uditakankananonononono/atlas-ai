"""Mounted dedicated legal computation surfaces over caller-supplied records only."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker import legal_project_management1307 as engine

PATH = "/api/v1/api/modules/20/legal/1307/run"

@pytest.fixture(autouse=True)
def production_identity(monkeypatch):
    monkeypatch.setenv("ATLAS_DEV_NO_AUTH", "0")
    monkeypatch.setenv("ATLAS_ENV", "production")


@pytest.fixture
def packet():
    return {'row': 1307, 'as_of': '2026-10-12', 'entries': [{'element': 'deliverables', 'status': 'supplied', 'source_ref': 'reference-A', 'entry_date': '2026-10-01'}]}


def test_mounted_value_and_actual_engine(packet, oidc_auth_headers):
    expected = engine.run(packet)
    with TestClient(app) as client:
        response = client.post(PATH, json={"data": packet}, headers=oidc_auth_headers())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {**expected, "tenant_id": "tenant-a", "actor_id": "tester"}
    assert body["elements"][0]["days_since_latest"] == 11
    assert body["coverage"]["referenced"] == 1
    assert body["legal_conclusion"] is False


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
    from app.modules.m20_general_cognitive_worker import legal_project_management1307_routes as adapter
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
