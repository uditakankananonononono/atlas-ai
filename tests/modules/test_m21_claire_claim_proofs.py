"""Claire claim path: proof-gated labels and the proof-gated action policy (direction 6 wiring)."""
from datetime import datetime, timezone

import pytest

from app.modules.m21_claire import (
    ActionPolicy, ActionRequest, Approval, CrossModulePlanner, ExecutionOrchestrator, PolicyViolation, ReviewMismatch,
    RiskLevel)
from app.modules.m21_claire import atomic_concepts_1_23 as ac
from app.modules.m21_claire.claim_proofs import (
    ClaimBlocked, ProofGatedActionPolicy, enforce_claim_labels, prove, require_verified)
from app.self_improve.proof_carrying import sha

NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)
TXT = "The program deadline is March 1."


def quote_claim(cid="c1", quote="deadline is March 1", driving=True, conf=0.5, **kw):
    ev = dict(source_text=TXT, source_sha256=sha(TXT.encode()), quote=quote)
    return dict(id=cid, claim="deadline", kind="sourced_quote", evidence=ev, confidence=conf, action_driving=driving, **kw)


def fact_claim(cid="c2", factors=(7, 13), driving=True):
    return dict(id=cid, claim="91 composite", kind="factorization", evidence=dict(n=91, factors=list(factors)), action_driving=driving)


# ---- label enforcement on the real tool_discovery output
def discovery_payload():
    d = {"sources": [{"id": "s1", "title": "Official", "url": "https://example.org/a", "official": True}],
         "products": [{"name": "P", "claims": [{"id": "k1", "text": "pricing is free", "source_id": "s1"},
                                               {"id": "k2", "text": "ships in May", "source_id": "nope"}]}]}
    return ac.tool_discovery(d)


def test_existing_helper_labels_a_claim_verified_from_source_id_existence_alone():
    out = discovery_payload()
    claims = out["products"][0]["claims"]
    assert [c["status"] for c in claims] == ["verified_from_cited_source", "unverified"]   # lookup, not proof


def test_enforce_downgrades_strong_label_without_proof_and_keeps_original_on_record():
    out = discovery_payload()
    fixed = enforce_claim_labels(out, {})
    c = fixed["products"][0]["claims"][0]
    assert c["status"] == "unverified"
    assert c["status_corrected"]["original_label"] == "verified_from_cited_source"
    assert c["proof"]["status"] == "VERIFICATION_IMPOSSIBLE"
    assert out["products"][0]["claims"][0]["status"] == "verified_from_cited_source"       # input not mutated


def test_enforce_keeps_label_only_with_verified_proof_and_confidence_does_not_matter():
    out = discovery_payload()
    ok = {"k1": {"status": "VERIFIED", "reason": "x", "confidence": 0.0}}
    assert enforce_claim_labels(out, ok)["products"][0]["claims"][0]["status"] == "verified_from_cited_source"
    for st in ("UNVERIFIED", "VERIFICATION_IMPOSSIBLE"):
        bad = {"k1": {"status": st, "reason": "x", "confidence": 1.0}}
        c = enforce_claim_labels(out, bad)["products"][0]["claims"][0]
        assert c["status"] == "unverified" and c["proof"]["confidence"] == 1.0


def test_enforce_handles_advice_style_top_level_claims_and_blocks_action_driving():
    payload = {"claims": [{"id": "a", "status": "supported", "action_driving": True},
                          {"claim_id": "b", "status": "Supported"}, {"id": "c", "status": "unsupported"}, "junk"]}
    r = enforce_claim_labels(payload, {})["claims"]
    assert [c["status"] for c in r[:3]] == ["unverified", "unverified", "unsupported"]
    assert r[0]["blocked"] is True and "blocked" not in r[1]
    assert r[2].get("status_corrected") is None


def test_prove_runs_checkers_and_flags_duplicate_ids():
    pr = prove([quote_claim("a"), quote_claim("b", quote="not there"), fact_claim("c"), dict(id="d", claim="x", kind="opinion")])
    assert [pr[k]["status"] for k in "abcd"] == ["VERIFIED", "UNVERIFIED", "VERIFIED", "VERIFICATION_IMPOSSIBLE"]
    dup = prove([quote_claim("a"), quote_claim("a")])
    assert dup["a"]["status"] == "UNVERIFIED" and "duplicate" in dup["a"]["reason"]


def test_require_verified_blocks_only_action_driving_unproven_claims():
    claims = [quote_claim("a"), quote_claim("b", quote="nope"), quote_claim("c", quote="nope", driving=False)]
    proofs = prove(claims)
    with pytest.raises(ClaimBlocked) as e:
        require_verified(claims, proofs)
    assert e.value.claim_id == "b" and e.value.status == "UNVERIFIED"
    require_verified([claims[0], claims[2]], proofs)
    with pytest.raises(ClaimBlocked) as e:
        require_verified([quote_claim("z")], {})
    assert e.value.status == "VERIFICATION_IMPOSSIBLE"


