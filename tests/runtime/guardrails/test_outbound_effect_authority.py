"""Owner effect authority for person-facing outbound kinds.

ToS-allow is NEVER sufficient for EFFECT_KINDS (send/post/submit/invite/
account/payment): those independently require a configured authority_check
hook and a validated authority_ref bound to the action digest. Public reads
stay policy admission. Docs claim owner-gating for exactly EFFECT_KINDS.
"""
import pytest

from app.runtime.guardrails import outbound_gate as g
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T08:00:00Z"
OK = lambda ref, digest: True  # noqa: E731
DECL = {
    "tos": {"github": {"allowed_kinds": ["read"] + list(g.EFFECT_KINDS),
                       "automation_allowed": True}},
    "rate_limits": {"github": {k: {"max": 100, "window_seconds": 60}
                               for k in ["read"] + list(g.EFFECT_KINDS)}},
    "consent": [], "recent_actions": [],
}


def act(aid, kind="post", at=1000, **extra):
    base = {"id": aid, "platform": "github", "kind": kind, "at": at, "count": 1}
    base.update(extra)
    return base


@pytest.mark.parametrize("kind", g.EFFECT_KINDS)
def test_every_effect_kind_refuses_without_hook(kind):
    ran = []
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("e1", kind=kind), DECL, effect=ran.append, now=T0)
    assert held.value.code == "OUTGATE:refused:authority_hook_required"
    assert ran == []
    assert held.value.ledger[-1]["record"]["authority_checked"] is True


@pytest.mark.parametrize("kind", g.EFFECT_KINDS)
def test_every_effect_kind_refuses_without_ref(kind):
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("e2", kind=kind), DECL, effect=lambda a: None, now=T0,
                   authority_check=OK)
    assert held.value.code == "OUTGATE:refused:authority_required"


def test_effect_kind_refused_on_hook_rejection():
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("e3"), DECL, effect=lambda a: None, now=T0,
                   authority_ref="m00-1", authority_check=lambda ref, digest: False)
    assert held.value.code == "OUTGATE:refused:authority_rejected"


def test_effect_kind_truthy_non_true_hook_rejects():
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("e4"), DECL, effect=lambda a: None, now=T0,
                   authority_ref="m00-1", authority_check=lambda ref, digest: "approved")
    assert held.value.code == "OUTGATE:refused:authority_rejected"


def test_effect_kind_dispatches_with_validated_authority():
    ledger, result = g.dispatch(act("e5"), DECL, effect=lambda a: "posted", now=T0,
                                authority_ref="m00-1", authority_check=OK)
    assert result == "posted"
    rec = ledger[-1]["record"]
    assert rec["verdict"] == "dispatched"
    assert rec["authority_checked"] is True and rec["authority_accepted"] is True
    assert rec["authority_ref"] == "m00-1"
    g.check_ledger(g.loads(g.dumps(ledger)))


def test_authority_hook_receives_exact_action_digest():
    seen = []
    action = act("e6", count=3)
    g.dispatch(action, DECL, effect=lambda a: None, now=T0,
               authority_ref="m00-1",
               authority_check=lambda ref, digest: seen.append((ref, digest)) or True)
    from app.runtime.guardrails._fields import payload_sha256
    expected = payload_sha256({k: v for k, v in action.items() if k != "id"})
    assert seen == [("m00-1", expected)]
    # content binding: a changed action yields a different digest
    other = dict(action, count=4)
    ledger2, _ = g.dispatch(other, DECL, effect=lambda a: None, now=T0,
                            authority_ref="m00-1", authority_check=OK)
    assert ledger2[-1]["record"]["action_digest"] != expected


def test_policy_deny_still_beats_authority():
    decl = {"tos": {"github": {"allowed_kinds": ["read"], "automation_allowed": True}},
            "rate_limits": {}, "consent": [], "recent_actions": []}
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("e7"), decl, effect=lambda a: None, now=T0,
                   authority_ref="m00-1", authority_check=OK)
    assert held.value.code == "OUTGATE:refused:denied"


def test_effect_kind_under_review_policy_needs_both():
    decl = dict(DECL, review_kinds=["post"])
    # validated authority + no review hook -> still refused on review
    with pytest.raises(GuardrailRefusal) as held:
        g.dispatch(act("e8"), decl, effect=lambda a: None, now=T0,
                   authority_ref="m00-1", authority_check=OK)
    assert held.value.code == "OUTGATE:refused:review_required"
    # validated authority + rejected review -> refused
    with pytest.raises(GuardrailRefusal):
        g.dispatch(act("e9"), decl, effect=lambda a: None, now=T0,
                   authority_ref="m00-1", authority_check=OK,
                   review_check=lambda a: False)
    # both satisfied -> dispatched:after_review
    ledger, result = g.dispatch(act("e10"), decl, effect=lambda a: "posted", now=T0,
                                authority_ref="m00-1", authority_check=OK,
                                review_check=lambda a: True)
    assert result == "posted"
    rec = ledger[-1]["record"]
    assert rec["verdict"] == "dispatched:after_review"
    assert rec["authority_accepted"] is True and rec["review_accepted"] is True


def test_read_kind_stays_policy_admission():
    ledger, result = g.dispatch(act("r1", kind="read"), DECL,
                                effect=lambda a: "read-ok", now=T0)
    assert result == "read-ok"
    rec = ledger[-1]["record"]
    assert rec["authority_checked"] is False
    assert rec["authority_ref"] is None


def test_ledger_rejects_forged_authority_acceptance():
    import hashlib, json
    ledger, _ = g.dispatch(act("e11"), DECL, effect=lambda a: None, now=T0,
                           authority_ref="m00-1", authority_check=OK)
    forged = [dict(e, record=dict(e["record"])) for e in ledger]
    rec = forged[-1]["record"]
    rec["authority_ref"] = None
    prev = forged[-1]["prev_hash"]
    payload = json.dumps({"seq": 0, "record": rec, "prev_hash": prev},
                         sort_keys=True, separators=(",", ":"))
    forged[-1]["record_hash"] = hashlib.sha256(payload.encode()).hexdigest()
    with pytest.raises(ValueError, match="OUTGATE:.*without a reference"):
        g.check_ledger(forged)
