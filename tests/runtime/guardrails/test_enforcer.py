"""GuardrailEnforcer facade tests (groups 134-142 integrated).

Pins the single choke point: every guardrail fires through the enforcer;
refusals persist in the gate ledgers (a refused attempt is durable evidence);
the audit digest counts records and refusals per gate; state round-trips
through dumps/loads with full chain verification; hooks fail closed.
"""
import hashlib

import pytest

from app.runtime.guardrails.enforcer import GuardrailEnforcer
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T08:00:00Z"
T1 = "2026-10-12T09:00:00Z"

DECL = {
    "tos": {"github": {"allowed_kinds": ["read"], "automation_allowed": True}},
    "rate_limits": {"github": {"read": {"max": 1, "window_seconds": 60}}},
    "consent": [], "recent_actions": [],
}
SILICO = {"id": "w1", "text": "compute k-mer statistics",
          "domain_terms": ["crispr"], "execution_mode": "computational"}
ACTION = {"action_id": "sub-1", "category": "submission",
          "summary": "submit the reviewed form", "payload": {"form": "v1"}}
REPORT = "| Claim | Status |\n|---|---|\n| Gate exists | VERIFIED |\n"


def test_all_gates_fire_through_one_surface():
    e = GuardrailEnforcer(approval_check=lambda ref, digest: ref == "IRB-1",
                          review_check=lambda a: True,
                          authority_check=lambda ref, digest: True)
    # 134+135
    assert e.run_bio_work(lambda i: "bio-ran", SILICO, now=T0) == "bio-ran"
    # 136
    assert e.dispatch_outbound({"id": "o1", "platform": "github", "kind": "read",
                                "at": 100, "count": 1}, DECL,
                               effect=lambda a: "sent", now=T0) == "sent"
    # 137
    e.open_review(ACTION, review_id="R1", reviewer="udita", now=T0)
    e.record_decision(review_id="R1", decision="approved", reviewer="udita",
                      rationale="exact draft reviewed", now=T0, authority_ref="m00-1")
    permit = e.issue_permit(ACTION, review_id="R1", now=T0)
    assert e.execute_reviewed(ACTION, effect=lambda a: "submitted", now=T1,
                              permit_id=permit["permit_id"]) == "submitted"
    # 138
    assert e.emit_text("e1", "Atlas is software with bounded mechanisms.",
                       channel="ui", now=T0)["verdict"] == "emitted"
    # 139
    e.register_account("github", "uditakankananonononono", registered_by="udita", now=T0)
    e.verify_account("github", "uditakankananonononono", verified_by="udita", now=T0,
                     authority_ref="m00-1")
    assert e.call_service("c1", "github", "uditakankananonononono",
                          effect=lambda: "api", now=T0) == "api"
    # 140
    digest = hashlib.sha256(b"run-output").hexdigest()
    e.register_dataset("proj-1", "ds-1", name="WikiText-103", now=T0)
    e.record_run("proj-1", "run-1", started_at=T0, ended_at=T1,
                 result_sha256=digest, summary="eval")
    e.record_result("proj-1", "res-1", finding="ppl 30.1", result_sha256=digest, now=T1)
    assert e.claim_research_done("proj-1", "cl-1", statement="conducted",
                                 now=T1)["verdict"] == "admitted"
    # 141
    for i in range(200):
        e.record_tool_use("proj-1", f"tool-{i:03d}", used_at=T0,
                          evidence_ref=f"ev-{i}", verified_by="builder")
    assert e.require_tool_bar("proj-1", now=T1)["verdict"] == "met"
    # 142
    assert e.emit_report("r1", REPORT, now=T1)["verdict"] == "emitted"
    audit = e.audit()
    assert all(v["refusals"] == 0 for v in audit.values())
    assert all(v["records"] > 0 for v in audit.values())


def test_refusals_persist_as_evidence_across_all_gates():
    e = GuardrailEnforcer()  # no hooks: everything fail-closed
    attempts = [
        lambda: e.run_bio_work(lambda i: None, dict(SILICO, text="how to culture it"), now=T0),
        lambda: e.dispatch_outbound({"id": "o1", "platform": "tiktok", "kind": "read",
                                     "at": 1, "count": 1}, DECL, effect=lambda a: None, now=T0),
        lambda: e.execute_reviewed(ACTION, effect=lambda a: None, now=T0),
        lambda: e.emit_text("e1", "I am sentient.", channel="ui", now=T0),
        lambda: e.call_service("c1", "github", "nobody", effect=lambda: None, now=T0),
        lambda: e.claim_research_done("proj-1", "cl-1", statement="done", now=T0),
        lambda: e.require_tool_bar("proj-1", now=T0),
        lambda: e.emit_report("r1", "no claims", now=T0),
    ]
    for attempt in attempts:
        with pytest.raises(GuardrailRefusal):
            attempt()
    audit = e.audit()
    assert [audit[name]["refusals"] for name in
            ("bio", "outbound", "review", "claims", "accounts", "research", "tools", "reports")] \
        == [1, 1, 1, 1, 1, 1, 1, 1]


