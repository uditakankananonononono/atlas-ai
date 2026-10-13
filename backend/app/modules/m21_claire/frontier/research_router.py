from __future__ import annotations
from dataclasses import dataclass, asdict
from itertools import combinations
from math import isfinite
from typing import Any

@dataclass(frozen=True)
class ResearchQuestion:
    question_id: str
    question: str
    domain: str
    uncertainty: float = 0.5
    impact: float = 0.5
    testability: float = 0.5
    transfer_potential: float = 0.2
    cost: float = 1.0
    risk: float = 0.1
    downstream_blockers: int = 0
    redundancy: float = 0.0

class ResearchRouter:
    """Ranks information-gathering tasks by decision value and controlled diversity."""
    def score(self, q: ResearchQuestion) -> dict[str, Any]:
        if not q.question_id.strip() or not q.question.strip() or not q.domain.strip(): raise ValueError("question_id, question and domain are required")
        for name in ("uncertainty","impact","testability","transfer_potential","risk","redundancy"):
            value=float(getattr(q,name))
            if not isfinite(value) or not 0 <= value <= 1: raise ValueError(f"{name} must be finite and in [0,1]")
        if not isfinite(float(q.cost)) or q.cost <= 0: raise ValueError("cost must be finite and positive")
        if q.downstream_blockers < 0: raise ValueError("downstream_blockers cannot be negative")
        downstream=1.0+min(q.downstream_blockers,10)*0.12
        # Information-value heuristic, not calibrated probability.
        raw=(q.uncertainty*q.impact*q.testability*(1+q.transfer_potential)*downstream)/q.cost
        adjusted=raw*(1-q.risk)*(1-q.redundancy)
        return {**asdict(q),"raw_value":round(raw,6),"priority":round(adjusted,6),
                "formula":"uncertainty × impact × testability × transfer × downstream leverage / cost × risk and redundancy discount",
                "interpretation":"heuristic ranking; do not interpret as a probability of success"}

    def route(self, questions: list[ResearchQuestion], limit: int = 10, diversity_weight: float = 0.18) -> list[dict[str, Any]]:
        if len(questions)>1000: raise ValueError("maximum 1000 candidate questions")
        if len({q.question_id for q in questions}) != len(questions): raise ValueError("question_id values must be unique")
        if not 0<=diversity_weight<=1: raise ValueError("diversity_weight must be in [0,1]")
        k=max(1,min(limit,len(questions))) if questions else 0
        base={q.question_id:self.score(q) for q in questions}
        remaining=list(questions); selected=[]; seen_domains=set()
        while remaining and len(selected)<k:
            def utility(q):
                diversity=diversity_weight if q.domain not in seen_domains else 0.0
                return base[q.question_id]["priority"]*(1+diversity)
            chosen=max(remaining,key=lambda q:(utility(q),q.question_id))
            row=base[chosen.question_id].copy(); row["selection_order"]=len(selected)+1
            row["diversity_bonus_applied"]=chosen.domain not in seen_domains
            selected.append(row); seen_domains.add(chosen.domain); remaining.remove(chosen)
        return selected


@dataclass(frozen=True)
class Mechanism:
    mechanism_id: str
    name: str
    domain: str
    input_structure: tuple[str,...]
    state_transition: tuple[str,...]
    output_structure: tuple[str,...]
    invariants: tuple[str,...]
    failure_modes: tuple[str,...]
    evidence_ids: tuple[str,...] = ()

