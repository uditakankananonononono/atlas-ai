from __future__ import annotations
import json
from pathlib import Path
import pytest
from app.modules.m21_claire.research_lab import (
    eval_expr, RepresentationInventor, FormalismMiner, CognitiveMultiverse,
    EpistemicCartographer, ExperimentalOntologyDiscovery, OpenEndedEvaluator,
    ClosedLoopResearchEngine, generate_concept_lattice,
)
from app.modules.m21_claire.source_connectors import parse_feed, SignalLedger, analyze_signals
from app.modules.m21_claire.approval_gate import ApprovalGate
from app.modules.m21_claire.research_workspace import ResearchWorkspaceStore


def data():
    train=[]; validation=[]; test=[]
    for x in range(1,16):
        case={"id":f"t{x}","input":{"x":x,"z":x%3},"expected":2*x}
        (train if x<=8 else validation if x<=11 else test).append(case)
    return train,validation,test


def test_safe_dsl_and_rejects_unknown_op():
    assert eval_expr({"op":"mul","args":[{"op":"field","name":"x"},{"op":"const","value":3}]},{"x":4})==12
    with pytest.raises(ValueError): eval_expr({"op":"python","code":"__import__('os')"},{})
    with pytest.raises(ValueError): eval_expr({"op":"field","name":"missing"},{})


def test_representation_search_has_heldout_report():
    train,validation,test=data()
    report=RepresentationInventor(max_candidates=50).search(train,validation,confirmation=test)
    assert report["candidate_count"] > 0
    assert report["best"] is not None
    assert report["baseline"]["total"]==len(validation)
    assert report["independent_confirmation"]["candidate_selection_used_confirmation"] is False
    assert report["confirmation_required"] is False


def test_formalism_miner_uses_test_split():
    train=[{"x":x,"target":3*x+2} for x in range(1,7)]
    validation=[{"x":x,"target":3*x+2} for x in range(7,9)]
    test=[{"x":x,"target":3*x+2} for x in range(9,12)]
    out=FormalismMiner().mine(train,validation,confirmation=test)
    assert out["formula_count"]>0
    assert out["top"][0]["confirmation_mae"] < 1e-6
    assert out["confirmation_required"] is False


def test_multiverse_scores_unique_contribution():
    train,validation,test=data(); out=CognitiveMultiverse().evaluate(train,validation,confirmation=test)
    assert out["population_size"]==18
    assert all("collective_value" in m for m in out["minds"])
    assert out["per_case_contributions"]
    assert out["independent_confirmation"]["selected_by_validation"]==out["minds"][0]["id"]


def test_epistemic_map_does_not_call_small_samples_reliable():
    c=EpistemicCartographer()
    for i in range(3): c.record(domain="biology",task_type="classification",complexity=.3,passed=True,predicted_confidence=.99)
    region=c.report()["regions"][0]
    assert region["status"]=="weak_evidence"
    assert c.assess(domain="unknown",task_type="unknown")["status"]=="unknown"


def test_intervention_is_copy_only_and_proposal_only():
    engine=ExperimentalOntologyDiscovery(); rows=[{"x":1},{"x":2},{"x":4}]
    proposals=engine.propose(rows,max_operators=6)
    assert proposals[0]["status"]=="proposal_only"
    base={"x":2}; changed=engine.apply_to_copy(base,{"kind":"scale_by","field":"x","factor":2})
    assert base=={"x":2} and changed=={"x":4.0}


def test_open_ended_dimensions_are_not_self_approved():
    items=OpenEndedEvaluator().propose_dimensions([{"failure_type":"distribution_shift","count":4}])
    assert items[0]["status"]=="proposed_not_validated"


def test_closed_loop_research_report_is_hashed():
    train,validation,test=data(); out=ClosedLoopResearchEngine(max_candidates=30).run(train=train,validation=validation,test=test,domain="synthetic")
    assert out["id"] and len(out["reproducibility_hash"])==64
    assert out["formalism_report"]["target_name"]=="target"
    assert out["split_counts"]=={"train":len(train),"validation":len(validation),"confirmation":len(test)}
    assert out["limitations"]


def test_concept_lattice_is_bounded_and_deduplicated():
    out=generate_concept_lattice(domains=["biology","math"],bottlenecks=["noise"],methods=["causal graph"],limit=1000)
    assert len(out)==6
    assert all(x["status"]=="unreviewed_idea" for x in out)


