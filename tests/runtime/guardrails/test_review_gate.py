"""Effect-category review gate tests (group 137). Stdlib only, hermetic.

Pins the enforcement: contact/application/submission/account actions never
execute without an approved hash-exact in-window single-use permit or a live
exact-scope preauthorization; refused executions are ledgered; one final
decision per review; permits cannot replay; tampered payloads cannot ride a
stale hash; preauthorizations expire and revoke; the chain detects edits.
"""
import pytest

from app.runtime.guardrails import review_gate as g
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T08:00:00Z"
T1 = "2026-10-12T09:00:00Z"
T2 = "2026-10-12T10:00:00Z"
ACTION = {"action_id": "sub-1", "category": "submission",
          "summary": "submit the prepared application form", "payload": {"form": "v1"}}


def approved_ledger(action=ACTION, rid="R1", valid_hours=24):
    ledger = []
    ledger = g.open_review(ledger, action, review_id=rid, reviewer="udita", now=T0,
                           valid_hours=valid_hours)
    ledger = g.record_decision(ledger, review_id=rid, decision="approved",
                               reviewer="udita", rationale="reviewed the exact draft", now=T1)
    ledger, permit = g.issue_permit(ledger, action, review_id=rid, now=T1)
    return ledger, permit


def test_unreviewed_action_never_executes():
    ran = []
    for category in g.CATEGORIES:
        action = {"action_id": f"a-{category}", "category": category,
                  "summary": "x", "payload": {}}
        with pytest.raises(GuardrailRefusal) as held:
            g.execute([], action, effect=ran.append, now=T0)
        assert held.value.code == "REVGATE:review_required"
        assert held.value.details["category"] == category
    assert ran == []


def test_refusal_is_ledgered():
    with pytest.raises(GuardrailRefusal) as held:
        g.execute([], ACTION, effect=lambda a: None, now=T0)
    ledger = held.value.ledger
    assert ledger[-1]["record"]["kind"] == "execution_refused"
    assert ledger[-1]["record"]["reason_code"] == "review_required"
    g.check_ledger(ledger)


def test_permit_executes_exactly_once():
    ledger, permit = approved_ledger()
    ledger, result = g.execute(ledger, ACTION, effect=lambda a: "submitted", now=T2,
                               permit_id=permit["permit_id"])
    assert result == "submitted"
    assert ledger[-1]["record"]["kind"] == "permit_spent"
    with pytest.raises(GuardrailRefusal) as held:
        g.execute(ledger, ACTION, effect=lambda a: "replay", now=T2,
                  permit_id=permit["permit_id"])
    assert "permit already spent" in held.value.details["reasons"]


def test_unknown_permit_refused():
    with pytest.raises(GuardrailRefusal) as held:
        g.execute([], ACTION, effect=lambda a: None, now=T0, permit_id="PERMIT-nope")
    assert held.value.code == "REVGATE:unknown_permit"


def test_tampered_payload_cannot_ride_permit():
    ledger, permit = approved_ledger()
    tampered = dict(ACTION, payload={"form": "v2-changed"})
    with pytest.raises(GuardrailRefusal) as held:
        g.execute(ledger, tampered, effect=lambda a: None, now=T2,
                  permit_id=permit["permit_id"])
    assert "action does not match the permit hashes" in held.value.details["reasons"]


def test_permit_window_expiry():
    ledger, permit = approved_ledger(valid_hours=1)
    with pytest.raises(GuardrailRefusal) as held:
        g.execute(ledger, ACTION, effect=lambda a: None, now="2026-10-13T09:00:01Z",
                  permit_id=permit["permit_id"])
    assert "review validity window has expired" in held.value.details["reasons"]


def test_rejected_review_gets_no_permit():
    ledger = g.open_review([], ACTION, review_id="R1", reviewer="udita", now=T0)
    ledger = g.record_decision(ledger, review_id="R1", decision="rejected",
                               reviewer="udita", rationale="wrong program", now=T1)
    with pytest.raises(ValueError, match="REVGATE:.*rejected"):
        g.issue_permit(ledger, ACTION, review_id="R1", now=T1)
    assert g.audit_state(ledger, "R1") == "rejected"


def test_one_final_decision_per_review():
    ledger = g.open_review([], ACTION, review_id="R1", reviewer="udita", now=T0)
    ledger = g.record_decision(ledger, review_id="R1", decision="approved",
                               reviewer="udita", rationale="ok", now=T1)
    with pytest.raises(ValueError, match="REVGATE:.*already has a decision"):
        g.record_decision(ledger, review_id="R1", decision="rejected",
                          reviewer="udita", rationale="changed my mind", now=T2)


def test_permit_not_issued_before_decision_or_for_other_action():
    ledger = g.open_review([], ACTION, review_id="R1", reviewer="udita", now=T0)
    with pytest.raises(ValueError, match="REVGATE:.*no decision"):
        g.issue_permit(ledger, ACTION, review_id="R1", now=T1)
    ledger = g.record_decision(ledger, review_id="R1", decision="approved",
                               reviewer="udita", rationale="ok", now=T1)
    other = dict(ACTION, action_id="sub-2")
    with pytest.raises(ValueError, match="REVGATE:.*does not match"):
        g.issue_permit(ledger, other, review_id="R1", now=T1)


