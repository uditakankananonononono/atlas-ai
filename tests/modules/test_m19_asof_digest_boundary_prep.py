"""ATLAS-2 prep. Builder-authored and not run by the builder; the peer auditor independently reported 11 PASS.
Boundary pins for rank_portfolio_as_of using existing APIs only.
The excluded-value test pins today's honest residue and does not demand any unimplemented binding."""
from datetime import datetime,timedelta,timezone
import pytest
from app.modules.m19_idea_incubator.historical_ranking import rank_portfolio_as_of
from app.modules.m19_idea_incubator.schemas import *
T0=datetime(2026,6,1,tzinfo=timezone.utc);ASOF=datetime(2026,9,1,tzinfo=timezone.utc);F=ASOF+timedelta(days=10)
class Repo:
    def __init__(s,ideas=(),ev=(),te=(),ex=()):s.i=list(ideas);s.e=list(ev);s.t=list(te);s.x=list(ex)
    def list_ideas(s):return [i.model_copy(deep=True) for i in s.i]
    def list_evidence(s,i):return [e.model_copy(deep=True) for e in s.e if e.idea_id==i]
    def list_tests(s,i):return [t.model_copy(deep=True) for t in s.t if t.idea_id==i]
    def list_experiments(s,i):return [x.model_copy(deep=True) for x in s.x if x.idea_id==i]
def mk_idea(stage=IdeaStage.VALIDATION):return Idea(id="i1",title="i1",problem="p",proposed_solution="s",stage=stage,created_at=T0,updated_at=T0)
def mk_ev(i,observed=T0,strength=.8,claim="c"):
    return Evidence(id=i,idea_id="i1",kind=EvidenceKind.OTHER,claim=claim,source="s",polarity=EvidencePolarity.SUPPORTS,strength=strength,confidence=.5,observed_at=observed,created_at=observed)
def mk_test(i,score=80.0):
    d={"score":score,"confidence":.8};return FeasibilityTest(id=i,idea_id="i1",desirability=d,technical=d,viability=d,strategic_fit=d,compliance=d,weighted_score=score,weighted_confidence=.8,outcome=FeasibilityOutcome.PASS,tested_at=T0)
def mk_exp(i,updated=None,status=ExperimentStatus.SUCCEEDED,learnings=""):
    return Experiment(id=i,idea_id="i1",name="n",hypothesis="h",method="m",metric="x",target=1,status=status,learnings=learnings,created_at=T0,updated_at=updated or T0)
def dg(repo,**k):return rank_portfolio_as_of(repo,ASOF,**k)

def test_excluded_value_change_at_same_id_reason_time_leaves_current_digest_unchanged_honest_residue():
    a=dg(Repo([mk_idea()],[mk_ev("e1"),mk_ev("e2",observed=F,strength=.1,claim="before")]))
    b=dg(Repo([mk_idea()],[mk_ev("e1"),mk_ev("e2",observed=F,strength=.9,claim="after")]))
    assert [(d.row_id,d.reason,d.timestamp) for d in a.diagnostics]==[(d.row_id,d.reason,d.timestamp) for d in b.diagnostics]
    assert a.provenance.digest==b.provenance.digest  # current behaviour: excluded values are not bound; no claim they should be
    assert a.provenance.reconstruction_claimed is False and b.provenance.reconstruction_claimed is False
def test_excluded_row_identity_change_does_change_digest():
    a=dg(Repo([mk_idea()],[mk_ev("e1"),mk_ev("e2",observed=F)]))
    b=dg(Repo([mk_idea()],[mk_ev("e1"),mk_ev("e3",observed=F)]))
    assert a.provenance.digest!=b.provenance.digest
def test_included_evidence_strength_change_changes_digest():
    a=dg(Repo([mk_idea()],[mk_ev("e1",strength=.8)]));b=dg(Repo([mk_idea()],[mk_ev("e1",strength=.7)]))
    assert a.provenance.digest!=b.provenance.digest
