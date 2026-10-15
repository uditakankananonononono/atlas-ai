import math, pytest
from app.modules.m12_ai_research_lab.models import *
from app.modules.m12_ai_research_lab.router import *

T = frozenset({TaskType.RESEARCH})
def M(i="a", q=.8, c=1.0, l=100, mx=1000, tasks=T):
    return ModelCapability(i, tasks, mx, c, l, q)
def R(**k):
    d = dict(task_type=TaskType.RESEARCH, output_tokens=100, budget_cents=10.0,
             latency_tolerance_ms=1000, tenant_id="t")
    d.update(k); return RouteRequest(**d)

BAD_MODELS = [
    dict(q=float("nan")), dict(q=float("inf")), dict(q=-.1), dict(q=1.5),
    dict(c=float("nan")), dict(c=-5.0), dict(c=float("inf")),
    dict(l=-1), dict(l=True), dict(mx=-1), dict(mx=1.5),
]
@pytest.mark.parametrize("kw", BAD_MODELS)
def test_invalid_model_profile_rejected(kw):
    with pytest.raises(ValueError):
        ModelRouter([M("a", **kw), M("b")]).route(R())

def test_duplicate_model_id_rejected():
    with pytest.raises(ValueError):
        ModelRouter([M("a"), M("a", q=.1)]).route(R())

BAD_REQS = [
    dict(budget_cents=float("nan")), dict(budget_cents=-1.0), dict(budget_cents=float("inf")),
    dict(output_tokens=-100), dict(output_tokens=True), dict(output_tokens=1.5),
    dict(latency_tolerance_ms=-1), dict(latency_tolerance_ms=float("nan")),
]
@pytest.mark.parametrize("kw", BAD_REQS)
def test_invalid_request_rejected(kw):
    with pytest.raises(ValueError):
        ModelRouter([M("a"), M("b")]).route(R(**kw))

def test_disabled_invalid_profile_still_rejected_but_valid_routing_unchanged():
    d = ModelRouter([M("a", q=.9), M("b", q=.5), M("c", q=.7, tasks=frozenset({TaskType.CODE}))]).route(R())
    assert d.primary.model_id == "a" and [f.model_id for f in d.fallbacks] == ["b"]

def test_zero_budget_zero_cost_still_routes():
    d = ModelRouter([M("a", c=0.0)]).route(R(budget_cents=0.0))
    assert d.primary.model_id == "a"

HUGE = 10**1000
@pytest.mark.parametrize("kw", [dict(output_tokens=HUGE), dict(budget_cents=HUGE), dict(latency_tolerance_ms=HUGE), dict(output_tokens=-HUGE)])
def test_unrepresentable_request_int_is_valueerror_not_overflow(kw):
    with pytest.raises(ValueError):
        ModelRouter([M("a")]).route(R(**kw))
@pytest.mark.parametrize("kw", [dict(q=HUGE), dict(c=HUGE), dict(l=HUGE), dict(mx=HUGE), dict(c=-HUGE)])
def test_unrepresentable_model_int_is_valueerror_not_overflow(kw):
    with pytest.raises(ValueError):
        ModelRouter([M("a", **kw)]).route(R())
def test_large_but_representable_int_still_routes():
    d = ModelRouter([M("a", mx=10**12)]).route(R(output_tokens=10**6, budget_cents=10**9))
    assert d.primary.model_id == "a"
