"""Authority-binding tests.

Reviewer / verified_by / granted_by labels are DECLARATIONS, never
authentication. When a decision, grant or verification carries an
authority_ref (an approval-store reference), the gate requires the
caller-bound authority_check hook and fails closed without it or on its
rejection; a validated binding is ledgered as such.
"""
import pytest

from app.runtime.guardrails import owner_account_gate, review_gate

T0 = "2026-10-12T08:00:00Z"
ACTION = {"action_id": "sub-1", "category": "submission",
          "summary": "submit the reviewed form", "payload": {"form": "v1"}}


def _open():
    return review_gate.open_review([], ACTION, review_id="R1", reviewer="udita", now=T0)


def test_decision_without_authority_ref_is_a_declaration():
    ledger = review_gate.record_decision(_open(), review_id="R1", decision="approved",
                                         reviewer="udita", rationale="ok", now=T0)
    rec = ledger[-1]["record"]
    assert rec["authority_ref"] is None
    assert rec["authority_validated"] is False


def test_decision_authority_ref_fails_closed_without_hook():
    with pytest.raises(ValueError, match="REVGATE:authority_unverifiable"):
        review_gate.record_decision(_open(), review_id="R1", decision="approved",
                                    reviewer="udita", rationale="ok", now=T0,
                                    authority_ref="m00-approval-123")


def test_decision_authority_rejected_by_hook():
    with pytest.raises(ValueError, match="REVGATE:authority_rejected"):
        review_gate.record_decision(_open(), review_id="R1", decision="approved",
                                    reviewer="udita", rationale="ok", now=T0,
                                    authority_ref="m00-approval-123",
                                    authority_check=lambda ref: False)


def test_decision_authority_validated_and_ledgered():
    seen = []
    ledger = review_gate.record_decision(
        _open(), review_id="R1", decision="approved", reviewer="udita",
        rationale="ok", now=T0, authority_ref="m00-approval-123",
        authority_check=lambda ref: seen.append(ref) or True)
    rec = ledger[-1]["record"]
    assert seen == ["m00-approval-123"]
    assert rec["authority_ref"] == "m00-approval-123"
    assert rec["authority_validated"] is True
    review_gate.check_ledger(review_gate.loads(review_gate.dumps(ledger)))


def test_preauthorization_authority_binding():
    with pytest.raises(ValueError, match="REVGATE:authority_unverifiable"):
        review_gate.grant_preauthorization([], ACTION, preauth_id="PA1",
                                           granted_by="udita", now=T0, valid_hours=24,
                                           scope_note="s", authority_ref="m00-9")
    ledger = review_gate.grant_preauthorization(
        [], ACTION, preauth_id="PA1", granted_by="udita", now=T0, valid_hours=24,
        scope_note="s", authority_ref="m00-9", authority_check=lambda ref: ref == "m00-9")
    rec = ledger[-1]["record"]
    assert rec["authority_validated"] is True


def test_account_verification_authority_binding():
    ledger = owner_account_gate.register_binding([], "github", "owner",
                                                 registered_by="u", now=T0)
    with pytest.raises(ValueError, match="ACCTGATE:authority_unverifiable"):
        owner_account_gate.verify_binding(ledger, "github", "owner", verified_by="u",
                                          now=T0, authority_ref="m00-7")
    with pytest.raises(ValueError, match="ACCTGATE:authority_rejected"):
        owner_account_gate.verify_binding(ledger, "github", "owner", verified_by="u",
                                          now=T0, authority_ref="m00-7",
                                          authority_check=lambda ref: False)
    ledger = owner_account_gate.verify_binding(
        ledger, "github", "owner", verified_by="u", now=T0,
        authority_ref="m00-7", authority_check=lambda ref: True)
    rec = ledger[-1]["record"]
    assert rec["authority_ref"] == "m00-7"
    assert rec["authority_validated"] is True


def test_ledger_rejects_validated_without_reference():
    ledger = owner_account_gate.register_binding([], "github", "owner",
                                                 registered_by="u", now=T0)
    ledger = owner_account_gate.verify_binding(ledger, "github", "owner",
                                               verified_by="u", now=T0)
    forged = [dict(e, record=dict(e["record"])) for e in ledger]
    rec = forged[-1]["record"]
    rec["authority_validated"] = True
    import hashlib, json
    prev = forged[-1]["prev_hash"]
    payload = json.dumps({"seq": 1, "record": rec, "prev_hash": prev},
                         sort_keys=True, separators=(",", ":"))
    forged[-1]["record_hash"] = hashlib.sha256(payload.encode()).hexdigest()
    with pytest.raises(ValueError, match="ACCTGATE:.*without a reference"):
        owner_account_gate.check_ledger(forged)
