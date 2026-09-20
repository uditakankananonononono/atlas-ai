"""Executive Function & Meta-Cognition engines (features-doc rows 10-34).

Each row is an exact, typed capability over the M20 cognitive runtime -
not a generic prompt wrapper. Engines are deterministic and offline by
default; where a model would help in production it sits behind an injected
protocol. Nothing here self-modifies deployed code: the recursive
improvement loop rewrites only versioned, approval-gated prompt templates
and algorithm parameters inside its own registry.
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from statistics import mean, median
from typing import Any, Callable, Protocol, runtime_checkable
from uuid import uuid4

from .reasoning import hyperbolic_discount, minimax_regret, opportunity_cost
from .schemas import Episode, PlanNode, Risk, TaskContext, TaskState
from .embeddings import tokenize


def _uid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- row 10 --
# Recursive Self-Improvement Loop, bounded to reviewed prompts/algorithms.

class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


@dataclass
class PromptTemplate:
    """One versioned prompt/algorithm-parameter entry the loop may rewrite."""
    name: str
    content: str
    kind: str = "prompt"  # "prompt" | "algorithm_parameter"
    version: int = 1
    active: bool = True


@dataclass
class ImprovementProposal:
    id: str
    target_name: str
    current_content: str
    proposed_content: str
    evidence: dict[str, Any]
    expected_gain: float
    status: ProposalStatus = ProposalStatus.PROPOSED
    approval_id: str | None = None
    created_at: datetime = field(default_factory=_now)


class PromptRegistry:
    """The ONLY thing the improvement loop may rewrite. Versioned, auditable."""

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self.audit: list[dict[str, Any]] = []

    def register(self, template: PromptTemplate) -> PromptTemplate:
        existing = self._templates.get(template.name)
        if existing is not None:
            existing.active = False
            template.version = existing.version + 1
        self._templates[template.name] = template
        self.audit.append({"at": _now().isoformat(), "event": "register",
                           "name": template.name, "version": template.version})
        return template

    def get(self, name: str) -> PromptTemplate | None:
        return self._templates.get(name)

    def active(self) -> list[PromptTemplate]:
        return [t for t in self._templates.values() if t.active]


class ImprovementLoop:
    """Row 10: analyze own performance, rewrite prompts/algorithm params.

    Bounded: proposals never apply themselves. Applying requires an approved
    token from the approval gate (Module 0 in production), and only touches
    the PromptRegistry - never code, never safety rules, never tool specs.
    """

    FORBIDDEN_TARGETS = {"constitutional_rules", "safety_gate", "tool_specs", "approval_gate"}

    def __init__(self, registry: PromptRegistry) -> None:
        self.registry = registry
        self.proposals: dict[str, ImprovementProposal] = {}

    def analyze(
        self,
        *,
        tool_records: list[Any],
        episodes: list[Episode],
        calibration_error: float | None = None,
    ) -> dict[str, Any]:
        total_calls = len(tool_records)
        failures = sum(1 for r in tool_records if not getattr(r, "succeeded", True))
        succeeded = [e for e in episodes if e.outcome.value == "succeeded"]
        return {
            "tool_calls": total_calls,
            "tool_failure_rate": (failures / total_calls) if total_calls else 0.0,
            "episode_success_rate": (len(succeeded) / len(episodes)) if episodes else 0.0,
            "calibration_error": calibration_error,
        }

    def propose(self, target_name: str, proposed_content: str,
                *, evidence: dict[str, Any], expected_gain: float) -> ImprovementProposal:
        if target_name in self.FORBIDDEN_TARGETS:
            raise ValueError(f"target {target_name!r} is outside the improvement loop's authority")
        template = self.registry.get(target_name)
        if template is None:
            raise KeyError(f"unknown prompt template {target_name!r}")
        if not proposed_content.strip():
            raise ValueError("proposed content must not be empty")
        proposal = ImprovementProposal(
            id=_uid(), target_name=target_name,
            current_content=template.content, proposed_content=proposed_content,
            evidence=evidence, expected_gain=expected_gain,
        )
        self.proposals[proposal.id] = proposal
        return proposal

    def apply(self, proposal_id: str, *, approved: bool, approval_id: str | None = None) -> PromptTemplate:
        proposal = self.proposals[proposal_id]
        if not approved:
            proposal.status = ProposalStatus.REJECTED
            raise PermissionError("improvement proposal requires human approval before applying")
        proposal.status = ProposalStatus.APPLIED
        proposal.approval_id = approval_id
        template = self.registry.register(PromptTemplate(
            name=proposal.target_name, content=proposal.proposed_content,
            kind=self.registry.get(proposal.target_name).kind,  # type: ignore[union-attr]
        ))
        self.registry.audit.append({
            "at": _now().isoformat(), "event": "apply",
            "proposal_id": proposal_id, "approval_id": approval_id,
            "name": proposal.target_name, "version": template.version,
        })
        return template


# ---------------------------------------------------------------- row 11 --
# Meta-Learning Across Domains.

ACTION_ROLES: dict[str, str] = {
    "web_search": "gather", "reader": "gather", "search": "gather",
    "python_sandbox": "analyze", "analyze": "analyze",
    "write_document": "transform", "draft_email": "transform", "draft_document": "transform",
    "send_email": "deliver", "publish": "deliver", "deploy": "deliver",
}

_DOMAIN_STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with",
    "prepare", "write", "create", "make", "build", "research", "analyze",
    "send", "draft", "plan", "get", "do", "my", "our", "me",
}


@dataclass
class AbstractPattern:
    role_sequence: tuple[str, ...]
    domain_tokens: frozenset[str]
    problem_class: str
    successes: int
    source_episode_ids: list[str]


class MetaLearner:
    """Row 11: lift domain-specific episodes into domain-neutral patterns,
    then re-apply those patterns to unrelated domains."""

    def __init__(self) -> None:
        self.patterns: dict[tuple[str, ...], AbstractPattern] = {}

    @staticmethod
    def _domain_tokens(goal: str) -> frozenset[str]:
        return frozenset(t for t in tokenize(goal) if t not in _DOMAIN_STOPWORDS)

    def abstract(self, episode: Episode) -> AbstractPattern | None:
        roles = tuple(ACTION_ROLES.get(a.tool) for a in episode.actions)
        if len(roles) < 2 or any(r is None for r in roles):
            return None
        key = tuple(r for r in roles if r)
        domains = self._domain_tokens(episode.goal)
        existing = self.patterns.get(key)
        if existing is not None:
            existing.successes += 1
            existing.source_episode_ids.append(episode.id)
            existing.domain_tokens = existing.domain_tokens | domains
            return existing
        pattern = AbstractPattern(
            role_sequence=key, domain_tokens=domains,
            problem_class=" -> ".join(key), successes=1,
            source_episode_ids=[episode.id],
        )
        self.patterns[key] = pattern
        return pattern

    def transfer(self, goal: str) -> list[dict[str, Any]]:
        """Find patterns whose domain tokens do NOT overlap the new goal's
        domain: genuine cross-domain transfer, ranked by successes."""
        goal_domains = self._domain_tokens(goal)
        transferred = []
        for pattern in self.patterns.values():
            overlap = goal_domains & pattern.domain_tokens
            if overlap:
                continue  # same domain: not meta-learning
            foreign = sorted(pattern.domain_tokens)[:3]
            transferred.append({
                "role_sequence": list(pattern.role_sequence),
                "learned_in_domains": foreign,
                "successes": pattern.successes,
                "suggested_skeleton": [
                    f"{role} (adapted to {sorted(goal_domains)[:1] or ['this domain']})"
                    for role in pattern.role_sequence
                ],
            })
        transferred.sort(key=lambda t: t["successes"], reverse=True)
        return transferred


# ---------------------------------------------------------------- row 12 --
# Cognitive Load Balancing.

def estimate_complexity(context: TaskContext) -> float:
    """Complexity from plan size and risk mix."""
    if not context.plan:
        return 1.0
    risk_weight = {Risk.READ: 1.0, Risk.REVERSIBLE: 1.5, Risk.EXTERNAL: 2.0, Risk.IRREVERSIBLE: 3.0}
    return sum(risk_weight.get(n.risk, 1.0) for n in context.plan)


class LoadBalancer:
    """Row 12: allocate a finite deliberation budget across parallel tasks
    by complexity and deadline pressure."""

    def allocate(
        self, contexts: list[TaskContext], *, total_ticks: float,
        now: datetime | None = None,
    ) -> dict[str, float]:
        now = now or _now()
        active = [c for c in contexts if c.state in (
            TaskState.PENDING, TaskState.PLANNING, TaskState.RUNNING, TaskState.RUMINATING,
        )]
        if not active or total_ticks <= 0:
            return {}
        weights: dict[str, float] = {}
        for ctx in active:
            complexity = estimate_complexity(ctx)
            urgency = 1.0
            if ctx.deadline is not None:
                minutes_left = max(1.0, (ctx.deadline - now).total_seconds() / 60.0)
                urgency = 1.0 + min(4.0, 240.0 / minutes_left)
            weights[ctx.id] = complexity * urgency * max(1, ctx.importance)
        total = sum(weights.values()) or 1.0
        return {cid: round(total_ticks * w / total, 3) for cid, w in weights.items()}


# ---------------------------------------------------------------- row 13 --
# Epistemic Humility Calibration.

@dataclass
class Claim:
    id: str
    text: str
    confidence: float
    evidence_count: int
    flagged: bool
    flag_reason: str
    resolved: bool = False
    correct: bool | None = None
    created_at: datetime = field(default_factory=_now)


class CalibrationEngine:
    """Row 13: estimate knowledge boundaries, flag overconfident claims,
    and shrink reported confidence toward observed accuracy."""

    def __init__(self, *, max_confidence_without_evidence: float = 0.55) -> None:
        self.max_confidence_without_evidence = max_confidence_without_evidence
        self.claims: dict[str, Claim] = {}

    def _confidence_ceiling(self, evidence_count: int) -> float:
        return min(0.97, self.max_confidence_without_evidence + 0.14 * max(0, evidence_count))

    def assess_claim(self, text: str, confidence: float, *, evidence_count: int = 0) -> Claim:
        ceiling = self._confidence_ceiling(evidence_count)
        flagged = confidence > ceiling
        reason = ""
        if flagged:
            reason = (f"confidence {confidence:.2f} exceeds evidence-supported ceiling "
                      f"{ceiling:.2f} (evidence_count={evidence_count})")
        claim = Claim(id=_uid(), text=text, confidence=confidence,
                      evidence_count=evidence_count, flagged=flagged, flag_reason=reason)
        self.claims[claim.id] = claim
        return claim

    def resolve(self, claim_id: str, correct: bool) -> Claim:
        claim = self.claims[claim_id]
        claim.resolved = True
        claim.correct = correct
        return claim

    def calibration_curve(self, *, bins: int = 5) -> list[dict[str, float]]:
        resolved = [c for c in self.claims.values() if c.resolved]
        out = []
        for i in range(bins):
            lo, hi = i / bins, (i + 1) / bins
            bucket = [c for c in resolved if lo <= c.confidence < hi or (i == bins - 1 and c.confidence == 1.0)]
            if bucket:
                out.append({
                    "bin_midpoint": (lo + hi) / 2,
                    "mean_confidence": mean(c.confidence for c in bucket),
                    "observed_accuracy": mean(1.0 if c.correct else 0.0 for c in bucket),
                    "count": float(len(bucket)),
                })
        return out

    def calibration_error(self) -> float | None:
        curve = self.calibration_curve()
        if not curve:
            return None
        total = sum(b["count"] for b in curve)
        return sum(
            b["count"] * abs(b["mean_confidence"] - b["observed_accuracy"]) for b in curve
        ) / total

    def adjusted_confidence(self, raw_confidence: float) -> float:
        """Shrink toward observed accuracy; identity when no history."""
        resolved = [c for c in self.claims.values() if c.resolved]
        if len(resolved) < 5:
            return raw_confidence
        observed = mean(1.0 if c.correct else 0.0 for c in resolved)
        return max(0.0, min(1.0, 0.5 * raw_confidence + 0.5 * observed))


# ---------------------------------------------------------------- row 14 --
# Counterfactual Reasoning Engine.

@runtime_checkable
class OutcomeModel(Protocol):
    def estimate(self, action_description: str, risk: Risk) -> float: ...


class HeuristicOutcomeModel:
    """Default counterfactual estimator: success odds fall with risk tier."""

    BASE = {Risk.READ: 0.9, Risk.REVERSIBLE: 0.75, Risk.EXTERNAL: 0.55, Risk.IRREVERSIBLE: 0.4}

    def estimate(self, action_description: str, risk: Risk) -> float:
        return self.BASE.get(risk, 0.5)


class CounterfactualEngine:
    """Row 14: simulate alternative histories over a finished episode."""

    def __init__(self, outcome_model: OutcomeModel | None = None) -> None:
        self.outcome_model = outcome_model or HeuristicOutcomeModel()

    def simulate(
        self,
        episode: Episode,
        alternatives: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """alternatives: [{replaces_step: int, action: str, risk: str}].
        Returns per-alternative estimated outcome vs. the actual path."""
        actual_success = episode.outcome.value == "succeeded"
        results = []
        for alt in alternatives:
            risk = Risk(alt.get("risk", Risk.REVERSIBLE.value))
            estimated = self.outcome_model.estimate(str(alt.get("action", "")), risk)
            results.append({
                "replaces_step": alt.get("replaces_step"),
                "alternative_action": alt.get("action"),
                "estimated_success_probability": round(estimated, 3),
                "actual_outcome_succeeded": actual_success,
                "lesson": (
                    f"alternative {alt.get('action')!r} had estimated success "
                    f"{estimated:.0%} vs actual {'success' if actual_success else 'failure'}"
                ),
            })
        best = max(results, key=lambda r: r["estimated_success_probability"], default=None)
        return {
            "episode_id": episode.id,
            "actual_outcome": episode.outcome.value,
            "alternatives": results,
            "best_alternative": best,
        }


# ---------------------------------------------------------------- row 15 --
# Temporal Discounting Optimization.

class TemporalTradeoffs:
    """Row 15: hyperbolic discounting tailored to the user's own k."""

    def __init__(self, k: float = 0.02) -> None:
        self.k = k

    def compare(self, *, immediate_value: float, delayed_value: float,
                delay_days: float, k: float | None = None) -> dict[str, Any]:
        k = self.k if k is None else k
        discounted = hyperbolic_discount(delayed_value, delay_days, k)
        choice = "delayed" if discounted > immediate_value else "immediate"
        indifference_k = (delayed_value / immediate_value - 1.0) / delay_days if delay_days > 0 and immediate_value > 0 else None
        return {
            "choice": choice,
            "discounted_delayed_value": round(discounted, 4),
            "immediate_value": immediate_value,
            "k": k,
            "indifference_k": (round(indifference_k, 6) if indifference_k is not None else None),
        }

    def calibrate(self, observations: list[dict[str, Any]]) -> float:
        """Fit k from observed choices: [(immediate, delayed, delay_days, chose_delayed)]."""
        if not observations:
            return self.k
        best_k, best_err = self.k, float("inf")
        for candidate in [x / 1000.0 for x in range(0, 501)]:
            err = 0.0
            for obs in observations:
                discounted = hyperbolic_discount(obs["delayed"], obs["delay_days"], candidate)
                predicted_delayed = discounted > obs["immediate"]
                err += 0.0 if predicted_delayed == bool(obs["chose_delayed"]) else 1.0
            if err < best_err:
                best_k, best_err = candidate, err
        self.k = best_k
        return self.k


