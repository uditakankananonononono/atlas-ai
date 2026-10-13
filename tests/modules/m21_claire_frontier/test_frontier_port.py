from __future__ import annotations
import hashlib, json, tempfile
from datetime import datetime, timezone
from pathlib import Path
import pytest
from app.modules.m21_claire.frontier.representation_inventor import TabularObservation, RepresentationInventor

from app.modules.m21_claire.frontier.closure import GapClosureEngine, CompletionRejected
from app.modules.m21_claire.frontier.compiler import CapabilityCompiler
from app.modules.m21_claire.frontier.evidence import EvidenceLattice
from app.modules.m21_claire.frontier.research_router import ResearchQuestion, ResearchRouter, Mechanism, MechanismBridgeFinder, CounterexampleForge
from app.modules.m21_claire.frontier.skill_ecology import SkillEcology, SkillRejected
from app.modules.m21_claire.frontier.preference_model import PreferenceCodec
from app.modules.m21_claire.frontier.data_gate import TrainingDataGate
from app.modules.m21_claire.frontier.preference_model import InMemoryPreferenceStore
from app.modules.m21_claire.frontier._canon import canonical_json


def test_full_65_item_closure_backlog_and_proof_gates():
    engine=GapClosureEngine()
    assert engine.status()["total"]==65
    with pytest.raises(CompletionRejected):
        engine.record_progress(1,automated_test=True,automated_test_receipt_sha256="a"*64,integration_test="",integration_test_receipt_sha256="c"*64,observed_result="yes",reviewer_id="r",artifact_sha256="b"*64)
    with pytest.raises(CompletionRejected):
        engine.record_progress(19,automated_test=True,automated_test_receipt_sha256="a"*64,integration_test="passed",integration_test_receipt_sha256="c"*64,observed_result="yes",reviewer_id="r",artifact_sha256="b"*64)
    safe=engine.record_safe_substitute(19,substitute="single-account approval-gated posting",boundary="no fake accounts",test_evidence="policy test passed",reviewer_id="reviewer")
    assert safe["state"]=="substitute_proposed"  # prose alone does not close a row
    done=engine.record_progress(1,automated_test=True,automated_test_receipt_sha256="a"*64,integration_test="Atlas staging route returned 200",integration_test_receipt_sha256="c"*64,observed_result="known fixture output matched",reviewer_id="reviewer",artifact_sha256="b"*64)
    assert done["state"]=="attested_unverified"  # no receipt verifier: hashes are claims only
    assert engine.status()["counts"]["verified_complete"]==0
    seen=[]
    def verifier(kind,digest): seen.append((kind,digest)); return digest!="c"*64
    eng2=GapClosureEngine(receipt_verifier=verifier)
    kw=dict(automated_test=True,automated_test_receipt_sha256="a"*64,integration_test="ok",observed_result="matched",reviewer_id="r",artifact_sha256="b"*64)
    assert eng2.record_progress(1,integration_test_receipt_sha256="c"*64,**kw)["state"]=="attested_unverified"
    assert eng2.record_progress(2,integration_test_receipt_sha256="d"*64,**kw)["state"]=="verified_complete"
    assert {k for k,_ in seen}=={"automated_test_receipt_sha256","integration_test_receipt_sha256","artifact_sha256"}


def test_capability_compiler_builds_acyclic_gated_workflow():
    c=CapabilityCompiler()
    plan=c.compile("Research scientific hypotheses and verify them",user_constraints=["CPU-only"],budget={"max_steps":20})
    valid,errors=c.validate_graph(plan)
    assert valid and not errors
    assert plan["status"]=="compiled_not_executed"
    assert any(n["kind"]=="experiment" for n in plan["nodes"])
    assert all(n["acceptance_gate"] for n in plan["nodes"])
    assert c.compile("apply for competition and submit",budget={"max_steps":20})["status"]=="compiled_not_executed"


