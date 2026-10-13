from fastapi.testclient import TestClient
from app.main import app
import pytest

ROW = 1297
PATH = "/api/v1/api/modules/20/legal/1297/support"
VOCAB = ('language', 'disability', 'cost', 'geography', 'procedure', 'service_resource_evidence')
PREFIX = 'ACCESS1297:'
BOUNDARY = "Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use."

@pytest.fixture
def client():
    return TestClient(app)

def request(entries=None, **kw):
    data = {"row": ROW, "as_of": "2026-10-12", "entries": entries if entries is not None else [{"element": VOCAB[0], "status": "supplied", "source_ref": "PRIVATE-REF"}]}
    data.update(kw)
    return data

def post(client, data):
    return client.post(PATH, json=data)

def test_row_1297_mounted_identity_and_vocabulary(client):
    response = post(client, request([{"element": v, "status": "supplied", "source_ref": "PRIVATE-REF"} for v in VOCAB]))
    assert response.status_code == 200, response.text
    out = response.json()
    assert set(out) == {"row", "elements", "coverage", "counsel_review_required", "legal_conclusion", "references_verified", "boundary", "scope"}
    assert out["row"] == ROW
    assert [x["element"] for x in out["elements"]] == list(VOCAB)
    assert out["coverage"] == {"elements_total": len(VOCAB), "referenced": len(VOCAB), "disputed": 0, "declared_missing": 0, "unaddressed": 0}

def test_row_1297_boundary_and_no_reference_echo(client):
    response = post(client, request())
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["counsel_review_required"] is True
    assert out["legal_conclusion"] is False
    assert out["references_verified"] is False
    assert out["boundary"] == BOUNDARY
    assert "PRIVATE-REF" not in response.text

def test_row_1297_status_partition_and_dates(client):
    entries = [{"element": VOCAB[0], "status": "supplied", "source_ref": "a", "entry_date": "2026-10-09"}, {"element": VOCAB[0], "status": "supplied", "source_ref": "b", "entry_date": "2026-10-10"}, {"element": VOCAB[0], "status": "missing"}, {"element": VOCAB[1], "status": "disputed", "source_ref": "c"}, {"element": VOCAB[2], "status": "missing"}]
    response = post(client, request(entries))
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["elements"][0] == {"element": VOCAB[0], "status": "referenced", "also_declared_missing": True, "latest_entry_date": "2026-10-10", "days_since_latest": 2}
    assert [x["status"] for x in out["elements"][:3]] == ["referenced", "disputed", "declared_missing"]
    assert out["coverage"]["unaddressed"] == len(VOCAB)-3

def test_row_1297_wrong_row_and_unknown_element(client):
    for data, code in [(request(row=9999), "UNKNOWN:row"), (request([{"element": "non_vocab_PRIVATE", "status": "supplied", "source_ref": "PRIVATE-REF"}]), "UNKNOWN:element")]:
        response = post(client, data)
        assert response.status_code == 422, response.text
        assert response.json() == {"detail": PREFIX + " " + code}
        assert "PRIVATE" not in response.text

def test_row_1297_forbidden_effect_refused(client):
    response = post(client, request(send=False))
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": PREFIX + " SEND:send"}

def test_row_1297_empty_and_oversize(client):
    for entries, code in [([], "EMPTY:entries"), ([{"element": VOCAB[0], "status": "missing"}]*201, "OVERSIZE:entries")]:
        response = post(client, request(entries))
        assert response.status_code == 422, response.text
        assert response.json() == {"detail": PREFIX + " " + code}

def test_row_1297_future_date_refused(client):
    response = post(client, request([{"element": VOCAB[0], "status": "supplied", "source_ref": "r", "entry_date": "2026-10-13"}]))
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": PREFIX + " BAD_TYPE:entry_date"}

def test_row_1297_duplicate_refused(client):
    item = {"element": VOCAB[0], "status": "supplied", "source_ref": "r"}
    response = post(client, request([item, item]))
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": PREFIX + " BAD_TYPE:entries"}

def test_row_1297_production_identity_enforced(client, monkeypatch, oidc_auth_headers):
    monkeypatch.setenv("ATLAS_ENV", "production")
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    response = client.post(PATH, json=request(), headers=oidc_auth_headers())
    assert response.status_code == 200, response.text
    assert response.json()["row"] == ROW
    assert client.post(PATH, json=request()).status_code == 401
