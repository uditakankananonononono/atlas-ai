"""Simulation, forecasting and decision-analysis engines (features-doc rows 35-59).

Each row is an exact, typed capability over the M20 cognitive runtime.
Engines are deterministic and offline; every analysis carries its
assumptions and caveats in the result so nothing is hidden reasoning.
Rows 56-59 are decision-support arithmetic only - they never make
investment-advice claims, and their outputs say so.
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from typing import Any
from uuid import uuid4

from .embeddings import tokenize
from .reasoning import bayesian_update, expected_value, kelly_criterion

DECISION_SUPPORT_CAVEAT = (
    "Decision-support arithmetic over the inputs you supplied, "
    "not investment, financial, legal or professional advice."
)


def _uid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pct_change(part: float, whole: float) -> float:
    return part / whole if whole else 0.0


# ---------------------------------------------------------------- row 35 --
# Serendipity Engineering: strategic randomness that creates conditions
# for lucky discoveries. Suggestions only - nothing here takes an external
# action; execution stays behind the service's normal approval gates.

@dataclass
class SerendipitySlot:
    action: str
    source_gap: str
    rationale: str
    slot_index: int


class SerendipityEngine:
    """Fills a bounded share of idle slots with exploration actions drawn
    from curiosity gaps, plus cross-domain collisions between two unrelated
    known topics. Randomness is seeded so plans are reproducible."""

    def __init__(self, *, epsilon: float = 0.2) -> None:
        if not 0.0 <= epsilon <= 1.0:
            raise ValueError("epsilon must be in [0, 1]")
        self.epsilon = epsilon

    def plan(
        self,
        gaps: list[str],
        *,
        available_slots: int,
        known_topics: list[str] | None = None,
        seed: int | None = None,
    ) -> list[SerendipitySlot]:
        if available_slots < 0:
            raise ValueError("available_slots must be >= 0")
        rng = random.Random(seed)
        n_explore = min(len(gaps) + (1 if (known_topics or []) and len(known_topics) >= 2 else 0),
                        round(available_slots * self.epsilon))
        slots: list[SerendipitySlot] = []
        pool = list(gaps)
        rng.shuffle(pool)
        for i in range(n_explore):
            if i < len(pool):
                gap = pool[i]
                slots.append(SerendipitySlot(
                    action=f"Explore: {gap}",
                    source_gap=gap,
                    rationale="Curiosity gap drawn at random to create discovery conditions",
                    slot_index=i,
                ))
            else:
                pair = rng.sample(list(known_topics or []), 2)
                gap = f"collision:{pair[0]}x{pair[1]}"
                slots.append(SerendipitySlot(
                    action=f"Connect '{pair[0]}' with '{pair[1]}': look for an unexpected link",
                    source_gap=gap,
                    rationale="Cross-domain collision between two unrelated known topics",
                    slot_index=i,
                ))
        return slots


# ---------------------------------------------------------------- row 36 --
# Insight Capture: record fleeting ideas before they are lost, then develop
# them. In-memory in this lane (durability follow-up noted in INTEGRATION.md).

@dataclass
class Insight:
    insight_id: str
    text: str
    context: str
    captured_at: datetime
    links: list[str] = field(default_factory=list)
    developments: list[dict[str, Any]] = field(default_factory=list)
    status: str = "captured"  # captured | developed


class InsightCapture:
    DEVELOPMENT_QUESTIONS = (
        "What would have to be true for this to work?",
        "What is the smallest test of this idea?",
        "Who or what does this connect to that I already know?",
    )

    def __init__(self) -> None:
        self.insights: dict[str, Insight] = {}

    def capture(self, text: str, *, context: str = "", semantic_memory: Any = None) -> Insight:
        insight = Insight(insight_id=_uid(), text=text, context=context, captured_at=_now())
        if semantic_memory is not None:
            insight.links = [
                fact.id
                for fact, score in semantic_memory.query(text, limit=3, min_score=0.05)
            ]
        self.insights[insight.insight_id] = insight
        return insight

    def develop(self, insight_id: str, note: str) -> Insight:
        insight = self.insights[insight_id]
        insight.developments.append({"note": note, "at": _now().isoformat()})
        insight.status = "developed"
        return insight

    def development_prompts(self, insight_id: str) -> list[str]:
        self.insights[insight_id]  # KeyError if unknown
        return list(self.DEVELOPMENT_QUESTIONS)

    def stale(self, *, older_than_days: float = 7.0) -> list[Insight]:
        cutoff = _now() - timedelta(days=older_than_days)
        return [i for i in self.insights.values()
                if i.status == "captured" and i.captured_at < cutoff]


# ---------------------------------------------------------------- row 37 --
# Mental Simulation Fidelity: calibrate how accurately imagined scenarios
# match reality, per domain.

@dataclass
class SimulationRecord:
    record_id: str
    domain: str
    predicted: float
    confidence: float
    actual: float | None = None
    fidelity: float | None = None


class SimulationFidelityTracker:
    """Records predicted vs actual numeric outcomes of mental simulations
    and scores fidelity = 1 - relative error, clamped to [0, 1]. The
    running per-domain fidelity is the calibration factor future
    simulation confidence should be multiplied by."""

    def __init__(self) -> None:
        self.records: dict[str, SimulationRecord] = {}

    def record_prediction(self, domain: str, predicted: float, *, confidence: float = 0.5) -> SimulationRecord:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        rec = SimulationRecord(record_id=_uid(), domain=domain, predicted=predicted, confidence=confidence)
        self.records[rec.record_id] = rec
        return rec

    def resolve(self, record_id: str, actual: float) -> SimulationRecord:
        rec = self.records[record_id]
        rec.actual = actual
        scale = max(abs(actual), abs(rec.predicted), 1e-9)
        rec.fidelity = max(0.0, 1.0 - abs(rec.predicted - actual) / scale)
        return rec

    def fidelity(self, *, domain: str | None = None) -> float | None:
        vals = [r.fidelity for r in self.records.values()
                if r.fidelity is not None and (domain is None or r.domain == domain)]
        return mean(vals) if vals else None

    def confidence_adjustment(self, *, domain: str | None = None) -> float:
        """Multiplier for future simulation confidence; 1.0 when uncalibrated."""
        f = self.fidelity(domain=domain)
        return 1.0 if f is None else f


# ---------------------------------------------------------------- row 38 --
# Parallel Hypothesis Tracking: multiple explanations maintained
# simultaneously; evidence updates all of them at once.

@dataclass
class Hypothesis:
    hypothesis_id: str
    statement: str
    probability: float
    status: str = "active"  # active | retired
    evidence_count: int = 0


class HypothesisTracker:
    RETIRE_BELOW = 0.01

    def __init__(self) -> None:
        self.hypotheses: dict[str, Hypothesis] = {}

    def add(self, statement: str, *, prior: float) -> Hypothesis:
        if not 0.0 < prior < 1.0:
            raise ValueError("prior must be in (0, 1)")
        h = Hypothesis(hypothesis_id=_uid(), statement=statement, probability=prior)
        self.hypotheses[h.hypothesis_id] = h
        return h

    def update(self, likelihood_ratios: dict[str, float]) -> list[Hypothesis]:
        """Apply one evidence item: per-hypothesis likelihood ratio
        P(evidence | hypothesis) / P(evidence | not hypothesis). Posteriors
        are computed in odds form and renormalized across active hypotheses."""
        for hid, lr in likelihood_ratios.items():
            if lr <= 0:
                raise ValueError("likelihood ratios must be positive")
            h = self.hypotheses[hid]
            odds = h.probability / (1.0 - h.probability)
            h.probability = odds * lr / (1.0 + odds * lr)
            h.evidence_count += 1
        active = [h for h in self.hypotheses.values() if h.status == "active"]
        for h in active:
            if h.probability < self.RETIRE_BELOW:
                h.status = "retired"
        survivors = [h for h in active if h.status == "active"]
        total = sum(h.probability for h in survivors)
        if total > 0:
            for h in survivors:
                h.probability /= total
        return self.ranking()

    def ranking(self) -> list[Hypothesis]:
        return sorted((h for h in self.hypotheses.values() if h.status == "active"),
                      key=lambda h: h.probability, reverse=True)


# ---------------------------------------------------------------- row 39 --
# Bayesian Belief Updating.

class BayesianUpdater:
    """Exact Bayesian revisions: odds-form updates with likelihood ratios,
    the sensitivity/specificity form, and beta-binomial rate learning."""

    @staticmethod
    def update(prior: float, likelihood_ratio: float) -> float:
        if not 0.0 <= prior <= 1.0:
            raise ValueError("prior must be in [0, 1]")
        if likelihood_ratio <= 0:
            raise ValueError("likelihood_ratio must be positive")
        odds = prior / (1.0 - prior) if prior < 1.0 else math.inf
        post_odds = odds * likelihood_ratio
        return 1.0 if math.isinf(post_odds) else post_odds / (1.0 + post_odds)

    @staticmethod
    def update_binary(prior: float, *, sensitivity: float, specificity: float,
                      positive: bool = True) -> float:
        return bayesian_update(prior, sensitivity, specificity, positive=positive)

    @staticmethod
    def update_beta(alpha: float, beta: float, *, successes: int, failures: int) -> dict[str, float]:
        if alpha <= 0 or beta <= 0 or successes < 0 or failures < 0:
            raise ValueError("invalid beta parameters or counts")
        a, b = alpha + successes, beta + failures
        return {"alpha": a, "beta": b, "mean": a / (a + b)}

    @staticmethod
    def sequence(prior: float, likelihood_ratios: list[float]) -> list[float]:
        out, p = [], prior
        for lr in likelihood_ratios:
            p = BayesianUpdater.update(p, lr)
            out.append(p)
        return out


# ---------------------------------------------------------------- row 40 --
# Causal vs Correlational Distinction.

@dataclass
class CausalReport:
    cause: str
    effect: str
    verdict: str  # causal_supported | plausible_unproven | correlational_only
    evidence_present: dict[str, bool]
    alternative_explanations: list[str]
    required_tests: list[str]
    assumptions: list[str]


class CausalAssessor:
    """Checklist-based assessment: causation is only 'supported' when the
    evidence supplied includes randomization, or the Bradford-Hill-style
    combination of temporal order + mechanism + dose response. Missing
    evidence generates the alternative explanations that remain open."""

    EVIDENCE_KEYS = ("randomized", "temporal_order", "mechanism", "dose_response", "controlled")

    def assess(self, *, cause: str, effect: str, evidence: dict[str, bool] | None = None) -> CausalReport:
        ev = {k: bool((evidence or {}).get(k, False)) for k in self.EVIDENCE_KEYS}
        alternatives: list[str] = []
        tests: list[str] = []
        if not ev["randomized"]:
            alternatives.append(f"A confounder may drive both '{cause}' and '{effect}'")
            tests.append("Randomize assignment to the cause, or control measured confounders")
        if not ev["temporal_order"]:
            alternatives.append(f"Reverse causation: '{effect}' may precede '{cause}'")
            tests.append("Establish that the cause precedes the effect in time")
        if not ev["mechanism"]:
            alternatives.append("The link may be coincidental or via a common cause")
            tests.append("Demonstrate a plausible mechanism connecting cause to effect")
        if not ev["dose_response"]:
            tests.append("Check whether more of the cause produces more of the effect")
        if not ev["controlled"]:
            tests.append("Replicate under controlled conditions with a comparison group")
        if ev["randomized"] or (ev["temporal_order"] and ev["mechanism"] and ev["dose_response"]):
            verdict = "causal_supported"
        elif any(ev.values()):
            verdict = "plausible_unproven"
        else:
            verdict = "correlational_only"
        return CausalReport(
            cause=cause, effect=effect, verdict=verdict, evidence_present=ev,
            alternative_explanations=alternatives, required_tests=tests,
            assumptions=["Only the evidence flags supplied were considered",
                          "This is a structured checklist, not a substitute for experimentation"],
        )


# ---------------------------------------------------------------- row 41 --
# Base Rate Integration.

@dataclass
class BaseRateEstimate:
    base_rate: float
    case_estimate: float
    weight_on_case: float
    adjusted: float
    explanation: str
    assumptions: list[str]


class BaseRateIntegrator:
    """Shrinks a case-specific estimate toward the base rate. The case
    weight grows with evidence reliability and sample size, so weak
    evidence lands near the base rate and strong evidence near the case."""

    def __init__(self, *, sample_strength: float = 5.0) -> None:
        self.sample_strength = sample_strength

    def integrate(self, *, base_rate: float, case_estimate: float,
                  evidence_reliability: float = 0.5, sample_size: int = 0) -> BaseRateEstimate:
        for name, v in (("base_rate", base_rate), ("case_estimate", case_estimate),
                        ("evidence_reliability", evidence_reliability)):
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        n_factor = sample_size / (sample_size + self.sample_strength) if sample_size > 0 else 0.0
        w = evidence_reliability * max(n_factor, 0.1)
        adjusted = w * case_estimate + (1.0 - w) * base_rate
        return BaseRateEstimate(
            base_rate=base_rate, case_estimate=case_estimate, weight_on_case=w,
            adjusted=adjusted,
            explanation=(f"Case estimate weighted {w:.0%}; base rate weighted {1 - w:.0%}. "
                         "Weak or thin evidence stays near the base rate."),
            assumptions=["The supplied base rate comes from a relevant reference class",
                          "evidence_reliability and sample_size were caller-supplied"],
        )


# ---------------------------------------------------------------- row 42 --
# Reference Class Forecasting.

@dataclass
class ReferenceClassForecast:
    n_cases: int
    mean: float
    median: float
    p25: float
    p75: float
    matched_cases: list[str]
    assumptions: list[str]


class ReferenceClassForecaster:
    """Predicts from similar past cases: similarity = token overlap of the
    feature text. Falls back to all cases when the class is small."""

    def __init__(self, *, min_similar: int = 3, min_overlap: float = 0.15) -> None:
        self.min_similar = min_similar
        self.min_overlap = min_overlap
        self.cases: list[dict[str, Any]] = []

    def add_case(self, features: str, outcome: float, *, label: str | None = None) -> None:
        self.cases.append({"features": features, "tokens": set(tokenize(features)),
                           "outcome": outcome, "label": label or features})

    def forecast(self, features: str) -> ReferenceClassForecast | None:
        if not self.cases:
            return None
        q = set(tokenize(features))
        def sim(c: dict[str, Any]) -> float:
            union = q | c["tokens"]
            return len(q & c["tokens"]) / len(union) if union else 0.0
        scored = sorted(self.cases, key=sim, reverse=True)
        matched = [c for c in scored if sim(c) >= self.min_overlap]
        if len(matched) < self.min_similar:
            matched = scored[: max(self.min_similar, len(matched))]
        outcomes = sorted(c["outcome"] for c in matched)
        n = len(outcomes)
        return ReferenceClassForecast(
            n_cases=n, mean=mean(outcomes), median=median(outcomes),
            p25=outcomes[int(0.25 * (n - 1))], p75=outcomes[int(0.75 * (n - 1))],
            matched_cases=[c["label"] for c in matched],
            assumptions=["Outcomes are only as relevant as the reference class is similar",
                          f"Similarity threshold {self.min_overlap}; {n} case(s) used"],
        )


# ---------------------------------------------------------------- row 43 --
# Outside View Adoption.

@dataclass
class OutsideViewReport:
    inside_estimate: float
    outside_median: float | None
    outside_weight: float
    blended: float
    perspective_notes: list[str]
    assumptions: list[str]


class OutsideView:
    """Blends the inside estimate with the reference-class median and
    restates the situation the way an uninvolved observer would see it.
    Notes are generated framing prompts - analysis output, not hidden
    reasoning."""

    def adopt(self, *, inside_estimate: float,
              reference_forecast: ReferenceClassForecast | None,
              outside_weight: float = 0.5, subject: str = "this project") -> OutsideViewReport:
        if not 0.0 <= outside_weight <= 1.0:
            raise ValueError("outside_weight must be in [0, 1]")
        outside_median = reference_forecast.median if reference_forecast else None
        if outside_median is None:
            blended, effective_w = inside_estimate, 0.0
        else:
            blended = outside_weight * outside_median + (1 - outside_weight) * inside_estimate
            effective_w = outside_weight
        notes = [
            f"An uninvolved observer would ask how similar cases of {subject} usually turn out.",
            f"An observer sees the statistics before the story: median comparable outcome is "
            f"{outside_median if outside_median is not None else 'unknown (no reference class)'}.",
            "Details that feel unique from the inside are usually common from the outside.",
        ]
        return OutsideViewReport(
            inside_estimate=inside_estimate, outside_median=outside_median,
            outside_weight=effective_w, blended=blended, perspective_notes=notes,
            assumptions=[f"Blend weight {effective_w:.0%} outside / {1 - effective_w:.0%} inside",
                          "No reference class supplied -> inside estimate kept"
                          if outside_median is None else "Reference class treated as relevant"],
        )


# ---------------------------------------------------------------- row 44 --
# Planning Fallacy Correction.

class PlanningFallacyCorrector:
    """Learns per-kind overrun multipliers (actual / estimated) and corrects
    new estimates. Multipliers are shrunk toward 1.0 while samples are few."""

    def __init__(self, *, shrinkage: float = 5.0) -> None:
        self.shrinkage = shrinkage
        self.history: dict[str, list[float]] = {}

    def record(self, *, kind: str, estimated: float, actual: float) -> None:
        if estimated <= 0 or actual < 0:
            raise ValueError("estimated must be > 0 and actual >= 0")
        self.history.setdefault(kind, []).append(actual / estimated)

    def multiplier(self, kind: str) -> tuple[float, int]:
        ratios = self.history.get(kind, [])
        if not ratios:
            return 1.0, 0
        raw = mean(ratios)
        n = len(ratios)
        return 1.0 + (raw - 1.0) * n / (n + self.shrinkage), n

    def correct(self, *, kind: str, estimate: float) -> dict[str, Any]:
        if estimate <= 0:
            raise ValueError("estimate must be > 0")
        mult, n = self.multiplier(kind)
        return {"estimate": estimate, "corrected": estimate * mult, "multiplier": mult,
                "samples": n,
                "assumptions": [f"Multiplier shrunk toward 1.0 (shrinkage {self.shrinkage})",
                                 "Past overruns of this task kind predict future ones"]}


# ---------------------------------------------------------------- row 45 --
# Optimism/Pessimism Calibration: match confidence to actual accuracy.

class OptimismCalibrator:
    """Tracks signed bias (predicted confidence minus actual success rate)
    per domain and subtracts it from new confidence judgments. Distinct
    from row 13's evidence-ceiling calibration: this measures direction
    of error, not just magnitude."""

    def __init__(self, *, min_samples: int = 3) -> None:
        self.min_samples = min_samples
        self.records: dict[str, list[tuple[float, bool]]] = {}

    def record(self, *, domain: str, predicted_confidence: float, succeeded: bool) -> None:
        if not 0.0 <= predicted_confidence <= 1.0:
            raise ValueError("predicted_confidence must be in [0, 1]")
        self.records.setdefault(domain, []).append((predicted_confidence, succeeded))

    def bias(self, domain: str) -> tuple[float, int]:
        rows = self.records.get(domain, [])
        if not rows:
            return 0.0, 0
        return mean(p - (1.0 if s else 0.0) for p, s in rows), len(rows)

    def adjust(self, *, domain: str, confidence: float) -> dict[str, Any]:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        b, n = self.bias(domain)
        applied = b if n >= self.min_samples else 0.0
        adjusted = min(1.0, max(0.0, confidence - applied))
        direction = "optimistic" if applied > 0 else ("pessimistic" if applied < 0 else "neutral")
        return {"confidence": confidence, "adjusted": adjusted, "bias": applied,
                "direction": direction, "samples": n,
                "assumptions": [f"Bias applied only with >= {self.min_samples} samples",
                                 "Historical bias in this domain persists"]}


# ---------------------------------------------------------------- row 46 --
# Scenario Planning.

@dataclass
class Scenario:
    name: str
    probability: float
    key_developments: list[str]
    strategy: str
    early_indicators: list[str]


class ScenarioPlanner:
    """Builds best/base/worst/wildcard scenarios from caller-supplied
    drivers. Probabilities are caller-visible defaults that can be
    overridden; every narrative point is derived from the drivers, so the
    construction is inspectable."""

    DEFAULTS = {"best": 0.2, "base": 0.5, "worst": 0.25, "wildcard": 0.05}

    def plan(self, *, objective: str, drivers: list[str],
             probabilities: dict[str, float] | None = None) -> dict[str, Any]:
        if not drivers:
            raise ValueError("at least one driver is required")
        probs = dict(self.DEFAULTS)
        if probabilities:
            probs.update(probabilities)
        total = sum(probs.values())
        if total <= 0:
            raise ValueError("probabilities must sum to a positive value")
        scenarios: list[Scenario] = []
        for name, p in probs.items():
            developments = {
                "best": [f"{d} resolves favorably" for d in drivers],
                "base": [f"{d} continues on its current path" for d in drivers],
                "worst": [f"{d} turns adverse" for d in drivers],
                "wildcard": [f"An unexpected event changes the meaning of {drivers[0]}"],
            }[name]
            strategy = {
                "best": f"Scale what works toward '{objective}' while conditions are favorable",
                "base": f"Execute the current plan for '{objective}' with steady monitoring",
                "worst": f"Protect the downside of '{objective}'; predefine retreat triggers",
                "wildcard": f"Keep slack and optionality so '{objective}' can absorb a surprise",
            }[name]
            scenarios.append(Scenario(
                name=name, probability=p / total, key_developments=developments,
                strategy=strategy,
                early_indicators=[f"Movement in: {d}" for d in drivers],
            ))
        return {"objective": objective, "drivers": list(drivers),
                "scenarios": [s.__dict__ for s in scenarios],
                "assumptions": ["Probabilities are defaults unless overridden",
                                 "Developments are constructed from the supplied drivers"]}


# ---------------------------------------------------------------- row 47 --
# Pre-Mortem Analysis.

@dataclass
class FailureCause:
    cause: str
    likelihood: float
    impact: float
    score: float
    prevention: str


class PremortemEngine:
    """Assumes the project has failed and works backward: caller-supplied
    risks plus generic failure modes (kept only when they share vocabulary
    with the goal) are scored likelihood x impact and paired with a
    prevention action."""

    GENERIC = [
        ("under-resourcing: the effort was starved of time or people", "resources|budget|staff|time|deadline",
         "Ring-fence resources before starting"),
        ("dependency failure: an external party or component did not deliver", "vendor|partner|api|dependency|supplier",
         "Identify critical dependencies and arrange fallbacks"),
        ("scope creep: the goal grew until it became unachievable", "scope|feature|launch|project",
         "Freeze scope and route additions through review"),
        ("key-person loss: one person held irreplaceable knowledge", "team|hire|person|expert",
         "Document critical knowledge and cross-train"),
        ("premature scaling: commitment grew before validation", "scale|growth|expand|marketing",
         "Validate with a small test before scaling"),
    ]

    def analyze(self, *, goal: str, risks: list[str] | None = None,
                failure_date: datetime | None = None) -> dict[str, Any]:
        causes: list[FailureCause] = []
        for risk in risks or []:
            causes.append(FailureCause(
                cause=risk, likelihood=0.5, impact=0.7, score=0.35,
                prevention=f"Define an owner and an early-warning indicator for: {risk}",
            ))
        goal_tokens = set(tokenize(goal))
        for text, pattern, prevention in self.GENERIC:
            if set(tokenize(re.sub(r"[|]", " ", pattern))) & goal_tokens:
                causes.append(FailureCause(cause=text, likelihood=0.4, impact=0.6,
                                           score=0.24, prevention=prevention))
        causes.sort(key=lambda c: c.score, reverse=True)
        return {
            "goal": goal,
            "failure_assumed_at": (failure_date or _now() + timedelta(days=180)).isoformat(),
            "framing": "It is the failure date and the project has failed. Work backward.",
            "causes": [c.__dict__ for c in causes],
            "assumptions": ["Likelihood/impact are placeholder scores for review, not measurements",
                             "Generic failure modes matched by vocabulary overlap with the goal"],
        }


# ---------------------------------------------------------------- row 48 --
# Red Team Thinking: adversarial vulnerability hunt. Distinct from row 30
# (devil's advocate stresses a decision's assumptions); this probes a plan
# or system for ways to break or abuse it.

@dataclass
class Vulnerability:
    vector: str
    target: str
    severity: str  # high | medium | low
    probe: str


class RedTeamer:
    SPOF_WORDS = ("only", "single", "just one", "one person", "sole")
    ASSUMPTION_WORDS = ("will", "should", "expects", "assumes", "always", "never")

    def probe(self, *, plan: str, assets: list[str] | None = None) -> dict[str, Any]:
        vulns: list[Vulnerability] = []
        lower = plan.lower()
        for word in self.SPOF_WORDS:
            if word in lower:
                vulns.append(Vulnerability(
                    vector="single point of failure", target=plan[:80], severity="high",
                    probe=f"Plan says '{word}' - what breaks if that one element fails?"))
                break
        assumption_hits = sum(1 for w in self.ASSUMPTION_WORDS if f" {w} " in f" {lower} ")
        if assumption_hits:
            vulns.append(Vulnerability(
                vector="unstated assumptions", target=plan[:80],
                severity="medium" if assumption_hits < 3 else "high",
                probe=f"{assumption_hits} forward-looking claim(s) found - which are load-bearing and untested?"))
        for i, asset in enumerate(assets or []):
            severity = "high" if i == 0 else ("medium" if i < 3 else "low")
            vulns.append(Vulnerability(
                vector="abuse case", target=asset, severity=severity,
                probe=f"How could '{asset}' be misused by someone with legitimate access? "
                      "How could it be attacked from outside?"))
        if not vulns:
            vulns.append(Vulnerability(
                vector="unknown unknowns", target=plan[:80], severity="low",
                probe="No obvious weakness found - what would make this conclusion wrong?"))
        order = {"high": 0, "medium": 1, "low": 2}
        vulns.sort(key=lambda v: order[v.severity])
        return {"vulnerabilities": [v.__dict__ for v in vulns],
                "assumptions": ["Severity of asset abuse cases follows the order assets were supplied",
                                 "Pattern-matched probes, not an exhaustive attack model"]}


# ---------------------------------------------------------------- row 49 --
# Second-Order Effects Tracing.

@dataclass
class EffectNode:
    effect: str
    order: int
    sign: str  # positive | negative | neutral
    parent: str | None
    rule_fired: str | None
    delay: str


class SecondOrderTracer:
    """Propagates first-order effects through an explicit, inspectable rule
    table. Every inferred effect names the rule that produced it - no
    hidden reasoning."""

    DEFAULT_RULES: tuple[tuple[str, str, str, str], ...] = (
        ("cheaper|cost down|price cut", "demand increases", "positive", "weeks"),
        ("demand increases", "capacity strain emerges", "negative", "months"),
        ("capacity strain", "quality slips or prices rise", "negative", "months"),
        ("faster|speed up|instant", "expectations reset higher", "negative", "weeks"),
        ("automate|automation", "skills that are automated away atrophy", "negative", "months"),
        ("cut|layoff|reduce staff", "morale drops", "negative", "days"),
        ("morale drops", "turnover rises among the strongest performers", "negative", "months"),
        ("growth|more users|expansion", "coordination complexity grows", "negative", "months"),
        ("surveillance|monitor|track", "trust erodes", "negative", "weeks"),
        ("trust erodes", "cooperation and candor decline", "negative", "months"),
    )

    def __init__(self, rules: tuple[tuple[str, str, str, str], ...] | None = None) -> None:
        self.rules = rules or self.DEFAULT_RULES

    def trace(self, *, action: str, first_order: list[str], depth: int = 2) -> dict[str, Any]:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        nodes: list[EffectNode] = [EffectNode(effect=e, order=1, sign="neutral",
                                              parent=action, rule_fired=None, delay="immediate")
                                   for e in first_order]
        frontier = list(first_order)
        for order in range(2, depth + 1):
            next_frontier: list[str] = []
            for parent_effect in frontier:
                for pattern, produced, sign, delay in self.rules:
                    if re.search(pattern, parent_effect, re.IGNORECASE) and \
                            not any(n.effect == produced for n in nodes):
                        nodes.append(EffectNode(effect=produced, order=order, sign=sign,
                                                parent=parent_effect,
                                                rule_fired=pattern, delay=delay))
                        next_frontier.append(produced)
            frontier = next_frontier
            if not frontier:
                break
        return {"action": action,
                "effects": [n.__dict__ for n in nodes],
                "rules_used": sorted({n.rule_fired for n in nodes if n.rule_fired}),
                "assumptions": ["Second-order effects come from the explicit rule table returned in "
                                 "rules_used - review it before trusting the trace",
                                 f"Trace stopped at depth {depth} or when no rule fired"]}


# ---------------------------------------------------------------- row 50 --
# Systems Thinking: feedback loops, delays, emergence.

@dataclass
class SystemLink:
    source: str
    target: str
    sign: str  # + | -
    delay: str


@dataclass
class FeedbackLoop:
    variables: list[str]
    kind: str  # reinforcing | balancing
    delay_notes: list[str]


class SystemsModel:
    """A directed signed graph of variables. Loops are found by DFS and
    classified: an even number of negative links makes a reinforcing loop,
    an odd number a balancing loop."""

    def __init__(self) -> None:
        self.variables: set[str] = set()
        self.links: list[SystemLink] = []

    def add_variable(self, name: str) -> None:
        self.variables.add(name)

    def add_link(self, source: str, target: str, *, sign: str = "+", delay: str = "") -> None:
        if sign not in ("+", "-"):
            raise ValueError("sign must be '+' or '-'")
        self.variables.update((source, target))
        self.links.append(SystemLink(source=source, target=target, sign=sign, delay=delay))

    def loops(self) -> list[FeedbackLoop]:
        adjacency: dict[str, list[SystemLink]] = {}
        for link in self.links:
            adjacency.setdefault(link.source, []).append(link)
        found: list[FeedbackLoop] = []
        seen: set[tuple[str, ...]] = set()

        def dfs(start: str, node: str, path: list[str], signs: list[str], delays: list[str]) -> None:
            for link in adjacency.get(node, []):
                if link.target == start and len(path) >= 2:
                    key = tuple(sorted(path))
                    if key not in seen:
                        seen.add(key)
                        negatives = (signs + [link.sign]).count("-")
                        found.append(FeedbackLoop(
                            variables=path + [start],
                            kind="reinforcing" if negatives % 2 == 0 else "balancing",
                            delay_notes=[d for d in delays + [link.delay] if d],
                        ))
                elif link.target not in path and len(path) < 12:
                    dfs(start, link.target, path + [link.target], signs + [link.sign], delays + [link.delay])

        for v in sorted(self.variables):
            dfs(v, v, [v], [], [])
        return found

    def emergence_notes(self) -> list[str]:
        degree: dict[str, int] = {v: 0 for v in self.variables}
        for link in self.links:
            degree[link.source] += 1
            degree[link.target] += 1
        hubs = [v for v, d in degree.items() if d >= 3]
        return ([f"'{v}' connects {degree[v]} links - behavior here may emerge rather than be designed"
                 for v in sorted(hubs)]
                or ["No high-connectivity hubs; dynamics are likely linear"])


# ---------------------------------------------------------------- row 51 --
# Leverage Point Identification.

@dataclass
class LeveragePoint:
    variable: str
    score: float
    level: str  # goal | structure | parameter
    rationale: str


class LeverageFinder:
    """Ranks intervention points: variables inside reinforcing loops and
    with many outgoing, low-delay links score highest. Level classification
    is heuristic: goal-named variables > loop members > parameters."""

    def rank(self, model: SystemsModel) -> list[LeveragePoint]:
        if not model.links:
            raise ValueError("at least one causal link is required")
        loops = model.loops()
        reinforcing_vars = {v for loop in loops if loop.kind == "reinforcing" for v in loop.variables}
        loop_vars = {v for loop in loops for v in loop.variables}
        out_degree: dict[str, int] = {}
        delays: dict[str, list[str]] = {}
        for link in model.links:
            out_degree[link.source] = out_degree.get(link.source, 0) + 1
            delays.setdefault(link.source, []).append(link.delay)
        points: list[LeveragePoint] = []
        for v in sorted(model.variables):
            score = float(out_degree.get(v, 0))
            rationale = [f"{out_degree.get(v, 0)} outgoing link(s)"]
            if v in reinforcing_vars:
                score += 2.0
                rationale.append("inside a reinforcing loop")
            elif v in loop_vars:
                score += 1.0
                rationale.append("inside a balancing loop")
            if any(d in ("", "days") for d in delays.get(v, [])):
                score += 0.5
                rationale.append("acts with short delay")
            level = ("goal" if re.search(r"goal|purpose|target|mission", v, re.IGNORECASE)
                     else ("structure" if v in loop_vars else "parameter"))
            points.append(LeveragePoint(variable=v, score=score, level=level,
                                        rationale="; ".join(rationale)))
        points.sort(key=lambda p: p.score, reverse=True)
        return points


# ---------------------------------------------------------------- row 52 --
# Constraint Theory Application (Theory of Constraints).

@dataclass
class StageAnalysis:
    name: str
    capacity: float
    demand: float
    utilization: float
    is_bottleneck: bool


class ConstraintAnalyzer:
    """Finds the bottleneck (lowest capacity relative to demand), computes
    system throughput, and maps the five focusing steps."""

    def analyze(self, *, stages: list[dict[str, Any]]) -> dict[str, Any]:
        if not stages:
            raise ValueError("at least one stage is required")
        rows: list[StageAnalysis] = []
        for s in stages:
            capacity, demand = float(s["capacity"]), float(s.get("demand", 0.0))
            if capacity <= 0:
                raise ValueError("capacity must be > 0")
            rows.append(StageAnalysis(name=s["name"], capacity=capacity, demand=demand,
                                      utilization=_pct_change(demand, capacity),
                                      is_bottleneck=False))
        bottleneck = min(rows, key=lambda r: r.capacity)
        for r in rows:
            r.is_bottleneck = r is bottleneck
        throughput = bottleneck.capacity
        elevate_gain = _pct_change(0.1 * bottleneck.capacity, throughput)
        return {
            "stages": [r.__dict__ for r in rows],
            "bottleneck": bottleneck.name,
            "system_throughput": throughput,
            "focusing_steps": [
                f"IDENTIFY: '{bottleneck.name}' limits the whole system at {throughput:g} units",
                f"EXPLOIT: keep '{bottleneck.name}' fully fed; never let it idle or process defects",
                f"SUBORDINATE: pace every other stage to '{bottleneck.name}' - excess output elsewhere is waste",
                f"ELEVATE: +10% capacity at '{bottleneck.name}' lifts system throughput ~{elevate_gain:.0%}",
                "REPEAT: after elevating, re-run this analysis - the constraint will have moved",
            ],
            "assumptions": ["Steady-state flow, no buffers modelled",
                             "Bottleneck = lowest absolute capacity stage"],
        }


# ---------------------------------------------------------------- row 53 --
# Antifragility Design.

@dataclass
class ComponentAssessment:
    name: str
    classification: str  # fragile | robust | antifragile
    stress_response: float
    redesign: list[str]


class AntifragilityAssessor:
    """Classifies each component by its response per unit of stress
    (negative: fragile, ~0: robust, positive: antifragile) and proposes
    redesign moves for the fragile ones."""

    REDESIGN = {
        "fragile": ["Add redundancy or a fallback for this component",
                     "Shrink the blast radius of its failure",
                     "Replace a single large exposure with many small experiments"],
        "robust": ["Consider adding optionality so volatility can pay, not just be survived"],
        "antifragile": ["Protect this component's exposure to stress - it is the source of gain"],
    }

    def assess(self, *, components: list[dict[str, Any]]) -> dict[str, Any]:
        if not components:
            raise ValueError("at least one component is required")
        out: list[ComponentAssessment] = []
        for c in components:
            response = float(c["stress_response"])
            classification = ("fragile" if response < -0.05
                              else "antifragile" if response > 0.05 else "robust")
            out.append(ComponentAssessment(
                name=c["name"], classification=classification, stress_response=response,
                redesign=list(self.REDESIGN[classification])))
        fragile_share = _pct_change(sum(1 for c in out if c.classification == "fragile"), len(out))
        verdict = ("antifragile" if all(c.classification == "antifragile" for c in out)
                   else "fragile-heavy" if fragile_share >= 0.5 else "mixed")
        return {"components": [c.__dict__ for c in out],
                "fragile_share": fragile_share, "verdict": verdict,
                "assumptions": ["stress_response is change per unit stress, caller-estimated",
                                 "Classification bands: |response| <= 0.05 is robust"]}


# ---------------------------------------------------------------- row 54 --
# Optionality Preservation.

class OptionalityAnalyzer:
    """Scores a decision by the options it keeps open versus closes, and
    recommends staging when valuable options would be lost."""

    def assess(self, *, decision: str, options_kept: list[str],
               options_closed: list[str], reversible: bool = False) -> dict[str, Any]:
        kept, closed = len(options_kept), len(options_closed)
        if kept + closed == 0:
            raise ValueError("list at least one option kept or closed")
        score = kept / (kept + closed)
        if reversible:
            score = min(1.0, score + 0.2)
        recommendations: list[str] = []
        if closed and score < 0.5:
            recommendations.append("Stage the commitment: decide in two steps so the first step "
                                   "keeps the most valuable closed option open")
        if options_closed:
            recommendations.append(f"Price the loss of '{options_closed[0]}' before committing - "
                                   "that is the option premium being paid")
        if not reversible and closed:
            recommendations.append("Prefer a pilot or trial run before the irreversible step")
        if not recommendations:
            recommendations.append("Optionality is well preserved; no staging needed")
        return {"decision": decision, "options_kept": options_kept,
                "options_closed": options_closed, "reversible": reversible,
                "optionality_score": score, "recommendations": recommendations,
                "assumptions": ["All listed options are treated as equally valuable",
                                 "Reversibility adds 0.2 to the score"]}


# ---------------------------------------------------------------- row 55 --
# Reversibility Assessment: one-way vs two-way doors.

class ReversibilityAssessor:
    """Classifies decisions by undo cost, undo time and blast radius, and
    recommends how much deliberation each class deserves. Irreversible,
    high-blast decisions are flagged for the approval path (Module 0)."""

    def assess(self, *, decision: str, undo_cost: float, undo_days: float,
               blast_radius: float) -> dict[str, Any]:
        for name, v in (("undo_cost", undo_cost), ("blast_radius", blast_radius)):
            if not 0.0 <= v <= 10.0:
                raise ValueError(f"{name} must be in [0, 10]")
        if undo_days < 0:
            raise ValueError("undo_days must be >= 0")
        if undo_cost <= 3.0 and undo_days <= 7.0 and blast_radius <= 3.0:
            classification, deliberation = "two_way_door", "decide fast, correct later"
        elif undo_cost >= 8.0 or blast_radius >= 8.0 or undo_days >= 90.0:
            classification = "one_way_door"
            deliberation = "slow down: independent review and approval before committing"
        else:
            classification, deliberation = "costly_reversible", "deliberate briefly, define an undo trigger"
        return {"decision": decision, "classification": classification,
                "undo_cost": undo_cost, "undo_days": undo_days, "blast_radius": blast_radius,
                "recommended_deliberation": deliberation,
                "requires_approval_review": classification == "one_way_door",
                "assumptions": ["Scales: undo_cost and blast_radius 0-10, undo_days in days",
                                 "Thresholds: two-way <= 3/7d/3; one-way >= 8 or 90d"]}


# ---------------------------------------------------------------- row 56 --
# Asymmetric Bet Identification.

class AsymmetryFinder:
    """Flags options whose downside is explicitly bounded and small relative
    to a much larger upside. Options with unbounded downside are flagged,
    never endorsed."""

    def evaluate(self, *, options: list[dict[str, Any]]) -> dict[str, Any]:
        if not options:
            raise ValueError("at least one option is required")
        rows: list[dict[str, Any]] = []
        for o in options:
            downside = o.get("downside")
            upside = float(o["upside"])
            prob = float(o.get("prob_upside", 0.5))
            if not 0.0 <= prob <= 1.0:
                raise ValueError("prob_upside must be in [0, 1]")
            if downside is None:
                rows.append({"name": o["name"], "asymmetric": False,
                             "flag": "unbounded downside - asymmetry cannot be confirmed",
                             "ratio": None, "expected_upside": None})
                continue
            downside = float(downside)
            if downside <= 0:
                raise ValueError("downside must be > 0 when supplied")
            ratio = upside / downside
            rows.append({"name": o["name"], "asymmetric": ratio >= 3.0 and prob > 0.0,
                         "flag": ("limited downside, large upside" if ratio >= 3.0
                                  else "downside too large relative to upside"),
                         "ratio": ratio, "expected_upside": prob * upside,
                         "downside_cap": downside})
        rows.sort(key=lambda r: (r["ratio"] or 0.0), reverse=True)
        return {"options": rows, "caveat": DECISION_SUPPORT_CAVEAT,
                "assumptions": ["Downside caps are caller-declared; verify them before trusting a flag",
                                 "Asymmetry threshold: upside/downside >= 3"]}


# ---------------------------------------------------------------- row 57 --
# Expected Value Calculation.

class EVCalculator:
    """Probability-weighted outcomes per option, with a simple sensitivity:
    how EV moves if the best outcome's probability shifts by +/-10 points."""

    def compute(self, *, options: list[dict[str, Any]]) -> dict[str, Any]:
        if not options:
            raise ValueError("at least one option is required")
        rows: list[dict[str, Any]] = []
        for o in options:
            outcomes = [(float(p), float(v)) for p, v in o["outcomes"]]
            total_p = sum(p for p, _ in outcomes)
            if any(p < 0 for p, _ in outcomes) or not 0.0 < total_p <= 1.0 + 1e-9:
                raise ValueError(f"invalid outcome probabilities for {o['name']}")
            ev = expected_value(outcomes)
            best = max(outcomes, key=lambda t: t[1])
            shift = 0.1
            # Sensitivity: shift the best outcome's probability by +/-10 points.
            ev_up = expected_value([(min(p + shift, 1.0) if (p, v) == best else p, v)
                                    for p, v in outcomes])
            ev_down = expected_value([(max(p - shift, 0.0) if (p, v) == best else p, v)
                                      for p, v in outcomes])
            rows.append({"name": o["name"], "ev": ev, "ev_if_best_+10pp": ev_up,
                         "ev_if_best_-10pp": ev_down, "probability_mass": total_p})
        rows.sort(key=lambda r: r["ev"], reverse=True)
        return {"options": rows, "caveat": DECISION_SUPPORT_CAVEAT,
                "assumptions": ["Probabilities and values are caller estimates",
                                 "Outcomes within an option should sum to <= 1.0 probability mass"]}