def test_public_feed_parse_and_dedupe_offline():
    xml=b'''<rss><channel><item><title>New spatial transcriptomics method</title><description>A method for biology</description><link>https://example.org/paper</link><guid>p1</guid></item></channel></rss>'''
    rows=parse_feed(xml,"https://example.org/rss")
    assert rows[0].source_domain=="example.org"
    ledger=SignalLedger(); assert ledger.add(rows)["new"]==1; assert ledger.add(rows)["duplicates"]==1
    trend=analyze_signals([{"title":"spatial transcriptomics method","summary":"spatial transcriptomics method biology","source_domain":"example.org","link":"https://example.org/paper","content_hash":"a"},
                           {"title":"spatial transcriptomics tools","summary":"spatial transcriptomics method biology","source_domain":"lab.org","link":"https://lab.org/paper","content_hash":"b"}])
    assert trend["document_count"]==2


def test_approval_exact_payload_and_single_use(tmp_path):
    g=ApprovalGate(tmp_path/"approval.db")
    proposal=g.propose("tenant","send_email",{"to":"person@example.org","body":"hello"})
    g.approve("tenant",proposal["id"],actor_id="owner",expected_payload_hash=proposal["payload_hash"])
    with pytest.raises(RuntimeError): g.consume("tenant",proposal["id"],action_type="send_email",payload={"to":"other@example.org","body":"hello"})
    permit=g.consume("tenant",proposal["id"],action_type="send_email",payload={"to":"person@example.org","body":"hello"})
    assert permit["permit"]=="issued_once_not_enforced_downstream"
    with pytest.raises(RuntimeError): g.consume("tenant",proposal["id"],action_type="send_email",payload={"to":"person@example.org","body":"hello"})


def test_workspace_persists_per_tenant_and_epistemic(tmp_path):
    store=ResearchWorkspaceStore(tmp_path/"workspace.db")
    assert store.add_signals("a",[{"content_hash":"abc","source_domain":"test","title":"signal"}])["new"]==1
    assert store.list_signals("b")==[]
    store.record_outcome("a",domain="biology",task_type="classify",complexity=.2,passed=True,predicted_confidence=.8,model_id="m1")
    assert store.epistemic_report("a")["records"]==1


def test_opportunity_rank_marks_unknown_eligibility_and_requires_verification():
    from app.modules.m21_claire.opportunity_engine import rank_opportunities, research_dossier, draft_evidence_post
    out=rank_opportunities([{"id":"p1","title":"Computational biology fellowship","domains":["biology"],
                            "official_url":"https://example.org/fellowship","full_funding":True,"source_reliability":.9}],
                           {"interests":["biology"],"prioritize_funding":True})
    item=out["items"][0]
    assert item["eligibility"]=="unknown_verify_before_applying"
    assert item["human_verification_required"] is True
    evidence=[{"title":"A paper about computational biology","link":"https://example.org/paper","summary":"A method tested on a public benchmark."}]
    dossier=research_dossier("computational biology",evidence)
    assert dossier["source_count"]==1
    draft=draft_evidence_post(topic="computational biology",audience="students",evidence=evidence)
    assert draft["publish_action"]=="not_performed"
    assert "https://example.org/paper" in draft["draft"]


def test_preference_interview_is_explicit_scoped_and_erasable(tmp_path):
    from app.modules.m21_claire.learning_interview import PreferenceInterviewStore
    store=PreferenceInterviewStore(tmp_path/"preferences.db")
    question=store.next_question("tenant","research","work_style",["theory-first","experiment-first","build-first"])
    assert len(question["answer_options"])==2
    store.answer("tenant","research","work_style","theory-first","experiment-first","experiment-first",importance=.8)
    assert store.profile("tenant")["items"]
    assert store.profile("other")["items"]==[]
    assert store.erase("tenant")["deleted_choices"]==1
    assert store.profile("tenant")["items"]==[]


def test_workspace_hash_and_research_run_persistence(tmp_path):
    store=ResearchWorkspaceStore(tmp_path/"workspace.db")
    run={"id":"run-1","finished_at":"2026-10-13T00:00:00+00:00","reproducibility_hash":"hash"}
    first=store.save_run("a",run)
    assert len(first["content_hash"])==64
    assert len(store.list_runs("a"))==1
    assert store.list_runs("b")==[]


def test_small_continuous_heldout_targets_use_regression_metric():
    from app.modules.m21_claire.research_lab import _score_predictions
    cases=[{"expected":float(v)} for v in (11,13,15,17,19,21)]
    score=_score_predictions(cases,[11.0,13.0,15.0,17.0,19.0,21.0])
    assert score["metric"]=="normalized_mae"
    assert score["score"]==1.0


def test_explicit_classification_mode_handles_numeric_class_ids():
    from app.modules.m21_claire.research_lab import _score_predictions
    cases=[{"expected":int(v)} for v in (11,13,15,17,19,21)]
    score=_score_predictions(cases,[11,13,15,17,19,21],task_type="classification")
    assert score["metric"]=="accuracy"
    assert score["score"]==1.0


