from __future__ import annotations
from dataclasses import dataclass
from math import exp
from .models import ModelCapability, RouteRequest

class NoEligibleModel(RuntimeError): pass

@dataclass(frozen=True)
class RouteDecision:
    primary: ModelCapability
    fallbacks: tuple[ModelCapability, ...]
    scores: dict[str, float]
    reasons: dict[str, list[str]]

class ModelRouter:
    """Pluggable deterministic router. Replace score() with an ML policy without changing callers."""
    def __init__(self, catalog: list[ModelCapability]): self.catalog = catalog
    def score(self, m: ModelCapability, req: RouteRequest) -> tuple[float, list[str]]:
        reasons=[]
        if not m.enabled or req.task_type not in m.task_types: return float("-inf"), ["unsupported"]
        if req.required_model_ids and m.model_id not in req.required_model_ids: return float("-inf"), ["not allow-listed"]
        estimated=(req.output_tokens/1000)*m.cents_per_1k_tokens
        if m.max_output_tokens < req.output_tokens: return float("-inf"), ["output limit"]
        if estimated > req.budget_cents: return float("-inf"), ["budget"]
        latency_fit=min(1.0, req.latency_tolerance_ms/max(1,m.p95_latency_ms))
        cost_fit=max(0.0, 1-estimated/max(.01, req.budget_cents))
        score=.62*m.quality+.23*latency_fit+.15*cost_fit
        reasons += [f"quality={m.quality:.2f}", f"estimated_cost={estimated:.3f}c", f"latency_fit={latency_fit:.2f}"]
        return score,reasons
    def route(self, req: RouteRequest) -> RouteDecision:
        ranked=[]; reasons={}; scores={}
        for m in self.catalog:
            score,why=self.score(m,req); reasons[m.model_id]=why; scores[m.model_id]=score
            if score != float("-inf"): ranked.append((score,m))
        if not ranked: raise NoEligibleModel("No model meets capability, budget, and latency constraints")
        ranked.sort(key=lambda x:(x[0],x[1].model_id),reverse=True)
        return RouteDecision(ranked[0][1],tuple(x[1] for x in ranked[1:]),scores,reasons)

def confidence_from_logprobs(values: list[float]) -> float | None:
    return None if not values else sum(exp(x) for x in values)/len(values)