def test_evidence_lattice_dedupes_domains_and_exposes_conflict():
    now=datetime.now(timezone.utc)
    dt=now.isoformat()
    lattice=EvidenceLattice()
    supportive=[{"source_id":"a","url":"https://www.example.org/a","excerpt":"support","stance":"supports","authority":0.9,"published_at":dt},
                {"source_id":"b","url":"https://second.gov/a","excerpt":"support","stance":"supports","authority":0.9,"published_at":dt},
                {"source_id":"c","url":"https://www.example.org/b","excerpt":"duplicate domain","stance":"supports","authority":1.0,"published_at":dt}]
    result=lattice.adjudicate("claim",supportive,now=now)
    assert result["grade"]=="corroborated_in_supplied_evidence"
    assert result["independent_domain_count"]==2
    mixed=supportive+[ {"source_id":"d","url":"https://contrary.net/x","excerpt":"refutation","stance":"refutes","authority":0.9,"published_at":dt} ]
    assert lattice.adjudicate("claim",mixed,now=now)["grade"]=="contested"
    assert "not a truth oracle" in " ".join(result["limitations"])


def test_research_router_prioritizes_high_value_and_diversifies():
    qs=[ResearchQuestion("a","check","biology",uncertainty=.9,impact=.9,testability=.9,cost=1),
        ResearchQuestion("b","check","biology",uncertainty=.8,impact=.9,testability=.9,cost=1),
        ResearchQuestion("c","check","physics",uncertainty=.75,impact=.9,testability=.9,cost=1)]
    out=ResearchRouter().route(qs,3,diversity_weight=.5)
    assert len(out)==3 and out[0]["question_id"]=="a"
    assert len({r["domain"] for r in out[:2]})==2


def test_mechanism_bridge_requires_structural_overlap_and_falsifier():
    a=Mechanism("a","feedback regulator","biology",("input signal","state"),("negative feedback","state update"),("stable output",),("homeostasis","bounded response"),("oscillation",),("paper1",))
    b=Mechanism("b","controller","engineering",("input signal","state"),("negative feedback","state update"),("stable output",),("homeostasis","bounded response"),("oscillation",),("paper2",))
    results=MechanismBridgeFinder().bridge([a,b],min_similarity=.4)
    assert results and results[0]["state"]=="analogy_hypothesis_not_validated"
    assert "falsification" in results[0]["transfer_plan"]


def test_counterexample_forge_is_finite_and_marks_tests_unrun():
    tests=CounterexampleForge().forge("X causes Y",known_assumptions=["no confounding"],max_tests=5)
    assert len(tests)==5 and all(t["execution"]=="proposal_not_run" for t in tests)
    assert any(t["operator"]=="insert_confounder" for t in tests)


def sample_skill():
    return {"skill_id":"normalize-01","name":"normalize intent","version":"1.0",
      "operations":[{"op":"normalize_text","source":"text","target":"normalized"},{"op":"contains_any","source":"normalized","target":"urgent","tokens":["urgent","asap"]}],
      "tests":[{"input":{"text":"  URGENT   Please help "},"expected":{"normalized":"urgent please help","urgent":True}}]}


def test_skill_ecology_unit_and_untouched_holdout_gates():
    eco=SkillEcology(); spec=sample_skill()
    held=[{"input":{"text":"asap response"},"expected":{"normalized":"asap response","urgent":True}}]
    got=eco.register(spec,held)
    assert got["status"]=="validated_on_holdout"
    assert got["held_out"]["accuracy"]==1.0
    composed=eco.compose(["normalize-01","normalize-01"],skill_id="composed-01",name="composition")
    assert len(composed["operations"])==4 and composed["status"]=="unvalidated_composition_proposal"


def test_skill_ecology_rejects_arbitrary_code_and_quarantines_failure():
    eco=SkillEcology(); spec=sample_skill()
    spec["operations"][0]["python"]="__import__('os').system('bad')"
    with pytest.raises(SkillRejected): eco.register(spec,[{"input":{"text":"a"},"expected":{}}])
    bad=sample_skill(); bad["operations"][1]["tokens"]=["never-match"]
    with pytest.raises(SkillRejected): eco.register(bad,[{"input":{"text":"asap response"},"expected":{"urgent":True}}])
    assert eco.quarantine