# ---------------------------------------------------------------- row 16 --
# Attention Residue Management.

@dataclass
class ResidueReport:
    from_partition: str
    to_partition: str
    cleared_count: int
    carried: list[str]


class AttentionResidueManager:
    """Row 16: clean context switches - wipe residue, carry only what is
    deliberately above the carry-over threshold."""

    def __init__(self, carry_over_threshold: float = 0.85) -> None:
        self.carry_over_threshold = carry_over_threshold

    def switch(self, working_memory: Any, *, from_partition: str,
               to_partition: str, active_goal: str = "") -> ResidueReport:
        """Carry-over is judged by the chunk's attention in the OLD context
        (what was highly attended there), then the old partition is wiped."""
        carried: list[str] = []
        if to_partition:
            for chunk in working_memory.focused(partition=from_partition):
                if chunk.attention_score >= self.carry_over_threshold:
                    from .schemas import MemoryChunk
                    working_memory.put(MemoryChunk(
                        type=chunk.type,
                        content=f"[carry-over] {chunk.content}",
                        confidence=chunk.confidence, source="attention-residue-carry",
                        salience=chunk.salience,
                    ), active_goal=active_goal, partition=to_partition)
                    carried.append(chunk.content)
        cleared = working_memory.clear_partition(from_partition)
        return ResidueReport(from_partition=from_partition, to_partition=to_partition,
                             cleared_count=cleared, carried=carried)


