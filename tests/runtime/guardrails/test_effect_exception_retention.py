"""Post-effect-exception retention tests (gate defect 0011).

Pins the durability rule: when an effect raises AFTER a gate admitted it,
the admission/spend records are never lost - the gate commits them
write-ahead via on_commit and attaches the ledger to the escaping exception,
and the enforcer persists them. An ambiguous outcome reconciles as
spent-pending-review, never silently re-usable.
"""
import pytest

from app.runtime.guardrails import bio_gate, outbound_gate, owner_account_gate, review_gate
from app.runtime.guardrails.errors import GuardrailRefusal, take_ledger

T0 = "2026-10-12T08:00:00Z"
SILICO = {"id": "w1", "text": "compute k-mer statistics",
          "domain_terms": ["crispr"], "execution_mode": "computational"}
DECL = {
    "tos": {"github": {"allowed_kinds": ["read"], "automation_allowed": True}},
    "rate_limits": {"github": {"read": {"max": 1, "window_seconds": 60}}},
    "consent": [], "recent_actions": [],
}
ACTION = {"action_id": "sub-1", "category": "submission",
          "summary": "submit the reviewed form", "payload": {"form": "v1"}}


def boom(_):
    raise RuntimeError("side effect happened, then failure")


def test_bio_effect_exception_carries_committed_ledger():
    commits = []
    with pytest.raises(RuntimeError) as held:
        bio_gate.run_guarded(boom, SILICO, now=T0, on_commit=commits.append)
    # write-ahead: admission was committed BEFORE the effect ran
    assert len(commits) == 2
    assert commits[0][-1]["record"]["verdict"] == "admitted:in_silico"
    assert commits[1][-1]["record"]["outcome"] == "failed"
    retained = take_ledger(held.value)
    assert retained is not None
    assert retained[-1]["record"]["error_type"] == "RuntimeError"
    bio_gate.check_ledger(retained)


def test_outbound_effect_exception_keeps_admission_and_rate_budget():
    commits = []
    with pytest.raises(RuntimeError) as held:
        outbound_gate.dispatch({"id": "a1", "platform": "github", "kind": "read",
                                "at": 1000, "count": 1}, DECL, effect=boom, now=T0,
                               on_commit=commits.append)
    assert commits and commits[0][-1]["record"]["verdict"] == "dispatched"
    retained = take_ledger(held.value)
    # the ambiguous attempt still consumes the rate budget: next call refuses
    assert len(outbound_gate.history(retained, "github")) == 1
    with pytest.raises(GuardrailRefusal) as held2:
        outbound_gate.dispatch({"id": "a2", "platform": "github", "kind": "read",
                                "at": 1010, "count": 1}, DECL, effect=lambda a: None,
                               now=T0, ledger=retained)
    assert held2.value.details["failed_checks"] == ["rate_limit"]


def _approved_ledger():
    ledger = review_gate.open_review([], ACTION, review_id="R1", reviewer="udita", now=T0)
    ledger = review_gate.record_decision(ledger, review_id="R1", decision="approved",
                                         reviewer="udita", rationale="ok", now=T0)
    return review_gate.issue_permit(ledger, ACTION, review_id="R1", now=T0)


def test_permit_stays_spent_when_effect_raises():
    ledger, permit = _approved_ledger()
    commits = []
    with pytest.raises(RuntimeError) as held:
        review_gate.execute(ledger, ACTION, effect=boom, now="2026-10-12T09:00:00Z",
                            permit_id=permit["permit_id"], on_commit=commits.append)
    # write-ahead: spend committed BEFORE the effect ran
    assert commits[0][-1]["record"]["kind"] == "permit_spent"
    retained = take_ledger(held.value)
    # the permit is NOT silently re-usable after the ambiguous outcome
    with pytest.raises(GuardrailRefusal) as held2:
        review_gate.execute(retained, ACTION, effect=lambda a: "replay",
                            now="2026-10-12T09:01:00Z", permit_id=permit["permit_id"])
    assert "permit already spent" in held2.value.details["reasons"]


def test_preauthorization_use_kept_when_effect_raises():
    ledger = review_gate.grant_preauthorization([], ACTION, preauth_id="PA1",
                                                granted_by="udita", now=T0,
                                                valid_hours=48, scope_note="grant")
    commits = []
    with pytest.raises(RuntimeError) as held:
        review_gate.execute(ledger, ACTION, effect=boom, now="2026-10-12T09:00:00Z",
                            on_commit=commits.append)
    assert commits[0][-1]["record"]["kind"] == "preauthorization_used"
    retained = take_ledger(held.value)
    review_gate.check_ledger(retained)
    assert retained[-1]["record"]["kind"] == "preauthorization_used"


def test_account_call_failure_record_committed_and_carried():
    ledger = owner_account_gate.register_binding([], "github", "owner",
                                                 registered_by="u", now=T0)
    ledger = owner_account_gate.verify_binding(ledger, "github", "owner",
                                               verified_by="u", now=T0)
    commits = []

    def boom0():
        raise ConnectionError("api down mid-write")

    with pytest.raises(ConnectionError) as held:
        owner_account_gate.call(ledger, "c1", "github", "owner", effect=boom0,
                                now=T0, on_commit=commits.append)
    assert commits[0][-1]["record"]["verdict"] == "admitted"
    assert commits[1][-1]["record"]["failure"] == "ConnectionError"
    retained = take_ledger(held.value)
    assert retained[-1]["record"]["failure"] == "ConnectionError"
    owner_account_gate.check_ledger(retained)


def test_keyboard_interrupt_style_base_exception_also_retained():
    def interrupt(_):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt) as held:
        bio_gate.run_guarded(interrupt, SILICO, now=T0)
    retained = take_ledger(held.value)
    assert retained[-1]["record"]["error_type"] == "KeyboardInterrupt"