def test_preference_codec_learns_explicit_pairwise_taste_and_erases():
    store=InMemoryPreferenceStore()
    codec=PreferenceCodec(store)
    for _ in range(8): codec.compare("tenant-a","visual-style",{"minimalist":1,"bright":0},{"minimalist":0,"bright":1},"a")
    m=codec.get("tenant-a","visual-style")
    assert m["comparisons"]==8 and m["weights"]["minimalist"]>m["weights"]["bright"]
    assert codec.score("tenant-a","visual-style",{"minimalist":1})["score"]>0
    assert codec.erase("tenant-a","visual-style")==1
    assert codec.get("tenant-a","visual-style")["comparisons"]==0


def test_training_data_gate_rejects_missing_permissions_and_pii():
    gate=TrainingDataGate(seed="test-seed")
    assert not gate.add(text="data",source_url="https://example.org/1",source_group="a",license_name="MIT",permission_to_use=False,permitted_uses=["training"])
    assert not gate.add(text="contact a@b.com",source_url="https://example.org/2",source_group="b",license_name="MIT",permission_to_use=True,permitted_uses=["training"])
    assert gate.rejections[0]["reason"]=="explicit_permission_missing"
    assert gate.rejections[1]["reason"]=="possible_personal_data_requires_review"


def test_training_data_gate_keeps_groups_in_one_split_and_manifest():
    gate=TrainingDataGate(seed="fixed")
    for i in range(150):
        assert gate.add(text=f"Unique permitted data record {i}",source_url=f"https://example.org/data/{i}",source_group=f"group-{i}",license_name="MIT",permission_to_use=True,permitted_uses=["training"],purpose="training")
    report=gate.validate()
    assert report["valid"] and report["record_count"]==150
    assert set(x.split(":")[1] for x in report["counts"]) <= {"train","validation","confirmation"}
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError): gate.export(Path(tmp)/"train.jsonl")  # no export_root configured
        gate.export_root=Path(tmp).resolve()
        with pytest.raises(ValueError): gate.export(Path(tmp)/".."/"escape.jsonl")
        with pytest.raises(ValueError): gate.export("/etc/escape.jsonl")
        (Path(tmp)/"link.jsonl").symlink_to(Path(tmp)/"target.jsonl")
        with pytest.raises(ValueError): gate.export(Path(tmp)/"link.jsonl")
        manifest=gate.export(Path(tmp)/"train.jsonl")
        assert manifest["dataset_sha256"] and (Path(tmp)/"train.jsonl.manifest.json").exists()
        assert manifest["training_rows_exported"]>0


def test_representation_inventor_discovers_square_term_only_after_validation_then_confirmation():
    from app.modules.m21_claire.frontier.representation_inventor import RepresentationInventor, TabularObservation
    rows=[]
    groups={"train":range(-8,0),"validation":[-10,-9,9,10],"confirmation":[-12,-11,11,12]}
    for split,values in groups.items():
        for i,x in enumerate(values):
            rows.append(TabularObservation(f"{split}-{i}",split,{"x":float(x)},float(x*x),f"source-{split}-{i}"))
    result=RepresentationInventor().search(rows,min_validation_gain=.2,min_confirmation_gain=.2)
    assert result["status"]=="representation_retained"
    assert result["retained_representation"]["name"]=="square(x)"
    assert result["confirmation"]["used_for_selection"] is False
    assert result["confirmation"]["relative_gain"]>.9


