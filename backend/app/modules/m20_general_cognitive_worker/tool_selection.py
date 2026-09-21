"""Principled tool selection for the executive's Decide phase (rows M20-13,
M20-17).

The selector scores every registered tool for a plan step on four typed
components - capability-token match, embedding similarity with the tool
description, a risk-tier penalty, and a Beta(1,1) posterior over the tool's
historical success - and reports the decomposition plus an explicit
uncertainty margin. When the top two tools are statistically
indistinguishable the selector asks a targeted clarifying question instead
of guessing (row M20-30).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .embeddings import DeterministicEmbedding, EmbeddingProvider, cosine_similarity, tokenize
from .schemas import Risk
from .tools import ToolRegistry

RISK_PENALTY = {Risk.READ: 0.0, Risk.REVERSIBLE: 0.1, Risk.EXTERNAL: 0.25, Risk.IRREVERSIBLE: 0.45}


@dataclass
class ToolScore:
    """One candidate with its full score decomposition."""

    tool_name: str
    total: float
    capability_match: float
    description_similarity: float
    historical_success: float
    risk_penalty: float
    preconditions_met: bool
    missing_preconditions: list[str] = field(default_factory=list)


@dataclass
class ToolSelection:
    """Selection result with evaluation and uncertainty reporting."""

    chosen: ToolScore | None
    candidates: list[ToolScore]
    margin: float
    needs_clarification: bool
    clarifying_question: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "chosen": vars(self.chosen) if self.chosen else None,
            "candidates": [vars(c) for c in self.candidates],
            "margin": self.margin,
            "needs_clarification": self.needs_clarification,
            "clarifying_question": self.clarifying_question,
        }


class ToolSelector:
    """Ranks registry tools for a step description."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        embedder: EmbeddingProvider | None = None,
        ambiguity_margin: float = 0.08,
    ) -> None:
        self.registry = registry
        self.embedder = embedder or DeterministicEmbedding()
        self.ambiguity_margin = ambiguity_margin
        # Beta(1,1) posterior per tool: (successes, failures)
        self._history: dict[str, tuple[float, float]] = {}

    def record_outcome(self, tool_name: str, succeeded: bool) -> None:
        successes, failures = self._history.get(tool_name, (0.0, 0.0))
        if succeeded:
            successes += 1.0
        else:
            failures += 1.0
        self._history[tool_name] = (successes, failures)

    def historical_success(self, tool_name: str) -> float:
        successes, failures = self._history.get(tool_name, (0.0, 0.0))
        return (successes + 1.0) / (successes + failures + 2.0)

    def score_all(self, step_description: str, *, context: dict[str, Any] | None = None) -> list[ToolScore]:
        context = context or {}
        step_tokens = set(tokenize(step_description))
        step_vector = self.embedder.embed(step_description)
        scored: list[ToolScore] = []
        for tool in self.registry._tools.values():
            spec = tool.spec
            missing = tool.check_preconditions(context)
            capability_tokens = set(tokenize(" ".join(spec.capabilities) + " " + spec.name.replace("_", " ")))
            if step_tokens and capability_tokens:
                capability_match = len(step_tokens & capability_tokens) / len(step_tokens | capability_tokens)
            else:
                capability_match = 0.0
            description_similarity = max(
                0.0, cosine_similarity(step_vector, self.embedder.embed(spec.description))
            )
            risk_penalty = RISK_PENALTY.get(spec.risk, 0.2)
            historical = self.historical_success(spec.name)
            total = (
                0.45 * capability_match
                + 0.30 * description_similarity
                + 0.15 * historical
                + 0.10 * (1.0 - risk_penalty)
                - (0.5 if missing else 0.0)
            )
            scored.append(ToolScore(
                tool_name=spec.name, total=round(total, 4),
                capability_match=round(capability_match, 4),
                description_similarity=round(description_similarity, 4),
                historical_success=round(historical, 4),
                risk_penalty=risk_penalty,
                preconditions_met=not missing,
                missing_preconditions=missing,
            ))
        scored.sort(key=lambda s: s.total, reverse=True)
        return scored

    def select(self, step_description: str, *, context: dict[str, Any] | None = None) -> ToolSelection:
        scored = self.score_all(step_description, context=context)
        eligible = [s for s in scored if s.preconditions_met]
        if not eligible:
            question = ""
            if scored:
                missing = sorted({m for s in scored for m in s.missing_preconditions})
                question = f"no tool can run yet - enable: {', '.join(missing)}?"
            return ToolSelection(
                chosen=None, candidates=scored, margin=0.0,
                needs_clarification=True, clarifying_question=question,
            )
        margin = eligible[0].total - eligible[1].total if len(eligible) > 1 else 1.0
        ambiguous = margin < self.ambiguity_margin
        question = ""
        if ambiguous:
            question = (
                f"should this step use {eligible[0].tool_name} or {eligible[1].tool_name}? "
                f"scores are within {self.ambiguity_margin:.2f}"
            )
        return ToolSelection(
            chosen=None if ambiguous else eligible[0],
            candidates=scored, margin=round(margin, 4),
            needs_clarification=ambiguous, clarifying_question=question,
        )