# ---------------------------------------------------------------- row 58 --
# Risk of Ruin Analysis.

class RiskOfRuinAnalyzer:
    """Probability of losing so much that the endeavor cannot continue.
    Closed form for the unit-bet gambler's ruin; otherwise a seeded Monte
    Carlo over repeated trials. Refuses to call negative-edge positions
    safe."""

    def __init__(self, *, mc_trials: int = 5000, seed: int = 42) -> None:
        self.mc_trials = mc_trials
        self.seed = seed

    def analyze(self, *, capital: float, bet_size: float, win_prob: float,
                payoff_ratio: float = 1.0, trials: int = 100) -> dict[str, Any]:
        if capital <= 0 or bet_size <= 0 or bet_size > capital:
            raise ValueError("need 0 < bet_size <= capital")
        if not 0.0 <= win_prob <= 1.0 or payoff_ratio <= 0:
            raise ValueError("need 0<=win_prob<=1 and payoff_ratio>0")
        edge = win_prob * payoff_ratio - (1.0 - win_prob)
        units = capital / bet_size
        if abs(payoff_ratio - 1.0) < 1e-9 and win_prob != 0.5:
            # classic gambler's ruin, absorbing at 0
            if win_prob < 0.5:
                ruin = 1.0
            else:
                ruin = ((1.0 - win_prob) / win_prob) ** units
            method = "closed_form"
        else:
            rng = random.Random(self.seed)
            ruined = 0
            for _ in range(self.mc_trials):
                c = capital
                for _ in range(trials):
                    c += bet_size * payoff_ratio if rng.random() < win_prob else -bet_size
                    if c <= 0:
                        ruined += 1
                        break
            ruin = ruined / self.mc_trials
            method = "monte_carlo"
        verdict = ("danger" if ruin >= 0.25 or edge <= 0
                   else "caution" if ruin >= 0.05 else "acceptable")
        return {"ruin_probability": ruin, "edge_per_trial": edge, "units_at_risk": units,
                "method": method, "verdict": verdict, "caveat": DECISION_SUPPORT_CAVEAT,
                "assumptions": [f"{trials} trials per path" if method == "monte_carlo"
                                 else "Infinite-horizon gambler's ruin, even-money bets",
                                 f"Seeded simulation ({self.seed}, {self.mc_trials} paths)"
                                 if method == "monte_carlo" else "Fixed unit bets",
                                 "Negative edge can never be made safe by sizing"]}