# ---------------------------------------------------------------- row 17 --
# Flow State Induction.

class FlowZone(str, Enum):
    APATHY = "apathy"
    BOREDOM = "boredom"
    FLOW = "flow"
    ANXIETY = "anxiety"


class FlowStateManager:
    """Row 17: challenge-skill balance, and work structuring to hold flow."""

    def assess(self, *, challenge: float, skill: float) -> dict[str, Any]:
        for name, v in (("challenge", challenge), ("skill", skill)):
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        delta = challenge - skill
        if challenge < 0.2 and skill < 0.2:
            zone = FlowZone.APATHY
        elif abs(delta) <= 0.15 and challenge >= 0.2:
            zone = FlowZone.FLOW
        elif delta > 0.15:
            zone = FlowZone.ANXIETY
        else:
            zone = FlowZone.BOREDOM
        return {"zone": zone.value, "delta": round(delta, 3),
                "advice": {
                    FlowZone.FLOW: "maintain current difficulty",
                    FlowZone.BOREDOM: "raise difficulty or add constraints",
                    FlowZone.ANXIETY: "split the task or build skill first",
                    FlowZone.APATHY: "find a meaningful entry point",
                }[zone]}

    def structure_work(self, tasks: list[dict[str, Any]], *, skill: float) -> list[dict[str, Any]]:
        """Order tasks so difficulty ramps through the flow channel: start at
        or just above current skill, then increase."""
        ordered = sorted(tasks, key=lambda t: abs(float(t.get("difficulty", 0.5)) - skill))
        result = []
        current_skill = skill
        for task in ordered:
            difficulty = float(task.get("difficulty", 0.5))
            zone = self.assess(challenge=difficulty, skill=current_skill)
            entry = {**task, "zone": zone["zone"]}
            if zone["zone"] == "anxiety":
                entry["recommendation"] = "split into smaller steps before scheduling"
            result.append(entry)
            current_skill = min(1.0, current_skill + 0.05)
        return result