def test_representation_inventor_rejects_cross_split_source_group_leakage():
    from app.modules.m21_claire.frontier.representation_inventor import RepresentationInventor, TabularObservation
    rows=[]
    values={"train":[1,2,3,4,5,6],"validation":[7,8,9],"confirmation":[10,11,12]}
    for split,seq in values.items():
        for i,x in enumerate(seq):
            group="same-source" if split!="train" and i==0 else f"{split}-{i}"
            rows.append(TabularObservation(f"{split}-{i}",split,{"x":float(x)},float(x),group))
    with pytest.raises(ValueError,match="source groups cross"):
        RepresentationInventor().search(rows)


def test_novelty_debt_does_not_claim_world_first_from_low_similarity():
    from app.modules.m21_claire.frontier.novelty_debt import NoveltyDebtLedger
    ledger=NoveltyDebtLedger()
    idea={"title":"Tiny local ecology simulator","problem":"students cannot test competing ecology theories","mechanism":"small agents compete for finite resources and reproduce under constraints"}
    result=ledger.assess(idea,[{"source_id":"paper-1","url":"https://example.org","title":"Forest remote sensing","abstract":"satellite images of tree cover"}])
    assert result["status"]=="idea_hypothesis_with_open_debt"
    assert result["debts"]["prior_art"]["status"]=="open"
    assert "do not call it novel" in result["permitted_claim"]
    paid=ledger.assess(idea,[{"source_id":"paper-1","url":"https://example.org","title":"Forest remote sensing","abstract":"satellite images of tree cover"}],
        prior_art_review={"reviewer_id":"independent","search_protocol":"database query list and date range","searched_sources":["Crossref","Semantic Scholar"]},
        mechanism_test={"preregistered":True,"baseline":"standard ABM","falsification_condition":"no transfer gain","result":"replicated on holdout"},
        execution_test={"artifact_ref":"sha256:prototype","independent_test_receipt":"receipt-1","result":"tests passed"})
    assert paid["status"]=="evidence_complete_for_review"


def test_frontier_cycle_joins_lanes_evidence_counterexamples_and_next_step():
    from app.modules.m21_claire.frontier.cycle import FrontierCycle
    report=FrontierCycle().run({"goal":"Research science, build a website prototype, analyze social trends and apply to competitions",
       "questions":[{"question_id":"q1","question":"which baseline is strongest?","domain":"software","uncertainty":.8,"impact":.9,"testability":.9,"transfer_potential":.4,"cost":1,"risk":.05}],
       "claims":[{"claim":"X improves Y","evidence":[]}],
       "hypotheses":[{"hypothesis_id":"h1","hypothesis":"X causes Y","assumptions":["no confounding"],"domain":"biology","max_tests":3}],
       "ideas":[{"title":"New local prototype","problem":"workflow gap","mechanism":"structured transformations"}],
       "prior_art":[]})
    assert report["status"]=="analysis_package_ready_not_executed"
    assert report["external_actions_executed"]==0
    assert report["workflow"]["template"]=="multi_lane"
    assert report["workflow_valid"]
    assert report["claim_evaluations"][0]["grade"]=="insufficient_evidence"
    assert len(report["counterexample_designs"][0]["tests"])==3
    assert report["cycle_sha256"]


def test_capability_compiler_keeps_multiple_relevant_lanes_and_gates_external_action():
    plan=CapabilityCompiler().compile("Research a science idea, build a website, publish content and apply to competitions")
    valid,errors=CapabilityCompiler().validate_graph(plan)
    assert valid,errors
    assert len(plan["selected_templates"])>=3
    gate=next(n for n in plan["nodes"] if n["node_id"]=="exact_payload_approval_gate")
    assert gate["side_effect_class"]=="approval_required_no_action_here"


def test_evaluation_dimension_inventor_only_proposes_after_independent_confirmatory_gain():
    from app.modules.m21_claire.frontier.evaluator_inventor import EvaluationDimensionInventor
    from app.modules.m21_claire.frontier.representation_inventor import TabularObservation
    rows=[]
    for split,values in {"train":range(-8,0),"validation":[-10,-9,9,10],"confirmation":[-12,-11,11,12]}.items():
        for i,x in enumerate(values):
            rows.append(TabularObservation(f"{split}-{i}",split,{"retry_count":float(x)},1.0 if abs(x)>=5 else 0.0,f"episode-{split}-{i}"))
    result=EvaluationDimensionInventor().invent(rows,min_validation_gain=.1,min_confirmation_gain=.1)
    assert result["status"]=="candidate_dimension_created_for_shadow_evaluation"
    assert result["self_awarded_score"] is False
    assert result["evidence"]["confirmation_was_not_used_for_selection"] is True
    assert any("shadow mode" in x for x in result["promotion_gates"])


