"""Hook API contract tests.

Approval/review/authority hooks accept ONLY a strict boolean True or a
structured verified-permit mapping {"verified": True}. Truthy non-True
values (1, "yes", non-empty strings) are rejections. The bio hook receives
the exact action digest so an approval binds to the action's content.
"""
import pytest

from app.runtime.guardrails import (bio_gate, outbound_gate, owner_account_gate,
                                    review_gate)

T0 = "2026-10-12T08:00:00Z"
DECL = {
    "tos": {"github": {"allowed_kinds": ["read"], "automation_allowed": True}},
    "rate_limits": {"github": {"read": {"max": 5, "window_seconds": 60}}},
    "consent": [], "recent_actions": [],
}
ACTION = {"action_id": "sub-1", "category": "submission",
          "summary": "submit the reviewed form", "payload": {"form": "v1"}}


def _flagged_item():
    return {"id": "w1", "text": "bench validation of the candidate",
            "domain_terms": ["vaccine"], "execution_mode": "physical",
            "approval_ref": "IRB-1"}


def _outbound():
    return {"id": "a1", "platform": "github", "kind": "read", "at": 1000, "count": 1}


def _review_ledger():
    return review_gate.open_review([], ACTION, review_id="R1", reviewer="u", now=T0)


def _account_ledger():
    return owner_account_gate.register_binding([], "github", "owner",
                                               registered_by="u", now=T0)


@pytest.mark.parametrize("truthy", [1, "yes", "approved", ["ok"], 2.5])
def test_bio_hook_truthy_non_true_is_rejection(truthy):
    _, rec = bio_gate.admit(_flagged_item(), now=T0,
                            approval_check=lambda ref, digest: truthy)
    assert rec["approval_checked"] is True
    assert rec["approval_accepted"] is False
    assert rec["verdict"] == "refused:physical_approval_rejected"


def test_bio_hook_strict_true_accepts():
    _, rec = bio_gate.admit(_flagged_item(), now=T0,
                            approval_check=lambda ref, digest: True)
    assert rec["approval_accepted"] is True
    assert rec["verdict"] == "admitted:physical_with_validated_approval"


def test_bio_hook_structured_permit_object_accepts():
    _, rec = bio_gate.admit(
        _flagged_item(), now=T0,
        approval_check=lambda ref, digest: {"verified": True, "permit": "m00-1"})
    assert rec["approval_accepted"] is True


def test_bio_hook_mapping_with_truthy_non_true_verified_rejects():
    _, rec = bio_gate.admit(_flagged_item(), now=T0,
                            approval_check=lambda ref, digest: {"verified": 1})
    assert rec["approval_accepted"] is False


def test_bio_hook_receives_exact_action_digest():
    from app.runtime.guardrails._fields import payload_sha256
    seen = []
    item = _flagged_item()
    _, rec = bio_gate.admit(item, now=T0,
                            approval_check=lambda ref, digest: seen.append((ref, digest)) or True)
    assert seen == [("IRB-1", payload_sha256(item))]
    assert rec["action_digest"] == payload_sha256(item)
    # content binding: a changed action yields a different digest
    other = dict(item, text="culture a different strain")
    _, rec2 = bio_gate.admit(other, now=T0,
                             approval_check=lambda ref, digest: seen.append((ref, digest)) or True)
    assert rec2["action_digest"] != rec["action_digest"]
    assert seen[1][1] == payload_sha256(other)


def test_bio_decision_digest_survives_serialization():
    item = _flagged_item()
    ledger, rec = bio_gate.admit(item, now=T0,
                                 approval_check=lambda ref, digest: True)
    bio_gate.check_ledger(bio_gate.loads(bio_gate.dumps(ledger)))


@pytest.mark.parametrize("truthy", [1, "ok", ["r"]])
def test_outbound_review_hook_truthy_non_true_is_rejection(truthy):
    from app.runtime.guardrails.errors import GuardrailRefusal
    decl = {"tos": {"github": {"allowed_kinds": ["read"], "automation_allowed": True}},
            "rate_limits": {"github": {"read": {"max": 5, "window_seconds": 60}}},
            "consent": [], "recent_actions": [], "review_kinds": ["read"]}
    with pytest.raises(GuardrailRefusal) as held:
        outbound_gate.dispatch(_outbound(), decl, effect=lambda a: None, now=T0,
                               review_check=lambda action: truthy)
    assert held.value.code == "OUTGATE:refused:review_required"


def test_review_authority_hook_truthy_non_true_fails():
    with pytest.raises(ValueError, match="REVGATE:authority_rejected"):
        review_gate.record_decision(_review_ledger(), review_id="R1",
                                    decision="approved", reviewer="u",
                                    rationale="ok", now=T0,
                                    authority_ref="m00-1",
                                    authority_check=lambda ref, digest: 1)


def test_owner_authority_hook_truthy_non_true_fails():
    with pytest.raises(ValueError, match="ACCTGATE:authority_rejected"):
        owner_account_gate.verify_binding(_account_ledger(), "github", "owner",
                                          verified_by="u", now=T0,
                                          authority_ref="m00-1",
                                          authority_check=lambda ref, digest: "yes")


def test_hooks_accept_structured_permit_objects():
    ledger = review_gate.record_decision(
        _review_ledger(), review_id="R1", decision="approved", reviewer="u",
        rationale="ok", now=T0, authority_ref="m00-1",
        authority_check=lambda ref, digest: {"verified": True, "permit": ref})
    assert ledger[-1]["record"]["authority_validated"] is True
    ledger = owner_account_gate.verify_binding(
        _account_ledger(), "github", "owner", verified_by="u", now=T0,
        authority_ref="m00-1", authority_check=lambda ref, digest: {"verified": True})
    assert ledger[-1]["record"]["authority_validated"] is True
