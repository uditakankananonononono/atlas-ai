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
    e = GuardrailEnforcer(approval_check=lambda ref: ref == "IRB-1",
                          review_check=lambda a: True)
    # 134+135
    assert e.run_bio_work(lambda i: "bio-ran", SILICO, now=T0) == "bio-ran"
    # 136
    assert e.dispatch_outbound({"id": "o1", "platform": "github", "kind": "read",
                                "at": 100, "count": 1}, DECL,
                               effect=lambda a: "sent", now=T0) == "sent"
    # 137
    e.open_review(ACTION, review_id="R1", reviewer="udita", now=T0)
    e.record_decision(review_id="R1", decision="approved", reviewer="udita",
                      rationale="exact draft reviewed", now=T0)
    permit = e.issue_permit(ACTION, review_id="R1", now=T0)
    assert e.execute_reviewed(ACTION, effect=lambda a: "submitted", now=T1,
                              permit_id=permit["permit_id"]) == "submitted"
    # 138
    assert e.emit_text("e1", "Atlas is software with bounded mechanisms.",
                       channel="ui", now=T0)["verdict"] == "emitted"
    # 139
    e.register_account("github", "uditakankananonononono", registered_by="udita", now=T0)
    e.verify_account("github", "uditakankananonononono", verified_by="udita", now=T0)
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
