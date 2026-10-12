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
                                    authority_check=lambda ref, digest: False)


def test_decision_authority_validated_and_ledgered():
    seen = []
    ledger = review_gate.record_decision(
        _open(), review_id="R1", decision="approved", reviewer="udita",
        rationale="ok", now=T0, authority_ref="m00-approval-123",
        authority_check=lambda ref, digest: seen.append(ref) or True)
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
        scope_note="s", authority_ref="m00-9", authority_check=lambda ref, digest: ref == "m00-9")
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
                                          authority_check=lambda ref, digest: False)
    ledger = owner_account_gate.verify_binding(
        ledger, "github", "owner", verified_by="u", now=T0,
        authority_ref="m00-7", authority_check=lambda ref, digest: True)
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


# ---- 0012: configured hook makes authority validated-only -----------------

OK = lambda ref, digest: True  # noqa: E731


def test_hook_configured_decision_without_ref_fails_closed():
    with pytest.raises(ValueError, match="REVGATE:authority_required"):
        review_gate.record_decision(_open(), review_id="R1", decision="approved",
                                    reviewer="udita", rationale="ok", now=T0,
                                    authority_check=OK)


def test_hook_configured_preauth_without_ref_fails_closed():
    with pytest.raises(ValueError, match="REVGATE:authority_required"):
        review_gate.grant_preauthorization([], ACTION, preauth_id="PA1",
                                           granted_by="udita", now=T0, valid_hours=24,
                                           scope_note="s", authority_check=OK)


def test_hook_configured_account_verification_without_ref_fails_closed():
    ledger = owner_account_gate.register_binding([], "github", "owner",
                                                 registered_by="u", now=T0)
    with pytest.raises(ValueError, match="ACCTGATE:authority_required"):
        owner_account_gate.verify_binding(ledger, "github", "owner", verified_by="u",
                                          now=T0, authority_check=OK)


def test_decision_hook_receives_reviewed_action_digest():
    seen = []
    ledger = review_gate.record_decision(
        _open(), review_id="R1", decision="approved", reviewer="udita",
        rationale="ok", now=T0, authority_ref="m00-1",
        authority_check=lambda ref, digest: seen.append(digest) or True)
    from app.runtime.guardrails._fields import payload_sha256
    assert seen == [payload_sha256(ACTION["payload"])]


def test_preauth_hook_receives_granted_action_digest():
    seen = []
    review_gate.grant_preauthorization(
        [], ACTION, preauth_id="PA1", granted_by="udita", now=T0, valid_hours=24,
        scope_note="s", authority_ref="m00-1",
        authority_check=lambda ref, digest: seen.append(digest) or True)
    from app.runtime.guardrails._fields import payload_sha256
    assert seen == [payload_sha256(ACTION["payload"])]


def test_account_hook_receives_binding_digest():
    seen = []
    ledger = owner_account_gate.register_binding([], "github", "owner",
                                                 registered_by="u", now=T0)
    owner_account_gate.verify_binding(ledger, "github", "owner", verified_by="u",
                                      now=T0, authority_ref="m00-1",
                                      authority_check=lambda ref, digest: seen.append(digest) or True)
    from app.runtime.guardrails._fields import payload_sha256
    assert seen == [payload_sha256({"service": "github", "account_identity": "owner"})]


def _unvalidated_approved_ledger():
    ledger = _open()  # decision recorded with NO hook: a declaration
    return review_gate.record_decision(ledger, review_id="R1", decision="approved",
                                       reviewer="udita", rationale="ok", now=T0)


def test_issue_permit_fails_closed_on_unvalidated_decision():
    ledger = _unvalidated_approved_ledger()
    with pytest.raises(ValueError, match="not authority-validated"):
        review_gate.issue_permit(ledger, ACTION, review_id="R1", now=T0,
                                 authority_check=OK)
    # without a hook configured the declaration path still issues (documented)
    ledger2, permit = review_gate.issue_permit(ledger, ACTION, review_id="R1", now=T0)
    assert permit["permit_id"] == "PERMIT-R1"


def test_execute_refuses_unvalidated_decision_permit():
    from app.runtime.guardrails.errors import GuardrailRefusal
    ledger = _unvalidated_approved_ledger()
    ledger, permit = review_gate.issue_permit(ledger, ACTION, review_id="R1", now=T0)
    with pytest.raises(GuardrailRefusal) as held:
        review_gate.execute(ledger, ACTION, effect=lambda a: "ran",
                            now="2026-10-12T09:00:00Z",
                            permit_id=permit["permit_id"], authority_check=OK)
    assert "decision is not authority-validated" in held.value.details["reasons"]
    # the effect never ran and the permit was NOT spent by the refusal:
    # without a hook configured (the documented declaration path) it runs
    ledger, result = review_gate.execute(ledger, ACTION, effect=lambda a: "ran",
                                         now="2026-10-12T09:00:00Z",
                                         permit_id=permit["permit_id"])
    assert result == "ran"


def test_execute_refuses_unvalidated_preauthorization():
    from app.runtime.guardrails.errors import GuardrailRefusal
    ledger = review_gate.grant_preauthorization([], ACTION, preauth_id="PA1",
                                                granted_by="udita", now=T0,
                                                valid_hours=48, scope_note="grant")
    with pytest.raises(GuardrailRefusal, match="not authority-validated"):
        review_gate.execute(ledger, ACTION, effect=lambda a: "ran",
                            now="2026-10-12T09:00:00Z", authority_check=OK)


def test_execute_validated_permit_still_runs():
    ledger = review_gate.record_decision(
        _open(), review_id="R1", decision="approved", reviewer="udita",
        rationale="ok", now=T0, authority_ref="m00-1", authority_check=OK)
    ledger, permit = review_gate.issue_permit(ledger, ACTION, review_id="R1",
                                              now=T0, authority_check=OK)
    ledger, result = review_gate.execute(ledger, ACTION, effect=lambda a: "ran",
                                         now="2026-10-12T09:00:00Z",
                                         permit_id=permit["permit_id"],
                                         authority_check=OK)
    assert result == "ran"