def test_hooks_fail_closed_when_unset():
    e = GuardrailEnforcer()
    physical = {"id": "w9", "text": "bench run", "domain_terms": ["vaccine"],
                "execution_mode": "physical", "approval_ref": "IRB-1"}
    with pytest.raises(GuardrailRefusal) as held:
        e.run_bio_work(lambda i: None, physical, now=T0)
    assert held.value.code == "BIOGATE:refused:physical_approval_unverifiable"


def test_state_roundtrip_preserves_everything():
    e = GuardrailEnforcer()
    e.emit_text("e1", "bounded", channel="ui", now=T0)
    e.register_account("github", "owner", registered_by="u", now=T0)
    e.record_tool_use("p", "blast", used_at=T0, evidence_ref="ev", verified_by="b")
    try:
        e.emit_text("e2", "I am alive.", channel="ui", now=T0)
    except GuardrailRefusal:
        pass
    restored = GuardrailEnforcer.loads(e.dumps())
    assert restored.audit() == e.audit()
    # restored ledgers enforce identically
    with pytest.raises(GuardrailRefusal):
        restored.call_service("c1", "github", "owner", effect=lambda: None, now=T0)


def test_serialized_tamper_detected():
    e = GuardrailEnforcer()
    e.emit_text("e1", "bounded", channel="ui", now=T0)
    blob = e.dumps()
    import json
    raw = json.loads(blob)
    raw["claims"][0]["record"]["verdict"] = "refused:false_claim"
    with pytest.raises(ValueError, match="GRLEDGER:.*integrity"):
        GuardrailEnforcer.loads(json.dumps(raw))


def test_constructor_validation():
    with pytest.raises(ValueError, match="ENFORCER:"):
        GuardrailEnforcer(approval_check="not-callable")
    with pytest.raises(ValueError, match="ENFORCER:"):
        GuardrailEnforcer(ledgers={"bio": []})
    with pytest.raises(ValueError, match="ENFORCER:"):
        GuardrailEnforcer.loads("{}")


def test_persist_sink_write_ahead_and_ambiguous_reconciliation():
    """The parent's defect scenario: permit spent, effect raises after a real
    side effect. The sink must hold the spend BEFORE the effect ran, and the
    permit must never be silently re-usable."""
    events = []
    e = GuardrailEnforcer(persist=lambda name, led: events.append(
        (name, len(led), led[-1]["record"].get("kind"))),
                          authority_check=lambda ref, digest: True)
    e.open_review(ACTION, review_id="R1", reviewer="udita", now=T0)
    e.record_decision(review_id="R1", decision="approved", reviewer="udita",
                      rationale="ok", now=T0, authority_ref="m00-1")
    permit = e.issue_permit(ACTION, review_id="R1", now=T0)

    def flaky(action):
        events.append(("EFFECT", None, "ran-then-failed"))
        raise RuntimeError("ambiguous")

    with pytest.raises(RuntimeError):
        e.execute_reviewed(ACTION, effect=flaky, now=T1, permit_id=permit["permit_id"])
    # the spend was committed to the sink BEFORE the effect event
    spend_index = next(i for i, ev in enumerate(events)
                       if ev == ("review", 4, "permit_spent"))
    effect_index = events.index(("EFFECT", None, "ran-then-failed"))
    assert spend_index < effect_index
    # the permit is spent in the enforcer's state: replay refuses
    with pytest.raises(GuardrailRefusal) as held:
        e.execute_reviewed(ACTION, effect=lambda a: "replay", now=T1,
                           permit_id=permit["permit_id"])
    assert "permit already spent" in held.value.details["reasons"]


def test_persist_sink_covers_refusals_and_all_gates():
    commits = []
    e = GuardrailEnforcer(persist=lambda name, led: commits.append((name, len(led))))
    with pytest.raises(GuardrailRefusal):
        e.emit_text("e1", "I am sentient.", channel="ui", now=T0)
    with pytest.raises(GuardrailRefusal):
        e.execute_reviewed(ACTION, effect=lambda a: None, now=T0)
    e.register_account("github", "owner", registered_by="u", now=T0)
    e.record_tool_use("p", "blast", used_at=T0, evidence_ref="ev", verified_by="b")
    assert ("claims", 1) in commits
    assert ("review", 1) in commits
    assert ("accounts", 1) in commits
    assert ("tools", 1) in commits


