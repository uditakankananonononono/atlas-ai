import hashlib
import json

from fastapi.testclient import TestClient

from app.main import app

C = TestClient(app)
U = "/api/v1/email-assistant/promise-state-reconciliation/verify"
H = {"X-Atlas-Tenant": "lab", "X-Atlas-Actor": "owner"}


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def promise(promise_id="p1", state="open"):
    return {
        "promise_id": promise_id,
        "commitment": "send the protocol",
        "source_message_id": "original-1",
        "source_excerpt": "I will send the protocol by Friday",
        "state": state,
        "revision": 1,
        "last_review_sha256": None,
    }


def request(action="complete", body="I sent the protocol this morning.", excerpt=None):
    row = promise()
    snapshot = {"thread_id": "thread-1", "promises": [row]}
    excerpt = body if excerpt is None else excerpt
    return {
        "previous_snapshot": snapshot,
        "previous_snapshot_sha256": sha(snapshot),
        "update_messages": [{
            "message_id": "update-1", "direction": "owner",
            "sent_at": "2026-09-22T03:00:00Z", "body": body,
        }],
        "reviewed_decisions": [{
            "decision_id": "review-1", "promise_id": "p1", "action": action,
            "reviewer_id": "owner", "reviewed_at": "2026-09-22T03:05:00Z",
            "evidence_message_id": "update-1", "evidence_excerpt": excerpt,
            "previous_promise_sha256": sha(row),
        }],
    }


def test_reconciles_explicit_reviewed_completion_and_hashes_snapshot():
    response = C.post(U, json=request(), headers=H)
    assert response.status_code == 200
    result = response.json()
    assert result["tenant_id"] == "lab" and result["valid"] is True
    assert result["completed_count"] == 1 and result["review_count"] == 1
    stored = result["reconciled_snapshot"]["promises"][0]
    assert stored["state"] == "completed" and stored["revision"] == 2
    assert len(stored["last_review_sha256"]) == 64
    assert len(result["reconciled_snapshot_sha256"]) == 64
    assert "transactionally persist" in result["boundary"]


def test_ambiguous_completion_fails_closed_instead_of_auto_closing():
    response = C.post(U, json=request(body="It should be handled soon."), headers=H)
    assert response.status_code == 422
    assert "ambiguous; keep the promise open" in response.text


def test_other_party_cannot_supply_completion_evidence():
    payload = request()
    payload["update_messages"][0]["direction"] = "other"
    response = C.post(U, json=payload, headers=H)
    assert response.status_code == 422 and "owner-authored" in response.text


def test_rejects_stale_snapshot_and_promise_hashes():
    payload = request()
    payload["previous_snapshot_sha256"] = "f" * 64
    response = C.post(U, json=payload, headers=H)
    assert response.status_code == 422 and "snapshot hash mismatch" in response.text
    payload = request()
    payload["reviewed_decisions"][0]["previous_promise_sha256"] = "f" * 64
    response = C.post(U, json=payload, headers=H)
    assert response.status_code == 422 and "promise hash mismatch" in response.text


def test_keep_open_records_review_without_claiming_completion():
    payload = request(action="keep_open", body="I might get to the protocol soon.")
    response = C.post(U, json=payload, headers=H)
    assert response.status_code == 200
    result = response.json()
    assert result["completed_count"] == 0
    assert result["reconciled_snapshot"]["promises"][0]["state"] == "open"
    assert result["reconciled_snapshot"]["promises"][0]["revision"] == 2
