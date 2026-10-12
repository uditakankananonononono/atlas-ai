"""Outbound action dispatch gate tests (group 136). Stdlib only, hermetic.

Pins the enforcement: undeclared platforms deny fail-closed; ToS kind and
automation rules fire; rate limits count the gate's OWN ledger history (an
action stream cannot redeclare its history); consent and privacy-purpose
checks fire; needs_review requires the caller hook; the effect only runs on
admission; every decision is ledgered and verifiable.
"""
import pytest

from app.runtime.guardrails import outbound_gate as g
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T08:00:00Z"
DECL = {
    "tos": {"github": {"allowed_kinds": ["read", "comment"], "automation_allowed": True},
            "instagram": {"allowed_kinds": ["read"], "automation_allowed": False}},
    "rate_limits": {"github": {"read": {"max": 2, "window_seconds": 60},
                            "comment": {"max": 100, "window_seconds": 60}},
                    "instagram": {"read": {"max": 100, "window_seconds": 60}}},
    "consent": [{"subject": "alice", "purpose": "notify", "granted_at": 0}],
    "privacy": {"personal_categories": ["email", "location"], "purpose_allowed": {"notify": ["email"]}},
    "review_kinds": ["comment"],
    "recent_actions": [],
}


def act(aid, platform="github", kind="read", at=1000, **extra):
    base = {"id": aid, "platform": platform, "kind": kind, "at": at, "count": 1}
    base.update(extra)
    return base


def test_allowed_action_dispatches_and_effect_runs():
    ledger, result = g.dispatch(act("a1"), DECL, effect=lambda a: ("ran", a["id"]), now=T0)
    assert result == ("ran", "a1")
    assert ledger[-1]["record"]["verdict"] == "dispatched"
    assert ledger[-1]["record"]["failed_checks"] == []


def test_undeclared_platform_denied_fail_closed():
    ran = []
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("a2", platform="tiktok"), DECL, effect=ran.append, now=T0)
    assert held.value.code == "OUTGATE:refused:denied"
    assert "tos_declared" in held.value.details["failed_checks"]
    assert ran == []


def test_kind_not_allowed_denied():
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("a3", kind="post"), DECL, effect=lambda a: None, now=T0)
    assert "tos_kind_allowed" in held.value.details["failed_checks"]


def test_automation_not_allowed_denied():
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("a4", platform="instagram", automated=True), DECL,
                   effect=lambda a: None, now=T0)
    assert "tos_automation" in held.value.details["failed_checks"]


def test_rate_limit_counts_gate_ledger_history():
    ledger = []
    ledger, _ = g.dispatch(act("a1", at=1000), DECL, effect=lambda a: 1, now=T0, ledger=ledger)
    ledger, _ = g.dispatch(act("a2", at=1010), DECL, effect=lambda a: 2, now=T0, ledger=ledger)
    # third read within 60s exceeds max 2 - even though the caller declares
    # an EMPTY recent_actions, the gate rebuilds history from its own ledger
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("a3", at=1020), DECL, effect=lambda a: 3, now=T0, ledger=ledger)
    assert held.value.code == "OUTGATE:refused:denied"
    assert held.value.details["failed_checks"] == ["rate_limit"]
    # refusal contributed no usage: same action still refused, later action fine
    ledger = held.value.ledger
    with pytest.raises(GuardrailRefusal):
        g.dispatch(act("a4", at=1030), DECL, effect=lambda a: 4, now=T0, ledger=ledger)
    ledger, result = g.dispatch(act("a5", at=2000), DECL, effect=lambda a: 5, now=T0, ledger=ledger)
    assert result == 5
    assert len(g.history(ledger, "github")) == 3


def test_caller_recent_actions_stack_on_gate_history():
    ledger = []
    ledger, _ = g.dispatch(act("a1", at=1000), DECL, effect=lambda a: 1, now=T0, ledger=ledger)
    decl = dict(DECL, recent_actions=[{"platform": "github", "kind": "read", "at": 990, "count": 1}])
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("a2", at=1020), decl, effect=lambda a: 2, now=T0, ledger=ledger)
    assert held.value.details["failed_checks"] == ["rate_limit"]


def test_consent_missing_denied():
    action = act("a6", subjects=["bob"], purpose="notify", data_categories=["email"])
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(action, DECL, effect=lambda a: None, now=T0)
    assert "consent" in held.value.details["failed_checks"]


def test_consent_valid_passes():
    action = act("a7", subjects=["alice"], purpose="notify", data_categories=["email"])
    _, result = g.dispatch(action, DECL, effect=lambda a: "ok", now=T0)
    assert result == "ok"


def test_privacy_purpose_denied_for_undeclared_category():
    action = act("a8", subjects=["alice"], purpose="notify", data_categories=["location"])
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(action, DECL, effect=lambda a: None, now=T0)
    assert "privacy_purpose" in held.value.details["failed_checks"]


def test_needs_review_fails_closed_without_hook():
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("a9", kind="comment"), DECL, effect=lambda a: None, now=T0)
    assert held.value.code == "OUTGATE:refused:review_required"
    assert held.value.details["preflight_verdict"] == "needs_review"


def test_needs_review_rejected_by_hook():
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("a10", kind="comment"), DECL, effect=lambda a: None, now=T0,
                   review_check=lambda a: False)
    assert held.value.code == "OUTGATE:refused:review_required"


def test_needs_review_dispatches_after_hook_approval():
    ledger, result = g.dispatch(act("a11", kind="comment"), DECL, effect=lambda a: "posted",
                                now=T0, review_check=lambda a: True)
    assert result == "posted"
    rec = ledger[-1]["record"]
    assert rec["verdict"] == "dispatched:after_review"
    assert rec["review_checked"] is True and rec["review_accepted"] is True


def test_refusal_is_ledgered_and_verifiable():
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("a12", platform="tiktok"), DECL, effect=lambda a: None, now=T0)
    ledger = held.value.ledger
    g.check_ledger(ledger)
    assert ledger[-1]["record"]["verdict"] == "refused:denied"


def test_roundtrip_and_tamper_detection():
    ledger = []
    ledger, _ = g.dispatch(act("a1"), DECL, effect=lambda a: 1, now=T0, ledger=ledger)
    restored = g.loads(g.dumps(ledger))
    assert restored == ledger
    tampered = [dict(e, record=dict(e["record"])) for e in restored]
    tampered[0]["record"]["verdict"] = "refused:denied"
    with pytest.raises(ValueError, match="GRLEDGER:.*integrity"):
        g.check_ledger(tampered)


def test_malformed_inputs_raise_valueerror():
    with pytest.raises(ValueError, match="OUTGATE:bad_type:effect"):
        g.dispatch(act("a1"), DECL, effect=None, now=T0)
    with pytest.raises(ValueError, match="OUTGATE:bad_id:id"):
        g.dispatch({"platform": "github", "kind": "read", "at": 1}, DECL,
                   effect=lambda a: None, now=T0)
    with pytest.raises(ValueError, match="OUTGATE:bad_type:declarations"):
        g.dispatch(act("a1"), [], effect=lambda a: None, now=T0)
    with pytest.raises(ValueError):
        g.dispatch(act("a1"), DECL, effect=lambda a: None, now="not-a-time")