# ---------------------------------------------------------------- row 18 --
# Cognitive Reframing.

_SETBACK_PATTERNS: list[tuple[str, list[str], str, list[str]]] = [
    ("technical", ["error", "bug", "failed", "exception", "crash", "test"],
     "the failure localizes exactly where the system is weakest",
     ["isolate the smallest failing case", "write a regression test for it",
      "fix, then re-run the full suite"]),
    ("planning", ["deadline", "late", "overrun", "estimate", "missed"],
     "the miss reveals the real cost curve of this kind of work",
     ["record the overrun ratio for future estimates",
      "identify the one step that consumed the slack",
      "re-plan with the corrected ratio"]),
    ("knowledge", ["unknown", "confused", "unclear", "dont know", "don't know", "uncertain"],
     "the gap is now mapped, which is the first step to closing it",
     ["name the exact unknown", "find one authoritative source",
      "schedule a focused learning block"]),
    ("rejection", ["rejected", "denied", "refused", "no"],
     "a rejection is information about fit, not a verdict on ability",
     ["extract every concrete reason given", "fix the strongest objection",
      "apply to the next opportunity with the improved version"]),
]


@dataclass
class Reframe:
    original: str
    category: str
    lesson: str
    actionable_steps: list[str]
    growth_statement: str


class ReframingEngine:
    """Row 18: setbacks -> learning opportunities with actionable steps."""

    def reframe(self, setback_description: str) -> Reframe:
        text = setback_description.lower()
        for category, markers, lesson, steps in _SETBACK_PATTERNS:
            if any(m in text for m in markers):
                return Reframe(
                    original=setback_description, category=category, lesson=lesson,
                    actionable_steps=steps,
                    growth_statement=f"Setback classified as {category}: {lesson}.",
                )
        return Reframe(
            original=setback_description, category="general",
            lesson="every failed attempt narrows the search space",
            actionable_steps=["write down exactly what was tried",
                              "change one variable", "try again with the new information"],
            growth_statement="Setback processed: the attempt produced usable information.",
        )


# ---------------------------------------------------------------- row 19 --
# Bias Detection & Mitigation.

_BIAS_MARKERS: dict[str, dict[str, Any]] = {
    "sunk_cost": {
        "markers": ["already invested", "come this far", "too much to quit", "sunk"],
        "mitigation": "evaluate only forward-looking costs and benefits",
    },
    "anchoring": {
        "markers": ["first offer", "initial estimate", "originally said", "list price"],
        "mitigation": "derive the value independently before comparing to the anchor",
    },
    "confirmation": {
        "markers": ["proves my point", "as i expected", "confirms what i thought", "right all along"],
        "mitigation": "actively search for disconfirming evidence before concluding",
    },
    "availability": {
        "markers": ["just saw", "recently heard", "in the news", "everyone is talking"],
        "mitigation": "check base rates instead of vivid recent examples",
    },
    "overconfidence": {
        "markers": ["definitely", "guaranteed", "cant fail", "can't fail", "100%", "no doubt"],
        "mitigation": "assign a calibrated probability and name what would prove it wrong",
    },
    "bandwagon": {
        "markers": ["everyone is doing", "trending", "viral", "all the top"],
        "mitigation": "evaluate the merits independent of popularity",
    },
    "survivorship": {
        "markers": ["successful people all", "winners always", "the secret of the rich"],
        "mitigation": "study the failures with the same traits before generalizing",
    },
}


