from __future__ import annotations
from dataclasses import dataclass
from math import exp, isfinite
from .models import ModelCapability, RouteRequest

class NoEligibleModel(RuntimeError): pass

@dataclass(frozen=True)
class RouteDecision:
    primary: ModelCapability
    fallbacks: tuple[ModelCapability, ...]
    scores: dict[str, float]
    reasons: dict[str, list[str]]

def _positive_finite_latency(value) -> bool:
    return type(value) in (int,float) and 0 < value <= 2**63-1 and (type(value) is int or isfinite(value))

def _nonnegative_finite(value) -> bool:
    if type(value) not in (int,float) or value < 0:return False
    try:return isfinite(value)
    except OverflowError:return False

class ModelRouter:
    """Pluggable deterministic router. Replace score() with an ML policy without changing callers."""
    def __init__(self, catalog: list[ModelCapability]): self.catalog = catalog
    def score(self, m: ModelCapability, req: RouteRequest) -> tuple[float, list[str]]:
        reasons=[]
        if type(m.enabled) is not bool:return float("-inf"), ["invalid enabled flag"]
        if not m.enabled or req.task_type not in m.task_types: return float("-inf"), ["unsupported"]
        if req.required_model_ids and m.model_id not in req.required_model_ids: return float("-inf"), ["not allow-listed"]
        if type(req.output_tokens) is not int or req.output_tokens<=0 or type(m.max_output_tokens) is not int or m.max_output_tokens<=0:return float("-inf"), ["invalid output token limits"]
        if not _nonnegative_finite(req.budget_cents) or not _nonnegative_finite(m.cents_per_1k_tokens):return float("-inf"), ["invalid budget or unit price"]
        if not valid_confidence(m.quality):return float("-inf"), ["invalid catalog quality"]
        if m.max_output_tokens < req.output_tokens: return float("-inf"), ["output limit"]
        try:estimated=(req.output_tokens/1000)*m.cents_per_1k_tokens
        except OverflowError:return float("-inf"), ["invalid estimated cost"]
        if not isfinite(estimated):return float("-inf"), ["invalid estimated cost"]
        if estimated > req.budget_cents: return float("-inf"), ["budget"]
        if not _positive_finite_latency(req.latency_tolerance_ms) or not _positive_finite_latency(m.p95_latency_ms): return float("-inf"), ["invalid latency estimate or tolerance"]
        if m.p95_latency_ms > req.latency_tolerance_ms: return float("-inf"), ["latency estimate exceeds tolerance"]
        latency_fit=min(1.0, req.latency_tolerance_ms/max(1,m.p95_latency_ms))
        cost_fit=max(0.0, 1-estimated/max(.01, req.budget_cents))
        score=.62*m.quality+.23*latency_fit+.15*cost_fit
        reasons += [f"quality={m.quality:.2f}", f"estimated_cost={estimated:.3f}c", f"latency_fit={latency_fit:.2f}"]
        return score,reasons
    def route(self, req: RouteRequest) -> RouteDecision:
        allow=req.required_model_ids
        if type(allow) not in (set,frozenset) or any(type(key) is not str or not key.strip() for key in allow):
            raise NoEligibleModel("Required model IDs must be a set of nonempty text IDs")
        ids=[m.model_id for m in self.catalog]
        if any(type(key) is not str or not key.strip() for key in ids):raise NoEligibleModel("Catalog model IDs must be nonempty text")
        if len(set(ids))!=len(ids):raise NoEligibleModel("Catalog model IDs must be unique")
        ranked=[]; reasons={}; scores={}
        for m in self.catalog:
            score,why=self.score(m,req); reasons[m.model_id]=why; scores[m.model_id]=score
            if score != float("-inf"): ranked.append((score,m))
        if not ranked: raise NoEligibleModel("No model meets capability, budget, and latency constraints")
        ranked.sort(key=lambda x:(x[0],x[1].model_id),reverse=True)
        return RouteDecision(ranked[0][1],tuple(x[1] for x in ranked[1:]),scores,reasons)

def valid_confidence(value) -> bool:
    return type(value) in (int,float) and 0 <= value <= 1 and isfinite(value)

def confidence_from_logprobs(values: list[float]) -> float | None:
    # These are log probabilities, not arbitrary model scores. Invalid evidence
    # is unavailable rather than converted into an apparent success.
    if not isinstance(values,list) or not values:return None
    if any(type(x) not in (int,float) or x > 0 or x < -1e308 or not isfinite(x) for x in values):return None
    return sum(exp(x) for x in values)/len(values)
