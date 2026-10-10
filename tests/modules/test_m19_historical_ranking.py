"""AUTHORED, NOT RUN. Pins for historical_ranking.py using an in-test read-only fake repository."""
from datetime import datetime,timedelta,timezone
import pytest
from app.modules.m19_idea_incubator.historical_ranking import rank_portfolio_as_of
from app.modules.m19_idea_incubator.ranking import rank_portfolio
from app.modules.m19_idea_incubator.schemas import *
T0=datetime(2026,6,1,tzinfo=timezone.utc);ASOF=datetime(2026,9,1,tzinfo=timezone.utc)
F=ASOF+timedelta(days=10)
class Repo:
    def __init__(s,ideas=(),ev=(),te=(),ex=()):s.i=list(ideas);s.e=list(ev);s.t=list(te);s.x=list(ex)
    def list_ideas(s):return list(s.i)
    def list_evidence(s,i):return [e for e in s.e if e.idea_id==i]
    def list_tests(s,i):return [t for t in s.t if t.idea_id==i]
    def list_experiments(s,i):return [x for x in s.x if x.idea_id==i]
def idea(i="i1",created=T0,stage=IdeaStage.VALIDATION):return Idea(id=i,title=i,problem="p",proposed_solution="s",stage=stage,created_at=created,updated_at=created)
def ev(i,idea_id="i1",observed=T0,created=None,pol=EvidencePolarity.SUPPORTS):
    return Evidence(id=i,idea_id=idea_id,kind=EvidenceKind.OTHER,claim="c",source="s",polarity=pol,strength=.8,confidence=.5,observed_at=observed,created_at=created or observed)
def mk_test(i,tested):
    d={"score":80,"confidence":.8};return FeasibilityTest(id=i,idea_id="i1",desirability=d,technical=d,viability=d,strategic_fit=d,compliance=d,weighted_score=80,weighted_confidence=.8,outcome=FeasibilityOutcome.PASS,tested_at=tested)
def exp(i,created=T0,updated=None,status=ExperimentStatus.SUCCEEDED):
    return Experiment(id=i,idea_id="i1",name="n",hypothesis="h",method="m",metric="x",target=1,status=status,created_at=created,updated_at=updated or created)

def test_as_of_required_and_must_be_timezone_aware():
    with pytest.raises(ValueError):rank_portfolio_as_of(Repo(),None)
    with pytest.raises(ValueError):rank_portfolio_as_of(Repo(),datetime(2026,9,1))
def test_bad_policy_rejected():
    with pytest.raises(ValueError):rank_portfolio_as_of(Repo(),ASOF,stale_experiment_policy="x")
def test_future_observed_evidence_excluded_and_diagnosed():
    h=rank_portfolio_as_of(Repo([idea()],[ev("e1"),ev("e2",observed=F)]),ASOF)
    assert [(d.row_id,d.reason) for d in h.diagnostics]==[("e2","evidence_observed_after_as_of")]
    assert h.provenance.included["evidence"]==["e1"]
def test_late_recorded_backdated_evidence_excluded():
    h=rank_portfolio_as_of(Repo([idea()],[ev("e1",observed=T0,created=F)]),ASOF)
    assert h.diagnostics[0].reason=="evidence_recorded_after_as_of" and h.ranking.ranked[0].support==0
def test_future_evidence_does_not_change_score_versus_clean_repo():
    a=rank_portfolio_as_of(Repo([idea()],[ev("e1")]),ASOF).ranking.ranked[0]
    b=rank_portfolio_as_of(Repo([idea()],[ev("e1"),ev("e2",observed=F)]),ASOF).ranking.ranked[0]
    assert (a.priority,a.support,a.net_evidence)==(b.priority,b.support,b.net_evidence)
def test_existing_ranking_still_gives_full_weight_to_future_evidence():
    r=Repo([idea()],[ev("e1",observed=F)]);assert rank_portfolio(r,as_of=ASOF).ranked[0].support==pytest.approx(.4)
    assert rank_portfolio_as_of(r,ASOF).ranking.ranked[0].support==0
def test_idea_created_after_as_of_excluded():
    h=rank_portfolio_as_of(Repo([idea("i1"),idea("i2",created=F)]),ASOF)
    assert [x.idea_id for x in h.ranking.ranked]==["i1"] and h.diagnostics[0].kind=="idea"
def test_future_test_excluded_so_feasibility_missing():
    h=rank_portfolio_as_of(Repo([idea()],[ev("e1")],[mk_test("t1",F)]),ASOF)
    assert "feasibility" in h.ranking.ranked[0].missing_signals and h.diagnostics[0].reason=="test_after_as_of"