def test_evaluation_dimension_inventor_rejects_non_failure_target():
    from app.modules.m21_claire.frontier.evaluator_inventor import EvaluationDimensionInventor
    from app.modules.m21_claire.frontier.representation_inventor import TabularObservation
    rows=[]
    for split,values in {"train":range(6),"validation":range(6,9),"confirmation":range(9,12)}.items():
        for i,x in enumerate(values):
            rows.append(TabularObservation(f"{split}-{i}",split,{"x":float(x)},float(x),f"g-{split}-{i}"))
    with pytest.raises(ValueError,match="failure label/rate"):
        EvaluationDimensionInventor().invent(rows)


def test_skill_ecology_rejects_empty_expected_outputs_that_would_fake_passes():
    eco=SkillEcology(); spec=sample_skill(); spec["tests"]=[{"input":{"text":"anything"},"expected":{}}]
    with pytest.raises(SkillRejected,match="non-empty expected"):
        eco.register(spec,[{"input":{"text":"x"},"expected":{"urgent":False}}])



# ---- auditor-driven regressions -------------------------------------------------

def test_preference_dimensions_sharing_80_char_prefix_are_not_aliased():
    codec=PreferenceCodec(InMemoryPreferenceStore())
    a="x"*80+"A"; b="x"*80+"B"
    with pytest.raises(ValueError):
        codec.compare("t",a,{"f":1},{"f":0},"a")
    with pytest.raises(ValueError):
        codec.get("t",b)
    codec.compare("t","x"*80,{"f":1},{"f":0},"a")
    assert codec.get("t","x"*80)["comparisons"]==1


def test_representation_leakage_signature_ignores_target_label():
    obs=[]
    for i in range(8): obs.append(TabularObservation(record_id=f"t{i}",split="train",features={"a":float(i)},target=float(i)*2,source_group=f"g{i}"))
    for i in range(3): obs.append(TabularObservation(record_id=f"v{i}",split="validation",features={"a":float(100+i)},target=1.0,source_group=f"gv{i}"))
    for i in range(3): obs.append(TabularObservation(record_id=f"c{i}",split="confirmation",features={"a":float(200+i)},target=1.0,source_group=f"gc{i}"))
    obs[8]=TabularObservation(record_id="v0",split="validation",features={"a":0.0},target=999.0,source_group="gv0")  # same input as train t0, new label
    with pytest.raises(ValueError):
        RepresentationInventor().search(obs)


def test_evidence_lattice_same_domain_equal_refutation_is_not_dropped():
    lat=EvidenceLattice(); now=datetime(2026,1,1,tzinfo=timezone.utc)
    def ev(sid,url,stance): return {"source_id":sid,"url":url,"stance":stance,"excerpt":"text "+sid,"authority":1.0,"published_at":"2026-01-01T00:00:00Z"}
    for order in (0,1):
        items=[ev("s1","https://a.example.com/1","supports"),ev("s2","https://a.example.com/2","refutes"),
               ev("s3","https://b.example.org/1","supports"),ev("s4","https://c.example.net/1","supports")]
        if order: items.reverse()
        out=lat.adjudicate("claim",items,now=now)
        assert out["grade"]!="corroborated_in_supplied_evidence"
        assert out["grade"]=="contested"
        assert any(e.get("intra_domain_conflict") for e in out["evidence"])


