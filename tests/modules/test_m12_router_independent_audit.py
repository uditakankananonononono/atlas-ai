import pytest
from app.modules.m12_ai_research_lab.models import ModelCapability, RouteRequest, TaskType
from app.modules.m12_ai_research_lab.router import ModelRouter,NoEligibleModel

def test_numeric_rejection_grid():
 for x in [True,False,None,'1',[],{},float('nan'),float('inf'),-float('inf'),-1,10**1000]:
  with pytest.raises(ValueError):ModelRouter._num(x,'audit',integer=True)
 for x in [True,False,None,'1',[],{},float('nan'),float('inf'),-1,10**1000]:
  with pytest.raises(ValueError):ModelRouter._num(x,'audit')
 for x in [0,1,2,10**10]:ModelRouter._num(x,'audit',integer=True)

def test_route_matches_independent_feasible_score_grid():
 task=TaskType.RESEARCH
 for budget in [0,1,10]:
  for tokens in [0,10,100]:
   for latency in [0,100,1000]:
    ms=[ModelCapability(str(i),frozenset({task}),limit,cost,delay,quality) for i,(limit,cost,delay,quality) in enumerate([(100,1.,100,.8),(1000,2.,10,.5),(100,0.,1000,1.)])]
    req=RouteRequest(tenant_id='audit',task_type=task,output_tokens=tokens,budget_cents=budget,latency_tolerance_ms=latency)
    feasible=[]
    for m in ms:
     charge=tokens*m.cents_per_1k_tokens/1000
     if tokens<=m.max_output_tokens and charge<=budget and m.p95_latency_ms<=latency:
      score=.62*m.quality+.23*min(1,latency/max(1,m.p95_latency_ms))+.15*max(0,1-charge/max(.01,budget));feasible.append((score,m.model_id))
    if feasible:assert ModelRouter(ms).route(req).primary.model_id==max(feasible)[1]
    else:
     with pytest.raises(NoEligibleModel):ModelRouter(ms).route(req)