@dataclass
class BiasFinding:
    bias: str
    evidence_span: str
    severity: float
    mitigation: str


class BiasDetector:
    """Row 19: marker-based bias scan over reasoning text or user input."""

    def scan(self, text: str) -> list[BiasFinding]:
        lowered = text.lower()
        findings = []
        for bias, spec in _BIAS_MARKERS.items():
            for marker in spec["markers"]:
                idx = lowered.find(marker)
                if idx >= 0:
                    start = max(0, idx - 30)
                    findings.append(BiasFinding(
                        bias=bias, evidence_span=text[start:idx + len(marker) + 30].strip(),
                        severity=0.6 if bias in ("overconfidence", "sunk_cost") else 0.4,
                        mitigation=spec["mitigation"],
                    ))
                    break
        return findings

    def scan_with_correction(self, text: str) -> dict[str, Any]:
        findings = self.scan(text)
        return {
            "findings": [f.__dict__ for f in findings],
            "corrected_prompt": (
                "Re-state the analysis addressing each mitigation: "
                + "; ".join(f.mitigation for f in findings)
            ) if findings else "",
        }


# ---------------------------------------------------------------- row 20 --
# Intuition Simulation.

@dataclass
class GutAnswer:
    answer: str
    confidence: float
    basis: str
    latency_class: str = "fast"


class IntuitionEngine:
    """Row 20: fast gut response (skill/semantic cache hit), then slow
    validation; disagreement defers to the slow path and is logged."""

    def __init__(self) -> None:
        self.validations: list[dict[str, Any]] = []

    def gut(self, question: str, *, skill_matches: list[Any], fact_hits: list[Any]) -> GutAnswer:
        if skill_matches:
            skill = skill_matches[0]
            return GutAnswer(
                answer=f"use the {skill.name} procedure",
                confidence=0.75, basis=f"matched skill {skill.name!r}",
            )
        if fact_hits:
            fact, score = fact_hits[0]
            return GutAnswer(answer=fact.content, confidence=min(0.7, 0.4 + score),
                             basis="top semantic memory hit")
        return GutAnswer(answer="", confidence=0.1, basis="no cached pattern")

    def validate(self, gut: GutAnswer, slow_answer_fn: Callable[[], str]) -> dict[str, Any]:
        slow = slow_answer_fn()
        agree = bool(gut.answer) and gut.answer.strip().lower() in slow.strip().lower()
        result = {
            "agree": agree,
            "final_answer": slow if (not agree or not gut.answer) else gut.answer,
            "note": ("gut contradicted or empty; slow reasoning wins"
                     if not agree else "gut validated by slow reasoning"),
            "gut_confidence": gut.confidence,
        }
        self.validations.append(result)
        return result


# ---------------------------------------------------------------- row 21 --
# Mental Model Versioning.

@dataclass
class WorldModel:
    name: str
    assumptions: dict[str, str]
    version: int = 1
    log_odds: float = 0.0
    updated_at: datetime = field(default_factory=_now)
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def posterior(self) -> float:
        return 1.0 / (1.0 + math.exp(-self.log_odds))


class WorldModelRegistry:
    """Row 21: multiple competing world models, updated by evidence."""

    def __init__(self) -> None:
        self.models: dict[str, WorldModel] = {}

    def register(self, name: str, assumptions: dict[str, str]) -> WorldModel:
        model = WorldModel(name=name, assumptions=dict(assumptions))
        self.models[name] = model
        return model

    def revise(self, name: str, new_assumptions: dict[str, str]) -> WorldModel:
        model = self.models[name]
        model.history.append({"version": model.version, "assumptions": dict(model.assumptions),
                              "log_odds": model.log_odds, "at": model.updated_at.isoformat()})
        model.assumptions = dict(new_assumptions)
        model.version += 1
        model.updated_at = _now()
        return model

    def apply_evidence(self, name: str, *, supported: bool, weight: float = 1.0) -> WorldModel:
        model = self.models[name]
        model.log_odds += (weight if supported else -weight)
        model.updated_at = _now()
        return model

    def current_best(self) -> WorldModel | None:
        if not self.models:
            return None
        return max(self.models.values(), key=lambda m: m.posterior)


# ---------------------------------------------------------------- row 22 --
# Goal Hierarchy Rewriting.

_VALUE_CONFLICT_MARKERS: dict[str, list[str]] = {
    "honesty": ["deceive", "lie", "fake", "mislead", "fabricate"],
    "privacy": ["share personal", "leak", "expose private", "sell data", "dox"],
    "safety": ["harm", "weapon", "dangerous", "injure"],
    "legality": ["pirate", "steal", "bypass paywall", "crack", "launder"],
    "budget": ["unlimited spend", "ignore cost", "money is no object"],
}


@dataclass
class GoalConflict:
    node_id: str
    node_title: str
    violated_value: str
    marker: str


class GoalHierarchyManager:
    """Row 22: detect sub-goals conflicting with terminal values and
    restructure the plan to resolve them."""

    def __init__(self, terminal_values: list[str] | None = None) -> None:
        self.terminal_values = [v.lower() for v in (terminal_values or ["honesty", "privacy", "legality"])]

    def check(self, plan: list[PlanNode]) -> list[GoalConflict]:
        conflicts = []
        for node in plan:
            text = f"{node.title} {node.arguments}".lower()
            for value in self.terminal_values:
                for marker in _VALUE_CONFLICT_MARKERS.get(value, []):
                    if marker in text:
                        conflicts.append(GoalConflict(
                            node_id=node.id, node_title=node.title,
                            violated_value=value, marker=marker,
                        ))
        return conflicts

    def restructure(self, plan: list[PlanNode]) -> dict[str, Any]:
        conflicts = self.check(plan)
        conflicted_ids = {c.node_id for c in conflicts}
        kept: list[PlanNode] = []
        for node in plan:
            if node.id in conflicted_ids:
                node.state = TaskState.CANCELLED
            elif any(dep in conflicted_ids for dep in node.depends_on):
                node.depends_on = [d for d in node.depends_on if d not in conflicted_ids]
                kept.append(node)
            else:
                kept.append(node)
        return {
            "cancelled": [c.node_title for c in conflicts],
            "conflicts": [c.__dict__ for c in conflicts],
            "remaining_steps": [n.title for n in kept],
            "restructured": bool(conflicts),
        }


