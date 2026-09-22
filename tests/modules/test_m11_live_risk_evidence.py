import hashlib
import json

from fastapi.testclient import TestClient

from app.main import app

C = TestClient(app)
U = "/api/v1/calendar-intelligence/schedule-risk/live-evidence/verify"
H = {"X-Atlas-Tenant": "lab", "X-Atlas-Actor": "owner"}
D = "a" * 64


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source(retrieved="2026-09-22T03:45:00Z"):
    return {
        "source_uri": "https://provider.example/snapshot/1",
        "retrieved_at": retrieved,
        "content_sha256": D,
        "retrieval_method": "official_api",
        "snapshot_bytes_base64_sha256": D,
    }


def payload():
    travel = {
        "estimate_id": "map-1", "provider": "maps", "origin": "A", "destination": "B",
        "mode": "driving", "duration_minutes": 42, "route_distance_meters": 18000,
        "source": source(),
    }
    travel["source_record_sha256"] = sha(travel)
    policy = {
        "policy_id": "policy-1", "vendor": "venue", "booking_reference_sha256": "b" * 64,
        "free_cancel_until": "2026-09-23T04:00:00Z", "cancellation_fee": 80.0,
        "currency": "USD", "policy_text_excerpt": "Free cancellation until the stated deadline.",
        "source": {**source(), "retrieval_method": "vendor_page"},
    }
    policy["source_record_sha256"] = sha(policy)
    return {
        "as_of": "2026-09-22T04:00:00Z", "max_age_minutes": 60,
        "travel_estimates": [travel], "cancellation_policies": [policy],
    }


def test_verifies_fresh_map_and_policy_snapshots_with_retrieval_provenance():
    response = C.post(U, json=payload(), headers=H)
    assert response.status_code == 200
    result = response.json()
    assert result["valid"] and result["tenant_id"] == "lab"
    assert result["travel_estimates"][0]["duration_minutes"] == 42
    assert result["cancellation_policies"][0]["cancellation_fee"] == 80
    assert result["travel_estimates"][0]["verification"]["retrieved_at"].endswith("+00:00")
    assert len(result["artifact_sha256"]) == 64
    assert "does not fetch" in result["boundary"]


def test_fails_closed_on_stale_or_future_retrieval():
    value = payload()
    value["travel_estimates"][0]["source"]["retrieved_at"] = "2026-09-22T01:00:00Z"
    value["travel_estimates"][0]["source_record_sha256"] = sha({k: v for k, v in value["travel_estimates"][0].items() if k != "source_record_sha256"})
    response = C.post(U, json=value, headers=H)
    assert response.status_code == 422 and "stale" in response.text
    value = payload()
    value["travel_estimates"][0]["source"]["retrieved_at"] = "2026-09-22T05:00:00Z"
    value["travel_estimates"][0]["source_record_sha256"] = sha({k: v for k, v in value["travel_estimates"][0].items() if k != "source_record_sha256"})
    response = C.post(U, json=value, headers=H)
    assert response.status_code == 422 and "after as_of" in response.text


def test_rejects_tampered_normalized_record_and_snapshot_mismatch():
    value = payload()
    value["travel_estimates"][0]["duration_minutes"] = 99
    response = C.post(U, json=value, headers=H)
    assert response.status_code == 422 and "record hash mismatch" in response.text
    value = payload()
    value["cancellation_policies"][0]["source"]["snapshot_bytes_base64_sha256"] = "c" * 64
    value["cancellation_policies"][0]["source_record_sha256"] = sha({k: v for k, v in value["cancellation_policies"][0].items() if k != "source_record_sha256"})
    response = C.post(U, json=value, headers=H)
    assert response.status_code == 422 and "snapshot hashes differ" in response.text
