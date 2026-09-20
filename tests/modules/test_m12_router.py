from app.modules.m12_ai_research_lab.models import *
from app.modules.m12_ai_research_lab.router import *
def test_router_obeys_budget_latency_and_capability():
    cat=[ModelCapability("best",frozenset({TaskType.RESEARCH}),8000,2,1000,.95),ModelCapability("fast",frozenset({TaskType.RESEARCH}),8000,.2,100,.8)]
    req=RouteRequest(TaskType.RESEARCH,1000,.5,200,"t1")
    assert ModelRouter(cat).route(req).primary.model_id=="fast"
def test_confidence_from_logprobs(): assert round(confidence_from_logprobs([0,-.693]),2)==.75