# ---------------------------------------------------------------- row 23 --
# Decision Fatigue Prevention.

@dataclass
class RoutinePolicy:
    decision_type: str
    default_choice: str
    max_auto_per_day: int = 10
    used_today: int = 0
    last_reset: datetime = field(default_factory=_now)


class DecisionFatigueGuard:
    """Row 23: automate routine decisions under policy; escalate the rest."""

    def __init__(self) -> None:
        self.policies: dict[str, RoutinePolicy] = {}
        self.automated_total = 0

    def add_policy(self, policy: RoutinePolicy) -> RoutinePolicy:
        self.policies[policy.decision_type] = policy
        return policy

    def _refresh(self, policy: RoutinePolicy) -> None:
        if _now() - policy.last_reset > timedelta(days=1):
            policy.used_today = 0
            policy.last_reset = _now()

    def decide(self, decision_type: str, *, options: list[str],
               routine: bool = True, stakes: str = "low") -> dict[str, Any]:
        policy = self.policies.get(decision_type)
        if policy is not None:
            self._refresh(policy)
        if (policy is None or not routine or stakes != "low"
                or policy.default_choice not in options
                or policy.used_today >= policy.max_auto_per_day):
            return {"automated": False, "chosen": None,
                    "reason": "no policy / non-routine / high stakes / daily cap reached",
                    "escalated_options": options}
        policy.used_today += 1
        self.automated_total += 1
        return {"automated": True, "chosen": policy.default_choice,
                "reason": f"routine policy for {decision_type}",
                "capacity_preserved_estimate": self.automated_total}


# ------------------------------------------------------------- rows 24-26 --
# Regret / opportunity cost / sunk cost, typed over reasoning.py.

def project_regret(options: dict[str, dict[str, float]]) -> dict[str, Any]:
    """Row 24: full per-option regret projection across scenarios."""
    if not options:
        raise ValueError("options required")
    scenarios = list(next(iter(options.values())).keys())
    table: dict[str, dict[str, float]] = {}
    for name, payoffs in options.items():
        table[name] = {}
        for scenario in scenarios:
            best = max(o[scenario] for o in options.values())
            table[name][scenario] = best - payoffs[scenario]
    return {
        "regret_table": table,
        "max_regret": {name: max(r.values()) for name, r in table.items()},
        "minimax_choice": minimax_regret(options),
    }


def quantify_sacrifice(chosen: dict[str, float], alternatives: list[dict[str, float]]) -> dict[str, Any]:
    """Row 25: what is sacrificed with this choice, ranked."""
    ranked = sorted(alternatives, key=lambda a: a["value"], reverse=True)
    best = ranked[0] if ranked else None
    return {
        "chosen": chosen,
        "best_foregone": best,
        "opportunity_cost": opportunity_cost(chosen["value"], [a["value"] for a in alternatives]),
        "ranked_alternatives": ranked,
    }


def sunk_cost_choice(options: list[dict[str, float]]) -> dict[str, Any]:
    """Row 26: choose on forward value only; flag when sunk costs would have
    changed the answer."""
    if not options:
        raise ValueError("options required")
    forward_best = max(options, key=lambda o: o["forward_value"])
    naive_best = max(options, key=lambda o: o["forward_value"] + o.get("past_investment", 0.0))
    influenced = naive_best["name"] != forward_best["name"]
    return {
        "recommended": forward_best["name"],
        "sunk_cost_influenced": influenced,
        "explanation": (
            f"including past investment would have picked {naive_best['name']!r}; "
            f"forward-looking value alone picks {forward_best['name']!r}"
            if influenced else
            f"forward-looking value picks {forward_best['name']!r}; past investment is irrelevant"
        ),
    }


# ---------------------------------------------------------------- row 27 --
# Planning Horizon Flexibility.

class PlanningHorizonController:
    """Row 27: planning depth from uncertainty and time available."""

    def horizon(self, *, uncertainty: float, time_available_minutes: float) -> dict[str, Any]:
        if not 0.0 <= uncertainty <= 1.0:
            raise ValueError("uncertainty must be in [0, 1]")
        if time_available_minutes <= 0:
            raise ValueError("time must be positive")
        depth = int(round(1 + 4 * (1 - uncertainty) * min(1.0, time_available_minutes / 240.0)))
        max_steps = depth * 3
        replan = max(15.0, min(240.0, 30.0 + uncertainty * 180.0))
        return {
            "max_depth": max(1, min(5, depth)),
            "max_steps": max_steps,
            "replan_interval_minutes": replan,
            "rationale": (
                "high uncertainty -> shallow plan, frequent replans"
                if uncertainty > 0.6 else
                "low uncertainty + time -> deeper plan"
            ),
        }


# ---------------------------------------------------------------- row 28 --
# Abstraction Level Shifting.