def test_preseeded_verified_complete_rows_are_demoted_without_verifier():
    rows=[{"requirement_id":1,"title":"t","previous_status":"❌","state":"verified_complete","current_boundary":""}]
    eng=GapClosureEngine(rows)
    assert eng.status()["counts"]["verified_complete"]==0
    assert eng.rows[1]["state"]=="attested_unverified"
    rows2=[{"requirement_id":1,"title":"t","previous_status":"❌","state":"verified_complete","current_boundary":"",
            "acceptance_evidence":[{"automated_test_receipt_sha256":"a"*64,"integration_test_receipt_sha256":"c"*64,"artifact_sha256":"b"*64}]}]
    assert GapClosureEngine(rows2,receipt_verifier=lambda k,d:True).rows[1]["state"]=="verified_complete"
    assert GapClosureEngine(rows2,receipt_verifier=lambda k,d:False).rows[1]["state"]=="attested_unverified"
    rows3=[{"requirement_id":1,"title":"t","previous_status":"❌","state":"verified_complete","current_boundary":""}]
    assert GapClosureEngine(rows3,receipt_verifier=lambda k,d:True).rows[1]["state"]=="attested_unverified"  # no evidence to verify


def test_skill_holdout_must_not_reuse_authored_test_inputs():
    eco=SkillEcology(); spec=sample_skill()
    with pytest.raises(SkillRejected):
        eco.register(spec,list(spec["tests"]))
    relabeled=[{"input":spec["tests"][0]["input"],"expected":{"urgent":True}}]
    with pytest.raises(SkillRejected):
        eco.register(spec,relabeled)
    assert eco.quarantine


def test_representation_vocabulary_comes_from_train_only():
    obs=[]
    for i in range(8): obs.append(TabularObservation(record_id=f"t{i}",split="train",features={"a":float(i)},target=float(i),source_group=f"g{i}"))
    for i in range(3): obs.append(TabularObservation(record_id=f"v{i}",split="validation",features={"a":float(50+i),"leak":1.0},target=1.0,source_group=f"gv{i}"))
    for i in range(3): obs.append(TabularObservation(record_id=f"c{i}",split="confirmation",features={"a":float(90+i)},target=1.0,source_group=f"gc{i}"))
    with pytest.raises(ValueError, match="absent from train"):
        RepresentationInventor().search(obs)


def test_safe_substitute_needs_verified_receipt_not_prose():
    eng=GapClosureEngine(receipt_verifier=lambda k,d: d=="e"*64)
    kw=dict(substitute="s",boundary="b",test_evidence="all tests passed, trust me",reviewer_id="r")
    assert eng.record_safe_substitute(19,**kw)["state"]=="substitute_proposed"
    assert eng.record_safe_substitute(19,test_receipt_sha256="f"*64,**kw)["state"]=="substitute_proposed"
    assert eng.record_safe_substitute(19,test_receipt_sha256="e"*64,**kw)["state"]=="safe_substitute"
    assert GapClosureEngine().record_safe_substitute(19,test_receipt_sha256="e"*64,**kw)["state"]=="substitute_proposed"


def test_canonical_json_rejects_non_finite():
    from app.modules.m21_claire.frontier._canon import canonical_json
    for bad in (float("nan"),float("inf"),{"x":float("-inf")}):
        with pytest.raises(ValueError): canonical_json(bad)


def test_evidence_lattice_is_order_independent_with_mixed_stances_in_one_domain():
    import itertools
    lat=EvidenceLattice(); now=datetime(2026,1,1,tzinfo=timezone.utc)
    def item(i,stance,w): return {"source_id":i,"url":"https://a.example.org/"+i,"excerpt":i,"stance":stance,"authority":w,"published_at":"2026-01-01T00:00:00+00:00"}
    for es in ([item("s","supports",1),item("r","refutes",1)],
               [item("n","neutral",1),item("s","supports",.8),item("r","refutes",.7)]):
        grades={lat.adjudicate("x",list(p),now=now)["grade"] for p in itertools.permutations(es)}
        assert grades=={"contested"}
    # neutral never hides a lone supporting item in the same domain
    out=lat.adjudicate("x",[item("n","neutral",1),item("s","supports",.8)],now=now)
    assert out["score"]["support"]>0