def test_closed_loop_rejects_exact_split_leakage():
    train,validation,test=data()
    test[0]={**train[0]}
    with pytest.raises(ValueError,match="split leakage"):
        ClosedLoopResearchEngine(max_candidates=30).run(train=train,validation=validation,test=test,domain="synthetic",task_type="regression")


def test_feed_fetcher_rejects_private_ip_without_network():
    from app.modules.m21_claire.source_connectors import fetch_public_feed
    with pytest.raises(ValueError,match="non-public"):
        fetch_public_feed("https://127.0.0.1/rss")


def test_approval_review_returns_exact_stored_payload(tmp_path):
    gate=ApprovalGate(tmp_path/"review.db")
    proposal=gate.propose("tenant","submit_application",{"program":"x","answers":{"q1":"verified claim"}})
    review=gate.get("tenant",proposal["id"])
    assert review["payload"]=={"program":"x","answers":{"q1":"verified claim"}}
    assert review["payload_hash"]==proposal["payload_hash"]


def test_research_router_import_and_approval_auth_fail_closed():
    import importlib, sys, types
    try:
        importlib.import_module("app.auth.context")
    except ModuleNotFoundError:
        auth_pkg=types.ModuleType("app.auth"); auth_pkg.__path__=[]
        context_mod=types.ModuleType("app.auth.context")
        class TenantContext:
            def __init__(self, tenant_id="tenant", actor_id=None, roles=None, scopes=None, can_approve_actions=False):
                self.tenant_id=tenant_id; self.actor_id=actor_id; self.roles=roles or []; self.scopes=scopes or []
                self.can_approve_actions=can_approve_actions
        def require_tenant(): return TenantContext()
        context_mod.TenantContext=TenantContext; context_mod.require_tenant=require_tenant
        sys.modules.setdefault("app.auth",auth_pkg); sys.modules.setdefault("app.auth.context",context_mod)
    route_mod=importlib.import_module("app.modules.m21_claire.research_lab_routes")
    assert len(route_mod.router.routes)>=19
    from types import SimpleNamespace
    assert route_mod._trusted_approver(SimpleNamespace(actor_id="human-1",roles=["owner"],scopes=[]))=="human-1"
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as err:
        route_mod._trusted_approver(SimpleNamespace(actor_id="caller-chosen",roles=[],scopes=[]))
    assert err.value.status_code==403


def test_reproducibility_hash_is_stable_for_identical_inputs():
    train, validation, test = data()
    engine = ClosedLoopResearchEngine(max_candidates=30)
    first = engine.run(train=train, validation=validation, test=test, domain="synthetic", task_type="regression")
    second = engine.run(train=train, validation=validation, test=test, domain="synthetic", task_type="regression")
    assert first["reproducibility_hash"] == second["reproducibility_hash"]
    assert first["report_content_hash"] != first["reproducibility_hash"]
    assert len(first["report_content_hash"]) == 64


def test_closed_loop_skips_regression_formula_miner_for_classification():
    train, validation, test = [], [], []
    for x in range(18):
        case = {"id": f"class-{x}", "input": {"x": x, "z": x % 2}, "expected": x % 2}
        (train if x < 10 else validation if x < 14 else test).append(case)
    out = ClosedLoopResearchEngine(max_candidates=30).run(
        train=train, validation=validation, test=test, domain="synthetic-labels", task_type="classification"
    )
    assert out["task_type"] == "classification"
    assert out["formalism_report"]["skipped"] is True


def test_feed_entry_javascript_link_is_discarded():
    xml = b"<rss><channel><item><title>Unsafe example</title><description>Check link handling</description><link>javascript:alert(1)</link></item></channel></rss>"
    rows = parse_feed(xml, "https://example.org/rss")
    assert rows and rows[0].link == ""


def test_closed_loop_rejects_relabeled_and_reidentified_leakage():
    train,validation,test=data()
    leaked={**train[0],"expected":train[0]["expected"]+999}
    leaked.pop("id",None)
    test[0]=leaked
    with pytest.raises(ValueError,match="split leakage"):
        ClosedLoopResearchEngine(max_candidates=30).run(train=train,validation=validation,test=test,domain="synthetic",task_type="regression")
    train,validation,test=data()
    validation[0]={**train[0],"id":"brand-new-id"}
    with pytest.raises(ValueError,match="split leakage"):
        ClosedLoopResearchEngine(max_candidates=30).run(train=train,validation=validation,test=test,domain="synthetic",task_type="regression")