class AbstractionShifter:
    """Row 28: the same plan at strategic, stream, and step levels."""

    def rollup(self, goal: str, plan: list[PlanNode], *, level: str) -> dict[str, Any]:
        if level == "strategy":
            return {"level": level, "goal": goal,
                    "summary": f"{len(plan)} steps, "
                               f"{len({n.tool for n in plan if n.tool})} tools",
                    "risk_profile": sorted({n.risk.value for n in plan})}
        if level == "streams":
            roots = [n for n in plan if not n.depends_on]
            return {"level": level, "goal": goal, "streams": [
                {"root": n.title,
                 "descendants": self._descendants(n, plan)}
                for n in roots
            ]}
        if level == "steps":
            return {"level": level, "goal": goal,
                    "steps": [{"title": n.title, "tool": n.tool,
                               "depends_on": n.depends_on, "risk": n.risk.value}
                              for n in plan]}
        raise ValueError(f"unknown level {level!r}")

    @staticmethod
    def _descendants(node: PlanNode, plan: list[PlanNode]) -> list[str]:
        children = [n for n in plan if node.id in n.depends_on]
        out = [c.title for c in children]
        for child in children:
            out.extend(AbstractionShifter._descendants(child, plan))
        return out


# ---------------------------------------------------------------- row 29 --
# Cognitive Diversity Simulation.

_PERSONAS: dict[str, dict[str, Any]] = {
    "analyst": {
        "focus": "evidence",
        "support_when": lambda p: p.get("evidence_count", 0) >= 3,
        "concern_when": lambda p: p.get("evidence_count", 0) < 2,
        "support": "the evidence base is adequate",
        "concern": "evidence is thin for the strength of the claim",
    },
    "skeptic": {
        "focus": "failure modes",
        "support_when": lambda p: p.get("risk", "high") in ("read", "reversible"),
        "concern_when": lambda p: p.get("risk", "high") in ("external", "irreversible", "high"),
        "support": "the blast radius of failure is small",
        "concern": "the irreversible parts have no rollback story",
    },
    "optimist": {
        "focus": "upside",
        "support_when": lambda p: p.get("upside", 0) >= 7,
        "concern_when": lambda p: p.get("upside", 0) < 4,
        "support": "the upside justifies the attempt",
        "concern": "even success may not be worth the effort",
    },
    "operator": {
        "focus": "executability",
        "support_when": lambda p: p.get("timeline_days", 999) <= 30,
        "concern_when": lambda p: p.get("timeline_days", 999) > 90,
        "support": "this can ship within the month",
        "concern": "the timeline is too long for the current capacity",
    },
    "guardian": {
        "focus": "values and safety",
        "support_when": lambda p: not p.get("externally_visible", False),
        "concern_when": lambda p: bool(p.get("externally_visible", False)),
        "support": "nothing leaves the building without review",
        "concern": "externally visible effects need explicit approval gating",
    },
}


@dataclass
class PerspectiveView:
    persona: str
    focus: str
    supports: list[str]
    concerns: list[str]
    score: float


class PerspectiveSimulator:
    """Row 29: evaluate one proposal through typed persona lenses."""

    def evaluate(self, proposal: dict[str, Any]) -> list[PerspectiveView]:
        views = []
        for persona, lens in _PERSONAS.items():
            supports = [lens["support"]] if lens["support_when"](proposal) else []
            concerns = [lens["concern"]] if lens["concern_when"](proposal) else []
            score = 0.5 + 0.25 * len(supports) - 0.25 * len(concerns)
            views.append(PerspectiveView(
                persona=persona, focus=lens["focus"],
                supports=supports, concerns=concerns, score=score,
            ))
        return views


# ------------------------------------------------------------- rows 30-31 --
# Devil's Advocate + Steel-manning.

@dataclass
class StressTestReport:
    claim: str
    assumption_attacks: list[dict[str, str]]
    evidence_gaps: list[str]
    alternative_explanations: list[str]
    residual_confidence: float


class DevilsAdvocate:
    """Row 30: systematically argue against a conclusion."""

    def stress_test(self, *, claim: str, assumptions: list[str],
                    evidence: list[str]) -> StressTestReport:
        attacks = [
            {"assumption": a,
             "attack": f"if '{a}' is false, the claim needs independent support",
             "test": f"find one observation that would disprove '{a}'"}
            for a in assumptions
        ]
        gaps = []
        if len(evidence) < len(assumptions):
            gaps.append(f"{len(assumptions) - len(evidence)} assumption(s) lack direct evidence")
        if not any(tokenize(e) for e in evidence):
            gaps.append("evidence entries carry no checkable content")
        tokens = [t for t in tokenize(claim) if len(t) > 4][:3]
        alternatives = [
            f"the observation is explained by an unrelated trend in {t}"
            for t in tokens
        ] or ["the observation is coincidence"]
        residual = max(0.05, 0.9 - 0.15 * len(attacks) - 0.2 * len(gaps) + 0.05 * len(evidence))
        return StressTestReport(
            claim=claim, assumption_attacks=attacks, evidence_gaps=gaps,
            alternative_explanations=alternatives, residual_confidence=round(residual, 3),
        )


@dataclass
class SteelmanReport:
    opposing_position: str
    strongest_form: str
    supporting_points: list[str]
    concessions: list[str]
    response_skeleton: list[str]