class MechanismBridgeFinder:
    """Cross-domain structural analogy; requires a target-domain falsification test."""
    def bridge(self, mechanisms: list[Mechanism], *, min_similarity: float=0.35) -> list[dict[str,Any]]:
        if not 0<=min_similarity<=1: raise ValueError("min_similarity must be [0,1]")
        if len(mechanisms)>200: raise ValueError("maximum 200 mechanism descriptors")
        results=[]
        for a,b in combinations(mechanisms,2):
            if a.domain == b.domain: continue
            components={}
            for field in ("input_structure","state_transition","output_structure","invariants","failure_modes"):
                aa={x.casefold().strip() for x in getattr(a,field) if x.strip()}; bb={x.casefold().strip() for x in getattr(b,field) if x.strip()}
                components[field]=len(aa&bb)/len(aa|bb) if aa|bb else 0.0
            # invariants and state transitions receive extra weight; surface/input match alone cannot dominate.
            similarity=0.10*components["input_structure"]+0.34*components["state_transition"]+0.18*components["output_structure"]+0.28*components["invariants"]+0.10*components["failure_modes"]
            if similarity<min_similarity: continue
            results.append({"bridge_id":f"{a.mechanism_id}__{b.mechanism_id}","source":{"id":a.mechanism_id,"domain":a.domain,"name":a.name},
                "target":{"id":b.mechanism_id,"domain":b.domain,"name":b.name},"structural_similarity":round(similarity,4),
                "component_overlap":{k:round(v,4) for k,v in components.items()},
                "transfer_plan":{"source_method":"Extract the transition/invariant as a minimal formal or executable rule.",
                    "target_adaptation":"Replace source-specific variables with target-domain observables; retain target-domain constraints.",
                    "baseline":"Evaluate against a target-domain standard method and a no-transfer baseline.",
                    "falsification":"Reject the bridge if it fails on a preregistered, untouched target-domain set or breaks domain constraints."},
                "evidence_ids":list(dict.fromkeys((*a.evidence_ids,*b.evidence_ids))),"state":"analogy_hypothesis_not_validated"})
        return sorted(results,key=lambda x:(-x["structural_similarity"],x["bridge_id"]))


class CounterexampleForge:
    """Generates adversarial test *designs* aimed at falsifying a hypothesis."""
    OPERATORS=("remove_assumed_feature","insert_confounder","temporal_shift","domain_shift","reverse_causal_direction",
               "ablate_component","replace_strong_baseline","increase_noise","adversarial_boundary_case","withhold_source")
    def forge(self, hypothesis: str, *, known_assumptions: list[str] | None=None,
              claimed_domain: str="unknown", max_tests: int=8) -> list[dict[str,Any]]:
        if not hypothesis.strip(): raise ValueError("hypothesis is required")
        assumptions=(known_assumptions or [])[:20]
        k=max(1,min(max_tests,len(self.OPERATORS)))
        out=[]
        for i,op in enumerate(self.OPERATORS[:k],1):
            assumption=assumptions[(i-1)%len(assumptions)] if assumptions else "the mechanism generalizes beyond the observed examples"
            out.append({"test_id":f"cf{i:02d}","operator":op,"hypothesis":hypothesis,"assumption_under_attack":assumption,
                "procedure":self._procedure(op,claimed_domain),"pass_condition":"pre-registered quantitative criterion is met on data not used to choose this test",
                "falsifier":"The predicted effect disappears, reverses, or falls below the baseline under this intervention.",
                "data_split":"confirmation_only","execution":"proposal_not_run"})
        return out
    @staticmethod
    def _procedure(op: str, domain: str) -> str:
        procedures={
            "remove_assumed_feature":"Remove the variable believed to carry the causal signal and compare predictions.",
            "insert_confounder":"Construct a plausible third variable that explains the association without the hypothesized mechanism.",
            "temporal_shift":"Train/select on earlier periods and evaluate on a later period not inspected during design.",
            "domain_shift":f"Evaluate the mechanism in a distinct environment within or adjacent to {domain}.",
            "reverse_causal_direction":"Compare the stated causal orientation against the reverse orientation and available interventions.",
            "ablate_component":"Remove one proposed mechanism component while keeping the rest fixed.",
            "replace_strong_baseline":"Compare against a stronger domain-specific baseline under equal data and compute budgets.",
            "increase_noise":"Add preregistered noise levels and locate the point where the effect collapses.",
            "adversarial_boundary_case":"Evaluate extreme, edge, and underspecified cases chosen before outcomes are observed.",
            "withhold_source":"Remove one source family or provenance group to test source dependence."}
        return procedures[op]