def test_export_refuses_symlinked_manifest_dataset_and_directory(tmp_path):
    (tmp_path/"root").mkdir()
    gate=TrainingDataGate(seed="fixed",export_root=tmp_path/"root")
    for i in range(150):
        gate.add(text=f"Unique permitted data record {i}",source_url=f"https://example.org/data/{i}",source_group=f"group-{i}",license_name="MIT",permission_to_use=True,permitted_uses=["training"],purpose="training")
    outside=tmp_path/"outside.txt"; outside.write_text("original")
    (tmp_path/"root"/"train.jsonl.manifest.json").symlink_to(outside)
    with pytest.raises(ValueError): gate.export("train.jsonl")
    assert outside.read_text()=="original"
    (tmp_path/"root"/"train.jsonl.manifest.json").unlink()
    (tmp_path/"root"/"d2.jsonl").symlink_to(outside)
    with pytest.raises(ValueError): gate.export("d2.jsonl")
    assert outside.read_text()=="original"
    outdir=tmp_path/"outdir"; outdir.mkdir()
    (tmp_path/"root"/"sub").symlink_to(outdir)
    with pytest.raises(ValueError): gate.export("sub/x.jsonl")
    assert list(outdir.iterdir())==[]
    m=gate.export("ok/train.jsonl")
    assert (tmp_path/"root"/"ok"/"train.jsonl.manifest.json").exists() and m["dataset_sha256"]
    import hashlib
    assert hashlib.sha256((tmp_path/"root"/"ok"/"train.jsonl").read_bytes()).hexdigest()==m["dataset_sha256"]


def test_imported_safe_substitute_rows_and_bad_digests_are_revalidated():
    rec={"test_receipt_sha256":"e"*64,"substitute":"s","boundary":"b","test_evidence":"x","reviewer_id":"r"}
    rows=lambda: [{"requirement_id":1,"state":"safe_substitute","safe_substitute_record":dict(rec)},
                  {"requirement_id":2,"state":"verified_complete","acceptance_evidence":[{"automated_test_receipt_sha256":"zz","integration_test_receipt_sha256":"c"*64,"artifact_sha256":"b"*64}]}]
    e=GapClosureEngine(rows())
    assert e.rows[1]["state"]=="substitute_proposed" and e.rows[2]["state"]=="attested_unverified"
    e=GapClosureEngine(rows(),receipt_verifier=lambda k,d:True)
    assert e.rows[1]["state"]=="safe_substitute"      # verified digest kept
    assert e.rows[2]["state"]=="attested_unverified"  # malformed digest never trusted
    e=GapClosureEngine(rows(),receipt_verifier=lambda k,d:False)
    assert e.rows[1]["state"]=="substitute_proposed"


def test_export_root_swapped_for_symlink_or_other_dir_after_configuration_is_refused(tmp_path):
    import os, shutil
    root=tmp_path/"root"; root.mkdir(); outdir=tmp_path/"outdir"; outdir.mkdir()
    gate=TrainingDataGate(seed="fixed",export_root=root)
    for i in range(150):
        gate.add(text=f"Unique permitted data record {i}",source_url=f"https://example.org/data/{i}",source_group=f"group-{i}",license_name="MIT",permission_to_use=True,permitted_uses=["training"],purpose="training")
    keep=tmp_path/"root-original"; root.rename(keep)  # keep original alive so its inode cannot be reused
    root.symlink_to(outdir)
    with pytest.raises(ValueError): gate.export("train.jsonl")
    assert list(outdir.iterdir())==[]
    root.unlink(); root.mkdir()          # a different directory at the same path
    with pytest.raises(ValueError, match="identity"): gate.export("train.jsonl")
    assert list(root.iterdir())==[]
    with pytest.raises(FileNotFoundError): TrainingDataGate(export_root=tmp_path/"missing")