def test_authority_check_threaded_to_decisions_and_verifications():
    e = GuardrailEnforcer(authority_check=lambda ref, digest: ref.startswith("m00-"))
    e.open_review(ACTION, review_id="R1", reviewer="udita", now=T0)
    with pytest.raises(ValueError, match="REVGATE:authority_rejected"):
        e.record_decision(review_id="R1", decision="approved", reviewer="udita",
                          rationale="ok", now=T0, authority_ref="bogus-1")
    e.record_decision(review_id="R1", decision="approved", reviewer="udita",
                      rationale="ok", now=T0, authority_ref="m00-1")
    rec = e.ledger("review")[-1]["record"]
    assert rec["authority_validated"] is True
    e.register_account("github", "owner", registered_by="u", now=T0)
    e.verify_account("github", "owner", verified_by="u", now=T0, authority_ref="m00-2")
    assert e.ledger("accounts")[-1]["record"]["authority_validated"] is True


def test_authority_ref_fails_closed_when_hook_unset():
    e = GuardrailEnforcer()
    e.open_review(ACTION, review_id="R1", reviewer="udita", now=T0)
    with pytest.raises(ValueError, match="REVGATE:authority_unverifiable"):
        e.record_decision(review_id="R1", decision="approved", reviewer="udita",
                          rationale="ok", now=T0, authority_ref="m00-1")


def test_persist_sink_failure_propagates():
    def bad_sink(name, led):
        raise OSError("disk full")
    e = GuardrailEnforcer(persist=bad_sink)
    with pytest.raises(OSError):
        e.register_account("github", "owner", registered_by="u", now=T0)


def test_loads_restores_hooks_and_sink():
    commits = []
    e = GuardrailEnforcer(authority_check=lambda ref, digest: True,
                          persist=lambda name, led: commits.append(name))
    e.register_account("github", "owner", registered_by="u", now=T0)
    restored = GuardrailEnforcer.loads(e.dumps(), authority_check=lambda ref, digest: True,
                                       persist=lambda name, led: commits.append(("r", name)))
    restored.verify_account("github", "owner", verified_by="u", now=T0,
                            authority_ref="m00-1")
    assert ("r", "accounts") in commits


def test_enforcer_authority_configured_end_to_end():
    e = GuardrailEnforcer(authority_check=lambda ref, digest: ref.startswith("m00-"))
    e.open_review(ACTION, review_id="R1", reviewer="udita", now=T0)
    with pytest.raises(ValueError, match="REVGATE:authority_required"):
        e.record_decision(review_id="R1", decision="approved", reviewer="udita",
                          rationale="ok", now=T0)  # hook configured, no ref
    e.record_decision(review_id="R1", decision="approved", reviewer="udita",
                      rationale="ok", now=T0, authority_ref="m00-9")
    permit = e.issue_permit(ACTION, review_id="R1", now=T0)
    assert e.execute_reviewed(ACTION, effect=lambda a: "done", now=T1,
                              permit_id=permit["permit_id"]) == "done"


def test_outbound_effect_kinds_require_authority_through_enforcer():
    post = {"id": "p1", "platform": "github", "kind": "post", "at": 100, "count": 1}
    decl = {"tos": {"github": {"allowed_kinds": ["read", "post"],
                               "automation_allowed": True}},
            "rate_limits": {"github": {"read": {"max": 10, "window_seconds": 60},
                                       "post": {"max": 10, "window_seconds": 60}}},
            "consent": [], "recent_actions": []}
    # RECORD-mode enforcer: person-facing effects refuse; reads still dispatch
    rec = GuardrailEnforcer()
    assert rec.dispatch_outbound({"id": "r1", "platform": "github", "kind": "read",
                                  "at": 100, "count": 1}, decl,
                                 effect=lambda a: "read-ok", now=T0) == "read-ok"
    with pytest.raises(GuardrailRefusal) as held:
        rec.dispatch_outbound(post, decl, effect=lambda a: None, now=T0)
    assert held.value.code == "OUTGATE:refused:authority_hook_required"
    # GATE-mode enforcer: needs authority_ref, then dispatches
    gate = GuardrailEnforcer(authority_check=lambda ref, digest: ref == "m00-1")
    with pytest.raises(GuardrailRefusal) as held:
        gate.dispatch_outbound(dict(post, id="p2"), decl, effect=lambda a: None, now=T0)
    assert held.value.code == "OUTGATE:refused:authority_required"
    assert gate.dispatch_outbound(dict(post, id="p3"), decl, effect=lambda a: "posted",
                                  now=T0, authority_ref="m00-1") == "posted"