def test_experiment_created_after_as_of_excluded():
    h=rank_portfolio_as_of(Repo([idea()],ex=[exp("x1",created=F)]),ASOF);assert h.diagnostics[0].reason=="experiment_created_after_as_of"
def test_experiment_updated_after_as_of_excluded_by_default_with_caveat():
    h=rank_portfolio_as_of(Repo([idea()],ex=[exp("x1",updated=F)]),ASOF)
    assert h.diagnostics[0].reason=="experiment_state_changed_after_as_of_unrecoverable"
    assert any("not recoverable" in c for c in h.caveats) and "experiments" in h.ranking.ranked[0].missing_signals
def test_current_policy_keeps_stale_experiment_and_flags_it():
    h=rank_portfolio_as_of(Repo([idea()],ex=[exp("x1",updated=F)]),ASOF,stale_experiment_policy="current")
    assert not h.diagnostics and any("x1" in c for c in h.caveats) and h.ranking.ranked[0].experiment_signal==1.0
def test_no_reconstruction_claim_in_provenance_and_caveats():
    h=rank_portfolio_as_of(Repo([idea()]),ASOF)
    assert h.provenance.reconstruction_claimed is False and "not a historical reconstruction" in h.provenance.note
    assert any("no historical reconstruction" in c for c in h.caveats)
def test_provenance_digest_deterministic_and_input_sensitive():
    r=Repo([idea()],[ev("e1")]);a=rank_portfolio_as_of(r,ASOF);b=rank_portfolio_as_of(r,ASOF)
    assert a.provenance.digest==b.provenance.digest and len(a.provenance.digest)==64
    assert rank_portfolio_as_of(r,ASOF,half_life_days=30).provenance.digest!=a.provenance.digest
    assert rank_portfolio_as_of(Repo([idea()],[ev("e1"),ev("e2",observed=F)]),ASOF).provenance.digest!=a.provenance.digest
def test_diagnostics_sorted_deterministically():
    h=rank_portfolio_as_of(Repo([idea()],[ev("e9",observed=F),ev("e2",observed=F)]),ASOF);assert [d.row_id for d in h.diagnostics]==["e2","e9"]
def test_equal_timestamp_row_is_included():
    assert not rank_portfolio_as_of(Repo([idea()],[ev("e1",observed=ASOF)]),ASOF).diagnostics
def test_naive_row_timestamps_treated_as_utc():
    h=rank_portfolio_as_of(Repo([idea()],[ev("e1",observed=datetime(2026,9,2))]),ASOF);assert h.diagnostics[0].row_id=="e1"
def test_terminal_stage_filter_is_current_stage_and_caveated():
    h=rank_portfolio_as_of(Repo([idea(stage=IdeaStage.PARKED)]),ASOF)
    assert h.ranking.excluded_count==1 and any("CURRENT idea stage" in c for c in h.caveats)
    assert len(rank_portfolio_as_of(Repo([idea(stage=IdeaStage.PARKED)]),ASOF,include_terminal=True).ranking.ranked)==1
def test_view_does_not_mutate_source_repository():
    r=Repo([idea()],[ev("e1",observed=F)]);rank_portfolio_as_of(r,ASOF);assert len(r.e)==1
def test_ranking_py_docstring_unchanged():
    import app.modules.m19_idea_incubator.ranking as m;assert "as_of is only the decay anchor" in m.__doc__

def test_digest_binds_scoring_values_not_only_ids():
    a=ev('e1');b=a.model_copy(update={'strength':.1})
    x=rank_portfolio_as_of(Repo([idea()],[a]),ASOF)
    y=rank_portfolio_as_of(Repo([idea()],[b]),ASOF)
    assert x.ranking.ranked[0].support!=y.ranking.ranked[0].support
    assert x.provenance.digest!=y.provenance.digest

@pytest.mark.parametrize('kwargs',[{'limit':0},{'limit':True},{'limit':1.5},{'include_terminal':1}])
def test_typed_policy_arguments(kwargs):
    with pytest.raises(ValueError):rank_portfolio_as_of(Repo([idea()]),ASOF,**kwargs)

def test_additive_http_binding_and_naive_time_rejection():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m19_idea_incubator.ranking_router import router,get_ranking_repository
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_ranking_repository]=lambda:Repo([idea()],[ev('future',observed=F)])
    with TestClient(app) as client:
        x=client.get('/portfolio/ranking/as-of',params={'as_of':ASOF.isoformat()})
        assert x.status_code==200 and x.json()['ranking']['ranked'][0]['support']==0
        assert client.get('/portfolio/ranking/as-of',params={'as_of':'2026-09-01T00:00:00'}).status_code==422