# ---------------------------------------------------------------- row 59 --
# Kelly Criterion Bet Sizing.

class KellySizer:
    """Full-Kelly fraction f* = p - q/b, then a fractional recommendation
    (default half-Kelly) with the log-growth rate it implies. Never sizes
    a no-edge position above zero."""

    def __init__(self, *, fraction: float = 0.5, cap: float = 0.25) -> None:
        if not 0.0 < fraction <= 1.0 or not 0.0 < cap <= 1.0:
            raise ValueError("fraction and cap must be in (0, 1]")
        self.fraction = fraction
        self.cap = cap

    def size(self, *, win_prob: float, payoff_ratio: float) -> dict[str, Any]:
        if not 0.0 <= win_prob <= 1.0 or payoff_ratio <= 0:
            raise ValueError("need 0<=win_prob<=1 and payoff_ratio>0")
        full = kelly_criterion(win_prob, payoff_ratio)
        if full <= 0.0:
            return {"full_kelly": 0.0, "recommended": 0.0, "growth_rate": 0.0,
                    "note": "No edge: the Kelly fraction is zero; do not size this position",
                    "caveat": DECISION_SUPPORT_CAVEAT,
                    "assumptions": ["win_prob and payoff_ratio are estimates; sizing amplifies estimate error"]}
        recommended = min(full * self.fraction, self.cap)
        p, q, b = win_prob, 1.0 - win_prob, payoff_ratio
        growth = p * math.log(1 + recommended * b) + q * math.log(1 - recommended)
        return {"full_kelly": full, "recommended": recommended,
                "growth_rate": growth,
                "note": f"{self.fraction:.0%}-Kelly capped at {self.cap:.0%}",
                "caveat": DECISION_SUPPORT_CAVEAT,
                "assumptions": ["win_prob and payoff_ratio are estimates; Kelly is sensitive to their error",
                                 f"Fractional Kelly ({self.fraction:.0%}) trades growth for drawdown tolerance"]}