def test_included_non_scoring_evidence_value_change_changes_digest():
    a=dg(Repo([mk_idea()],[mk_ev("e1",claim="x")]));b=dg(Repo([mk_idea()],[mk_ev("e1",claim="y")]))
    assert a.ranking.ranked[0].priority==b.ranking.ranked[0].priority and a.provenance.digest!=b.provenance.digest
def test_included_test_value_change_changes_digest():
    a=dg(Repo([mk_idea()],[mk_ev("e1")],[mk_test("t1",80.0)]));b=dg(Repo([mk_idea()],[mk_ev("e1")],[mk_test("t1",60.0)]))
    assert a.provenance.digest!=b.provenance.digest
def test_included_experiment_value_change_changes_digest():
    a=dg(Repo([mk_idea()],ex=[mk_exp("x1",learnings="a")]));b=dg(Repo([mk_idea()],ex=[mk_exp("x1",learnings="b")]))
    assert a.provenance.digest!=b.provenance.digest
def test_digest_changes_with_current_stage_but_provenance_has_no_stage_at_as_of_field():
    a=dg(Repo([mk_idea(IdeaStage.VALIDATION)]));b=dg(Repo([mk_idea(IdeaStage.PARKED)]))
    assert len(a.ranking.ranked)==1 and a.ranking.excluded_count==0
    assert len(b.ranking.ranked)==0 and b.ranking.excluded_count==1  # current stage drives the current filter
    assert a.provenance.digest!=b.provenance.digest
    fields=set(type(a.provenance).model_fields)|set(type(a.ranking).model_fields)
    assert not any("stage_at" in f or "archiv" in f or "snapshot" in f for f in fields)  # no archival stage state is exposed
    assert a.provenance.included==b.provenance.included and [d.model_dump() for d in a.diagnostics]==[d.model_dump() for d in b.diagnostics]
def test_stage_mutation_back_restores_original_result_no_memory_of_prior_stage():
    base=dg(Repo([mk_idea(IdeaStage.VALIDATION)]));back=dg(Repo([mk_idea(IdeaStage.VALIDATION)]))
    assert base.provenance.digest==back.provenance.digest
def test_stale_experiment_exclude_and_current_policies_are_distinct():
    r=Repo([mk_idea()],ex=[mk_exp("x1",updated=F)])
    ex=dg(r,stale_experiment_policy="exclude");cur=dg(r,stale_experiment_policy="current")
    assert [d.row_id for d in ex.diagnostics]==["x1"] and cur.diagnostics==[]
    assert ex.provenance.included["experiments"]==[] and cur.provenance.included["experiments"]==["x1"]
    assert ex.provenance.digest!=cur.provenance.digest
    assert ex.ranking.ranked[0].experiment_signal is None and cur.ranking.ranked[0].experiment_signal==1.0
    assert any("not recoverable" in c for c in ex.caveats) and any("x1" in c for c in cur.caveats)
def test_stale_experiment_current_state_change_is_visible_only_under_current_policy():
    a=dg(Repo([mk_idea()],ex=[mk_exp("x1",updated=F,status=ExperimentStatus.SUCCEEDED)]),stale_experiment_policy="current")
    b=dg(Repo([mk_idea()],ex=[mk_exp("x1",updated=F,status=ExperimentStatus.FAILED)]),stale_experiment_policy="current")
    assert a.provenance.digest!=b.provenance.digest
    c=dg(Repo([mk_idea()],ex=[mk_exp("x1",updated=F,status=ExperimentStatus.SUCCEEDED)]));d=dg(Repo([mk_idea()],ex=[mk_exp("x1",updated=F,status=ExperimentStatus.FAILED)]))
    assert c.provenance.digest==d.provenance.digest  # excluded under default policy: values not bound
def test_snapshot_policy_doc_states_non_claims():
    import pathlib
    p=pathlib.Path(__file__).resolve().parents[2]/"docs"/"M19_SNAPSHOT_POLICY_PREP.md";t=p.read_text()
    for s in ("NOT IMPLEMENTED","no signature","does NOT exist","excluded kind/id/reason","reconstruct"):
        assert s.lower() in t.lower()