class SteelmanEngine:
    """Row 31: construct the strongest opposing case before responding."""

    def strengthen(self, *, opposing_position: str,
                   known_facts: list[str]) -> SteelmanReport:
        pos_tokens = set(tokenize(opposing_position))
        supporting = [
            f for f in known_facts
            if len(set(tokenize(f)) & pos_tokens) >= max(1, len(pos_tokens) // 3)
        ]
        strongest = (
            f"Taken at its best: {opposing_position} - argued with the "
            f"{len(supporting)} most aligned known facts, not the weakest version."
        )
        return SteelmanReport(
            opposing_position=opposing_position,
            strongest_form=strongest,
            supporting_points=supporting,
            concessions=[f"grant: {s}" for s in supporting[:2]],
            response_skeleton=[
                "restate the strongest form accurately",
                "concede the supporting points that hold",
                "show where the strong form still falls short",
            ],
        )


# ---------------------------------------------------------------- row 32 --
# Epistemic Calendar.

@dataclass
class BeliefReview:
    belief_id: str
    content: str
    formed_at: datetime
    review_interval_days: int
    last_reviewed_at: datetime
    times_reviewed: int = 0

    def next_review(self) -> datetime:
        return self.last_reviewed_at + timedelta(days=self.review_interval_days)


class EpistemicCalendar:
    """Row 32: beliefs carry formation dates and periodic review schedules."""

    def __init__(self) -> None:
        self.beliefs: dict[str, BeliefReview] = {}

    def register(self, content: str, *, formed_at: datetime | None = None,
                 review_interval_days: int = 90) -> BeliefReview:
        entry = BeliefReview(
            belief_id=_uid(), content=content,
            formed_at=formed_at or _now(),
            review_interval_days=review_interval_days,
            last_reviewed_at=formed_at or _now(),
        )
        self.beliefs[entry.belief_id] = entry
        return entry

    def due(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or _now()
        due_list = [
            {"belief_id": b.belief_id, "content": b.content,
             "next_review": b.next_review().isoformat(),
             "overdue_days": max(0.0, (now - b.next_review()).total_seconds() / 86400.0)}
            for b in self.beliefs.values() if b.next_review() <= now
        ]
        due_list.sort(key=lambda d: d["overdue_days"], reverse=True)
        return due_list

    def mark_reviewed(self, belief_id: str, *, now: datetime | None = None) -> BeliefReview:
        entry = self.beliefs[belief_id]
        entry.last_reviewed_at = now or _now()
        entry.times_reviewed += 1
        return entry


# ---------------------------------------------------------------- row 33 --
# Knowledge Decay Modeling (extends semantic_memory's freshness model).

KIND_DECAY_DEFAULTS: dict[str, float] = {
    "fact": 0.5, "price": 2.0, "deadline": 3.0, "contact": 1.0,
    "concept": 0.1, "opinion": 1.0, "regulation": 0.8, "tool_version": 1.5,
}


class KnowledgeDecayModeler:
    """Row 33: predict which facts will be outdated and schedule refreshes."""

    def default_decay(self, kind: str) -> float:
        return KIND_DECAY_DEFAULTS.get(kind, 0.5)

    def forecast(self, semantic_memory: Any, *, days_ahead: float = 30.0,
                 threshold: float = 0.5) -> list[dict[str, Any]]:
        now = _now()
        future = now + timedelta(days=days_ahead)
        forecasts = []
        for fact in semantic_memory._facts.values():
            decay = fact.decay_rate or self.default_decay(fact.kind)
            if decay <= 0:
                continue
            current = fact.confidence * (0.5 ** (decay * max(0.0, (now - fact.last_confirmed_at).total_seconds() / 86400.0) / 30.0))
            predicted = fact.confidence * (0.5 ** (decay * max(0.0, (future - fact.last_confirmed_at).total_seconds() / 86400.0) / 30.0))
            if predicted < threshold:
                forecasts.append({
                    "fact_id": fact.id, "content": fact.content, "kind": fact.kind,
                    "current_freshness": round(current, 3),
                    "predicted_freshness": round(predicted, 3),
                    "refresh_by": (fact.last_confirmed_at + timedelta(days=30.0 / decay)).isoformat(),
                })
        forecasts.sort(key=lambda f: f["predicted_freshness"])
        return forecasts


# ---------------------------------------------------------------- row 34 --
# Curiosity-Driven Exploration.

@dataclass
class ExplorationItem:
    gap: str
    frequency: int
    expected_learning_value: float
    allocated_budget: float = 0.0


class CuriosityEngine:
    """Row 34: detect knowledge gaps and spend idle budget investigating
    them even without immediate utility."""

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)
        self._gap_counts: dict[str, int] = {}

    def detect_gaps(self, text: str, semantic_memory: Any) -> list[str]:
        """Tokens that appear in goals but nowhere in semantic memory."""
        known = set()
        for fact in semantic_memory._facts.values():
            known |= set(tokenize(fact.content))
        gaps = []
        for token in set(tokenize(text)):
            if len(token) < 5 or token in known or token in _DOMAIN_STOPWORDS:
                continue
            self._gap_counts[token] = self._gap_counts.get(token, 0) + 1
            gaps.append(token)
        return gaps

    def allocate(self, *, idle_budget: float, gaps: list[str] | None = None) -> list[ExplorationItem]:
        pool = gaps or list(self._gap_counts)
        items = []
        for gap in pool:
            freq = self._gap_counts.get(gap, 1)
            items.append(ExplorationItem(
                gap=gap, frequency=freq,
                expected_learning_value=round(min(1.0, 0.3 + 0.2 * freq), 3),
            ))
        items.sort(key=lambda i: i.expected_learning_value, reverse=True)
        remaining = max(0.0, idle_budget)
        for item in items:
            if remaining <= 0:
                break
            share = min(remaining, idle_budget * item.expected_learning_value /
                        max(1e-9, sum(i.expected_learning_value for i in items)))
            item.allocated_budget = round(share, 3)
            remaining -= share
        return items

    def serendipity_pull(self, semantic_memory: Any, *, count: int = 3) -> list[str]:
        facts = list(semantic_memory._facts.values())
        if not facts:
            return []
        return [f.content for f in self.random.sample(facts, min(count, len(facts)))]