# ---- the consequential-action path
def send(claims, risk=RiskLevel.HIGH, action="send", **params):
    return ActionRequest("m05", action, {"to": "a@example.com", "claims": claims, **params}, "outreach", risk)


def test_policy_refuses_consequential_action_with_unproven_or_missing_claims():
    pol = ProofGatedActionPolicy()
    assert pol.require_allowed(send([quote_claim()])).requires_approval is True
    cases = [([quote_claim(quote="invented")], "unproven action-driving claim 'c1'"),
             ([quote_claim(driving=False)], "no action-driving claim"),
             ([], "no action-driving claim"),
             ([dict(id="o", claim="wise", kind="opinion", action_driving=True)], "VERIFICATION_IMPOSSIBLE"),
             ([quote_claim(), fact_claim(factors=(7, 11))], "'c2'"),
             ([quote_claim(conf=0.999, quote="invented")], "UNVERIFIED"),
             ("claims", "no claims list"), (["x"], "no claims list")]
    for claims, why in cases:
        with pytest.raises(PolicyViolation) as e:
            pol.require_allowed(send(claims))
        assert why in str(e.value), (claims, str(e.value))
    with pytest.raises(PolicyViolation) as e:
        pol.require_allowed(ActionRequest("m05", "send", {"to": "x"}, "p", RiskLevel.HIGH))
    assert "no claims list" in str(e.value)


def test_policy_leaves_non_consequential_and_hard_blocked_behaviour_unchanged():
    pol, base = ProofGatedActionPolicy(), ActionPolicy()
    low = ActionRequest("m04", "research", {"q": "x"}, "report")
    assert pol.evaluate(low) == base.evaluate(low) and pol.evaluate(low).requires_approval is False
    hb = ActionRequest("m05", "impersonate", {"claims": [quote_claim()]}, "p", RiskLevel.HIGH)
    assert pol.evaluate(hb) == base.evaluate(hb) and pol.evaluate(hb).allowed is False
    high_low_verb = ActionRequest("m04", "research", {"claims": []}, "p", RiskLevel.HIGH)
    with pytest.raises(PolicyViolation):
        pol.require_allowed(high_low_verb)                    # HIGH risk is consequential even with a harmless verb
    approval_verb_low_risk = ActionRequest("m04", "publish", {}, "p", RiskLevel.LOW)
    with pytest.raises(PolicyViolation):
        pol.require_allowed(approval_verb_low_risk)           # approval verbs are consequential at any risk


def test_orchestrator_with_proof_policy_executes_proven_action_and_refuses_unproven_at_prepare():
    log = []
    good = send([quote_claim()])
    plan = CrossModulePlanner().build("send", [good])
    orch = ExecutionOrchestrator(policy=ProofGatedActionPolicy(), clock=lambda: NOW)
    orch.register("m05.send", lambda p: log.append(p["to"]) or "sent")
    review = orch.prepare(plan)[0]
    orch.approve(plan, Approval("ok", review.digest, "user", NOW))
    orch.execute(plan)
    assert log == ["a@example.com"]
    bad = send([quote_claim(quote="invented")])
    plan2 = CrossModulePlanner().build("send", [bad])
    orch2 = ExecutionOrchestrator(policy=ProofGatedActionPolicy(), clock=lambda: NOW)
    orch2.register("m05.send", lambda p: log.append("SHOULD NOT RUN"))
    with pytest.raises(PolicyViolation):
        orch2.prepare(plan2)
    assert log == ["a@example.com"]


def test_evidence_swapped_after_review_is_caught_at_execution():
    log = []
    req = send([quote_claim()])
    plan = CrossModulePlanner().build("send", [req])
    orch = ExecutionOrchestrator(policy=ProofGatedActionPolicy(), clock=lambda: NOW)
    orch.register("m05.send", lambda p: log.append("ran"))
    review = orch.prepare(plan)[0]
    orch.approve(plan, Approval("ok", review.digest, "user", NOW))
    req.parameters["claims"][0]["evidence"]["quote"] = "invented"      # tamper after review
    with pytest.raises((PolicyViolation, ReviewMismatch)):
        orch.execute(plan)
    assert log == []


def test_plain_orchestrator_would_have_run_the_same_unproven_action():
    """Scope pin: the gate applies only where ProofGatedActionPolicy is injected."""
    log = []
    plan = CrossModulePlanner().build("send", [send([quote_claim(quote="invented")])])
    orch = ExecutionOrchestrator(clock=lambda: NOW)
    orch.register("m05.send", lambda p: log.append("ran"))
    review = orch.prepare(plan)[0]
    orch.approve(plan, Approval("ok", review.digest, "user", NOW))
    orch.execute(plan)
    assert log == ["ran"]
