"""Pins for M19 evidence-decayed portfolio ranking. Each pin names what it counts."""
import os
from datetime import datetime,timedelta,timezone
import pytest
from fastapi import Depends,FastAPI
from fastapi.testclient import TestClient
from app.modules.m19_idea_incubator.ledger import LedgerService
from app.modules.m19_idea_incubator.repository import MemoryIdeaRepository
from app.modules.m19_idea_incubator.ranking import rank_portfolio
from app.modules.m19_idea_incubator.schemas import *
NOW=datetime(2026,10,8,tzinfo=timezone.utc)
def svc():return LedgerService(MemoryIdeaRepository(),"a")
def idea(s,t):return s.create_idea(IdeaCreate(title=t,problem="p",proposed_solution="s")).id
def ev(s,i,pol="supports",strength=.8,conf=.5,days=0,kind="market_data"):
    return s.add_evidence(i,EvidenceCreate(kind=kind,claim="c",source="s",polarity=pol,strength=strength,confidence=conf,observed_at=NOW-timedelta(days=days)))
def feas(s,i,score=80):
    d={"score":score,"confidence":.8,"notes":""};return s.test_feasibility(i,FeasibilityTestCreate(desirability=d,technical=d,viability=d,strategic_fit=d,compliance=d))
def rank(s,**k):return rank_portfolio(s.repository,as_of=NOW,**k)

def test_hand_computed_priority_with_one_half_life_of_decay():
    s=svc();i=idea(s,"a");ev(s,i,days=90)
    r=rank(s,half_life_days=90).ranked[0]
    assert r.support==pytest.approx(.2,abs=1e-4) and r.net_evidence==pytest.approx(.2,abs=1e-4)
    assert r.priority==34.0
    assert r.missing_signals==["feasibility","experiments"] and r.signal_coverage==pytest.approx(1/3,abs=1e-4)

def test_recent_evidence_outranks_stale_equal_evidence():
    s=svc();old=idea(s,"old");new=idea(s,"new");ev(s,old,days=400);ev(s,new,days=1)
    assert [x.title for x in rank(s,half_life_days=60).ranked]==["new","old"]
    flat=rank(s,half_life_days=3650).ranked;assert abs(flat[0].priority-flat[1].priority)<1.5

def test_contradiction_lowers_priority_and_feasibility_raises_it():
    s=svc();a=idea(s,"a");b=idea(s,"b");ev(s,a);ev(s,b);ev(s,b,"contradicts",strength=.9,conf=.9)
    base={x.title:x.priority for x in rank(s).ranked};assert base["a"]>base["b"]
    feas(s,a,90);assert rank(s).ranked[0].priority>base["a"]

def test_overdue_open_experiment_penalises_and_changes_next_action():
    s=svc();i=idea(s,"x");ev(s,i,strength=.9,conf=.9);feas(s,i)
    before=rank(s).ranked[0]
    s.create_experiment(i,ExperimentCreate(name="n",hypothesis="h",method="m",metric="m",target=1,deadline=NOW-timedelta(days=2)))
    after=rank(s).ranked[0]
    assert after.overdue_experiments==1 and after.priority<before.priority and "overdue" in after.next_action
    assert before.next_action=="design an experiment: none exist"

def test_experiment_results_move_signal_and_cancelled_are_ignored():
    s=svc();i=idea(s,"x");ev(s,i)
    def run(status,val):
        e=s.create_experiment(i,ExperimentCreate(name="n",hypothesis="h",method="m",metric="m",target=1));s.update_experiment(i,e.id,ExperimentUpdate(status=ExperimentStatus.RUNNING))
        s.update_experiment(i,e.id,ExperimentUpdate(status=status,observed_value=val))
    run(ExperimentStatus.SUCCEEDED,2);assert rank(s).ranked[0].experiment_signal==1.0
    run(ExperimentStatus.FAILED,0);assert rank(s).ranked[0].experiment_signal==0.0
    e=s.create_experiment(i,ExperimentCreate(name="n",hypothesis="h",method="m",metric="m",target=1));s.update_experiment(i,e.id,ExperimentUpdate(status=ExperimentStatus.CANCELLED))
    assert rank(s).ranked[0].experiment_signal==0.0

def test_terminal_ideas_excluded_unless_requested_and_limit_applies():
    s=svc();a=idea(s,"a");b=idea(s,"b");idea(s,"c");s.decide(b,DecisionCreate(to_stage=IdeaStage.REJECTED,rationale="no"))
    r=rank(s);assert [x.title for x in r.ranked].count("b")==0 and r.excluded_count==1
    assert len(rank(s,include_terminal=True).ranked)==3 and len(rank(s,limit=1).ranked)==1
    assert [x.rank for x in rank(s,include_terminal=True).ranked]==[1,2,3]

@pytest.mark.parametrize("bad",[float("nan"),float("inf"),float("-inf"),-1,0,True,"90"])
def test_non_finite_or_invalid_half_life_raises_value_error(bad):
    s=svc();idea(s,"a")
    with pytest.raises(ValueError):rank_portfolio(s.repository,as_of=NOW,half_life_days=bad)

def test_naive_as_of_handled():
    s=svc();idea(s,"a");assert rank_portfolio(s.repository,as_of=datetime(2026,10,8)).ranked

def test_missing_feasibility_scores_zero_and_is_stated_not_neutral():
    s=svc();i=idea(s,"a");ev(s,i,strength=.9,conf=.9,days=0)
    r0=rank(s).ranked[0];assert r0.feasibility is None and any("scored 0, not neutral" in x for x in r0.reasons)
    feas(s,i,score=0);r1=rank(s).ranked[0]
    assert r1.feasibility==0.0 and r1.priority==r0.priority
    feas(s,i,score=100);assert rank(s).ranked[0].priority>r0.priority

def test_as_of_is_decay_anchor_future_evidence_has_age_zero():
    s=svc();i=idea(s,"a");ev(s,i,days=-30)
    r=rank(s,half_life_days=10).ranked[0];assert r.support==pytest.approx(.4,abs=1e-4)

needs_db=pytest.mark.skipif(not os.environ.get("ATLAS_DATABASE_URL","").startswith("sqlite:///"),reason="needs isolated ATLAS_DATABASE_URL")
@needs_db
def test_http_ranking_is_tenant_scoped_and_auth_required(monkeypatch,oidc_auth_headers):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH",raising=False);monkeypatch.setenv("ATLAS_ENV","production")
    from app.auth.context import require_tenant
    from app.modules.m19_idea_incubator.routes import router
    app=FastAPI();app.include_router(router,prefix="/api/v1",dependencies=[Depends(require_tenant)]);c=TestClient(app);U="/api/v1/idea-incubator/portfolio"
    assert c.get(U+"/ranking").status_code in (401,403)
    TA,TB="rank-tenant-a","rank-tenant-b"
    for t,title in ((TA,"A idea"),(TA,"A idea 2"),(TB,"B idea")):
        assert c.post(U+"/ideas",json={"title":title,"problem":"p","proposed_solution":"s"},headers=oidc_auth_headers(t)).status_code==201
    a=c.get(U+"/ranking",headers=oidc_auth_headers(TA)).json();b=c.get(U+"/ranking",headers=oidc_auth_headers(TB)).json()
    assert sorted(x["title"] for x in a["ranked"])==["A idea","A idea 2"] and [x["title"] for x in b["ranked"]]==["B idea"]
    assert c.get(U+"/ranking?half_life_days=0",headers=oidc_auth_headers(TA)).status_code==422
    assert len(c.get(U+"/ranking?limit=1",headers=oidc_auth_headers(TA)).json()["ranked"])==1