def test_preauthorization_executes_and_ledgers_use():
    ledger = g.grant_preauthorization([], ACTION, preauth_id="PA1", granted_by="udita",
                                      now=T0, valid_hours=48, scope_note="weekly form resubmit")
    ledger, result = g.execute(ledger, ACTION, effect=lambda a: "ran", now=T1)
    assert result == "ran"
    assert ledger[-1]["record"] == {"kind": "preauthorization_used", "preauth_id": "PA1",
                                    "used_at": "2026-10-12T09:00:00+00:00",
                                    "action_id": "sub-1"}


def test_preauthorization_scope_is_exact():
    ledger = g.grant_preauthorization([], ACTION, preauth_id="PA1", granted_by="udita",
                                      now=T0, valid_hours=48, scope_note="exact form only")
    changed = dict(ACTION, payload={"form": "v2"})
    with pytest.raises(GuardrailRefusal) as held:
        g.execute(ledger, changed, effect=lambda a: None, now=T1)
    assert held.value.code == "REVGATE:review_required"
    other_category = dict(ACTION, category="contact")
    with pytest.raises(GuardrailRefusal):
        g.execute(ledger, other_category, effect=lambda a: None, now=T1)


def test_preauthorization_expiry_and_revocation():
    ledger = g.grant_preauthorization([], ACTION, preauth_id="PA1", granted_by="udita",
                                      now=T0, valid_hours=1, scope_note="short grant")
    with pytest.raises(GuardrailRefusal):
        g.execute(ledger, ACTION, effect=lambda a: None, now="2026-10-12T09:00:01Z")
    ledger = g.grant_preauthorization([], ACTION, preauth_id="PA2", granted_by="udita",
                                      now=T0, valid_hours=48, scope_note="revocable grant")
    ledger = g.revoke_preauthorization(ledger, preauth_id="PA2", revoked_by="udita",
                                       rationale="scope done", now=T1)
    with pytest.raises(GuardrailRefusal) as held:
        g.execute(ledger, ACTION, effect=lambda a: None, now=T1)
    assert held.value.code == "REVGATE:review_required"
    with pytest.raises(ValueError, match="REVGATE:.*already revoked"):
        g.revoke_preauthorization(ledger, preauth_id="PA2", revoked_by="udita",
                                  rationale="again", now=T2)


def test_contact_and_account_categories_permit_flow():
    for category in ("contact", "account"):
        action = {"action_id": f"a-{category}", "category": category,
                  "summary": "x", "payload": {"k": category}}
        ledger, permit = approved_ledger(action=action, rid=f"R-{category}")
        ledger, result = g.execute(ledger, action, effect=lambda a: category, now=T2,
                                   permit_id=permit["permit_id"])
        assert result == category


def test_bad_action_shapes():
    with pytest.raises(ValueError, match="REVGATE:bad_category"):
        g.execute([], dict(ACTION, category="payment"), effect=lambda a: None, now=T0)
    with pytest.raises(ValueError, match="REVGATE:unknown_fields:action"):
        g.execute([], dict(ACTION, extra=1), effect=lambda a: None, now=T0)
    with pytest.raises(ValueError, match="REVGATE:bad_type:payload"):
        g.execute([], dict(ACTION, payload="x"), effect=lambda a: None, now=T0)


def test_roundtrip_and_chain_tamper_detection():
    ledger, permit = approved_ledger()
    restored = g.loads(g.dumps(ledger))
    assert restored == ledger
    tampered = [dict(e, record=dict(e["record"])) for e in restored]
    tampered[1]["record"]["decision"] = "rejected"
    with pytest.raises(ValueError, match="GRLEDGER:.*integrity"):
        g.check_ledger(tampered)
    # order violation: deciding an unopened review inside a valid chain
    import hashlib, json
    record = {"kind": "review_decision", "review_id": "RX", "decision": "approved",
              "reviewer": "u", "rationale": "r", "decided_at": "2026-10-12T10:00:00+00:00"}
    seq = len(ledger)
    prev = ledger[-1]["record_hash"]
    payload = json.dumps({"seq": seq, "record": record, "prev_hash": prev},
                         sort_keys=True, separators=(",", ":"))
    forged = ledger + [{"seq": seq, "record": record, "prev_hash": prev,
                        "record_hash": hashlib.sha256(payload.encode()).hexdigest()}]
    with pytest.raises(ValueError, match="REVGATE:.*out of order"):
        g.check_ledger(forged)


def test_audit_state_progression():
    ledger = g.open_review([], ACTION, review_id="R1", reviewer="udita", now=T0)
    assert g.audit_state(ledger, "R1") == "open"
    ledger = g.record_decision(ledger, review_id="R1", decision="approved",
                               reviewer="udita", rationale="ok", now=T1)
    assert g.audit_state(ledger, "R1") == "approved"
    ledger, _ = g.issue_permit(ledger, ACTION, review_id="R1", now=T1)
    assert g.audit_state(ledger, "R1") == "permitted"
