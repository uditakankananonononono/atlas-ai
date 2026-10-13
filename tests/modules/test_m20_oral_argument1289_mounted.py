"""Row 1289 Oral Argument: mounted-app proof with real RS256 identities.

Every test hits POST /api/v1/api/modules/20/legal-1289/oral-argument through the
mounted application (TestClient over app.main.app) using real RS256 test
identities issued through the production verifier path (the conftest
oidc_auth_headers fixture; development auth bypass explicitly disabled per
test). At the package base the route does not exist, so each behavioral test
fails with an AssertionError on the 404 route result - not a collection,
import or environment error. Patched, the route executes the dedicated
row-1289 engine (five-label supplied-reference partition), which the
assertions distinguish from the generic shared legal engine by shape: the
dedicated result carries row/elements/coverage and never carries the generic
engine's named_capability_executed.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

ROUTE = "/api/v1/api/modules/20/legal-1289/oral-argument"
LABELS = ["likely_questions", "record_cites", "authorities", "concessions", "unknowns"]


@pytest.fixture
def rs256_client(monkeypatch, oidc_auth_headers):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    monkeypatch.setenv("ATLAS_ENV", "production")
    return TestClient(app), oidc_auth_headers("tenant-a", "tester")


def request(**kw):
    d = {"row": 1289, "as_of": "2026-10-12",
         "entries": [{"element": x, "status": "supplied", "source_ref": "private-ref"} for x in LABELS]}
    d.update(kw)
    return d


def post(client, body, headers):
    return client.post(ROUTE, json=body, headers=headers)


def test_unauthenticated_is_401(rs256_client):
    client, _ = rs256_client
    r = client.post(ROUTE, json={"data": request()})
    assert r.status_code == 401, r.text


def test_mounted_route_executes_dedicated_engine(rs256_client):
    client, headers = rs256_client
    r = post(client, {"data": request()}, headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["module_id"] == 20 and body["tenant_id"] == "tenant-a"
    assert body["actor_id"] == "tester" and body["requires_licensed_counsel"] is True
    result = body["result"]
    # dedicated engine shape, not the generic legal support engine
    assert result["row"] == 1289
    assert "named_capability_executed" not in result
    assert result["legal_conclusion"] is False and result["references_verified"] is False
    assert result["counsel_review_required"] is True
    assert [x["element"] for x in result["elements"]] == LABELS
    assert result["coverage"]["referenced"] == 5
    assert "private-ref" not in str(result)


def test_mounted_route_five_label_partition(rs256_client):
    client, headers = rs256_client
    entries = [{"element": "likely_questions", "status": "supplied", "source_ref": "r1"},
               {"element": "record_cites", "status": "disputed", "source_ref": "r2"},
               {"element": "authorities", "status": "missing"}]
    r = post(client, {"data": request(entries=entries)}, headers)
    assert r.status_code == 200, r.text
    coverage = r.json()["result"]["coverage"]
    assert coverage == {"elements_total": 5, "referenced": 1, "disputed": 1,
                        "declared_missing": 1, "unaddressed": 2}


def test_mounted_route_refusals_are_422_with_row_prefix(rs256_client):
    client, headers = rs256_client
    r = post(client, {"data": request(entries=[])}, headers)
    assert r.status_code == 422, r.text
    assert "ORALAR1289: EMPTY:entries" in r.json()["detail"]
    r = post(client, {"data": request(entries=[{"element": "torts", "status": "supplied",
                                                "source_ref": "x"}])}, headers)
    assert r.status_code == 422, r.text
    assert "ORALAR1289: UNKNOWN:element" in r.json()["detail"]
    r = post(client, {"data": request(file=1)}, headers)
    assert r.status_code == 422, r.text
    assert "ORALAR1289: EFFECT:file" in r.json()["detail"]
    r = post(client, {"data": request(row=1288)}, headers)
    assert r.status_code == 422, r.text
    assert "ORALAR1289: UNKNOWN:row" in r.json()["detail"]


def test_mounted_route_scope_mismatch_is_403(rs256_client):
    client, headers = rs256_client
    r = post(client, {"data": request(), "tenant_id": "tenant-b"}, headers)
    assert r.status_code == 403, r.text
    r = post(client, {"data": request(), "actor_id": "someone-else"}, headers)
    assert r.status_code == 403, r.text
    r = post(client, {"data": request(tenant_id="tenant-b")}, headers)
    assert r.status_code == 403, r.text
    r = post(client, {"data": request(actor_id="someone-else")}, headers)
    assert r.status_code == 403, r.text
