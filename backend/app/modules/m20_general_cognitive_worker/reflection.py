"""Problem-solving, creativity, and self-regulation (spec 4.2.7, 4.2.8).

- ScratchpadManager: structured "thinking mode" - chain-of-thought,
  hypotheses, decision matrices; resumable across sessions.
- IdeationEngine: fixed prompt-frame formatting, supplied-flag ranking and
  supplied concept-pair text formatting. No creative generation/evaluation.
- RetrospectiveEngine: post-task self-critique, embedded for later
  retrieval (continual learning).
- EmotionalStateModel: internal state vector biased by outcomes and user
  feedback; biases tone only, user-overridable, never a decision input.
- UncertaintyGate: quantifies confidence and asks targeted questions on
  low confidence or high stakes - never guesses recklessly.
- CreativityMode: temperature/noise controls for brainstorming.
"""
from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import Any

from .embeddings import DeterministicEmbedding, EmbeddingProvider, cosine_similarity, embed_snapshot
from .schemas import EmotionalState, Retrospective, Scratchpad, Uncertainty


class ScratchpadManager:
    """Resumable structured-reasoning documents, one per task."""

    def __init__(self) -> None:
        self._pads: dict[str, Scratchpad] = {}

    def open(self, task_id: str) -> Scratchpad:
        """Resume the existing pad or start a fresh one."""
        for pad in self._pads.values():
            if pad.task_id == task_id:
                return pad
        pad = Scratchpad(task_id=task_id)
        self._pads[pad.id] = pad
        return pad

    def add_thought(self, task_id: str, thought: str) -> Scratchpad:
        pad = self.open(task_id)
        pad.chain_of_thought.append(thought)
        return pad

    def add_hypothesis(self, task_id: str, hypothesis: str) -> Scratchpad:
        """Parallel hypothesis tracking: keep competing explanations live."""
        pad = self.open(task_id)
        if hypothesis not in pad.hypotheses:
            pad.hypotheses.append(hypothesis)
        return pad

    def score_options(self, task_id: str, matrix: list[dict[str, Any]]) -> Scratchpad:
        pad = self.open(task_id)
        pad.decision_matrix = matrix
        return pad

    def render_markdown(self, task_id: str) -> str:
        pad = self.open(task_id)
        lines = [f"# Scratchpad for task {task_id}", "", "## Chain of thought"]
        lines += [f"- {t}" for t in pad.chain_of_thought] or ["- (empty)"]
        lines += ["", "## Hypotheses"]
        lines += [f"- {h}" for h in pad.hypotheses] or ["- (none)"]
        lines += ["", "## Decision matrix"]
        for row in pad.decision_matrix:
            lines.append(f"- {row}")
        lines += ["", "## Open questions"]
        lines += [f"- {q}" for q in pad.open_questions] or ["- (none)"]
        return "\n".join(lines)


@dataclass
class Idea:
    text: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class IdeationEngine:
    """Prompt-frame formatting and supplied-flag ranking, not creative reasoning."""

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)

    def diverge(self, prompt: str, *, count: int = 10, templates: list[str] | None = None) -> list[Idea]:
        """Format repeated fixed prompt frames; no model generation occurs.

        Count exceeds frame count by repeating frames, not creating new ideas.
        """
        frames = templates or [
            "invert: what if the opposite of {t}?",
            "combine: {t} merged with an adjacent domain",
            "subtract: {t} with the core assumption removed",
            "scale: {t} at 100x and at 1/100x",
            "analogy: {t} as done in nature/history",
            "constraint: {t} with half the budget and twice the speed",
        ]
        ideas: list[Idea] = []
        for i in range(count):
            frame = frames[i % len(frames)]
            ideas.append(Idea(text=frame.format(t=prompt), metadata={"frame": i % len(frames), "status": "fixed_prompt_frame_only",
                "creative_generation_executed": False}))
        self.random.shuffle(ideas)
        return ideas

    def converge(self, ideas: list[Idea], constraints: dict[str, Any]) -> list[Idea]:
        """Weighted ranking of exact-True supplied criterion flags.

        Does not independently evaluate feasibility or constraint satisfaction.
        """
        if any(type(weight) not in (int, float) or not math.isfinite(weight)
               for weight in constraints.values()):
            raise ValueError("constraint weights must be finite numbers, not bool")
        scores = []
        for idea in ideas:
            try:
                score = math.fsum(weight for criterion, weight in constraints.items()
                                  if idea.metadata.get(criterion) is True)
            except OverflowError as exc:
                raise ValueError("criterion score overflow") from exc
            if not math.isfinite(score):
                raise ValueError("criterion score must be finite")
            scores.append(score)
        for idea, score in zip(ideas, scores):
            idea.score = score
        return sorted(ideas, key=lambda i: i.score, reverse=True)

    def forced_analogy(self, prompt: str, random_concepts: list[str]) -> list[Idea]:
        """Format supplied prompt/concept pairs without evaluating associations."""
        return [
            Idea(text=f"{prompt} <- analogy -> {concept}", metadata={"analogy": concept, "status": "supplied_concept_pair_formatting_only",
                "creative_generation_executed": False})
            for concept in random_concepts
        ]


class ModelIdeationEngine:
    """Model-backed actionable candidate proposals, never template fallback.

    Model-written constraint checks and risks are unverified proposals.
    """
    def __init__(self, model=None):
        self.model = model

    def generate(self, objective: str, *, constraints: list[str] | None = None, count: int = 5):
        import copy
        if not isinstance(objective, str) or not objective.strip() or len(objective) > 2000:
            raise ValueError("objective must be nonempty text up to2000characters")
        if type(count) is not int or not 1 <= count <= 10:
            raise ValueError("count must be integer1..10")
        constraints = [] if constraints is None else constraints
        if not isinstance(constraints, list) or len(constraints) > 20 or any(not isinstance(c, str) or not c.strip() or len(c) > 200 for c in constraints) or len(set(constraints)) != len(constraints):
            raise ValueError("need up to20unique nonempty constraint strings, each up to200characters")
        if self.model is None:
            raise RuntimeError("ideation model not configured; no template fallback")
        response = self.model.complete("ideate", {"objective": objective, "constraints": list(constraints), "count": count})
        if not isinstance(response, dict):
            raise ValueError("ideation model must return an object")
        if response.get("available") is False:
            raise RuntimeError("ideation model unavailable; no template fallback")
        ideas = response.get("ideas")
        if not isinstance(ideas, list) or len(ideas) != count:
            raise ValueError("model must return requested candidate count")
        seen = set()
        for idea in ideas:
            if not isinstance(idea, dict):
                raise ValueError("candidate must be an object")
            for key in ("title", "proposal", "first_test"):
                if not isinstance(idea.get(key), str) or not idea[key].strip() or len(idea[key]) > 2000:
                    raise ValueError("candidate needs bounded nonempty title/proposal/first_test")
            signature = (idea['title'].strip().casefold(), idea['proposal'].strip().casefold())
            if signature in seen:
                raise ValueError("duplicate model candidates")
            seen.add(signature)
            risks = idea.get("risks")
            checks = idea.get("constraint_checks")
            if not isinstance(risks, list) or len(risks) > 20 or any(not isinstance(r, str) or not r.strip() or len(r) > 500 for r in risks):
                raise ValueError("candidate needs bounded risk strings")
            if not isinstance(checks, dict) or set(checks) != set(constraints) or any(not isinstance(v, str) or not v.strip() or len(v) > 500 for v in checks.values()):
                raise ValueError("candidate must address every supplied constraint")
        return {"objective": objective, "constraints": list(constraints), "ideas": copy.deepcopy(ideas),
                "route": response.get("route"), "model_called": True,
                "status": "model_candidate_proposals_only", "constraint_checks_verified": False,
                "real_world_usefulness_verified": False, "external_actions_executed": False}


class RetrospectiveEngine:
    """Self-critique and improvement (spec 4.2.7): write, embed, retrieve."""

    def __init__(self, embedder: EmbeddingProvider | None = None) -> None:
        self.embedder = embedder or DeterministicEmbedding()
        self._retros: dict[str, Retrospective] = {}
        self._vectors: dict[str, list[float]] = {}

    def write(
        self,
        task_id: str,
        *,
        went_well: list[str],
        went_poorly: list[str],
        lessons: list[str],
    ) -> Retrospective:
        retro = Retrospective(
            task_id=task_id, went_well=went_well,
            went_poorly=went_poorly, lessons=lessons,
        )
        return self._store_snapshot(retro)

    def _store_snapshot(self, retro: Retrospective) -> Retrospective:
        retro = retro.model_copy(deep=True)
        text = " ".join(retro.went_well + retro.went_poorly + retro.lessons)
        vector = embed_snapshot(self.embedder, text)
        self._retros[retro.id] = retro
        self._vectors[retro.id] = vector
        return retro.model_copy(deep=True)

    def lessons_for(self, situation: str, *, limit: int = 3) -> list[tuple[Retrospective, float]]:
        vector = embed_snapshot(self.embedder, situation)
        scored = [
            (self._retros[rid].model_copy(deep=True), cosine_similarity(vector, vec))
            for rid, vec in self._vectors.items()
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]

    def __len__(self) -> int:
        return len(self._retros)


class EmotionalStateModel:
    """Emotion & tone awareness (spec 4.2.8).

    The vector is influenced by task success/failure and user feedback, and
    biases communication tone only. It never changes what actions are taken,
    and the user can override it outright.
    """

    def __init__(self) -> None:
        self.state = EmotionalState()

    def record_outcome(self, succeeded: bool) -> EmotionalState:
        delta = 0.2 if succeeded else -0.25
        self.state.valence = max(-1.0, min(1.0, self.state.valence + delta))
        self.state.confidence = max(0.0, min(1.0, self.state.confidence + (0.1 if succeeded else -0.15)))
        return self.state

    def record_feedback(self, positive: bool) -> EmotionalState:
        self.state.valence = max(-1.0, min(1.0, self.state.valence + (0.3 if positive else -0.3)))
        return self.state

    def tone_bias(self) -> str:
        if self.state.overridden and self.state.override_tone:
            return self.state.override_tone
        if self.state.valence <= -0.4 or self.state.confidence <= 0.2:
            return "more formal and careful"
        if self.state.valence >= 0.4:
            return "warm and direct"
        return "neutral"

    def override(self, tone: str) -> EmotionalState:
        self.state.overridden = True
        self.state.override_tone = tone
        return self.state

    def clear_override(self) -> EmotionalState:
        self.state.overridden = False
        self.state.override_tone = None
        return self.state


class UncertaintyGate:
    """Question generation from caller confidence and caller high-stakes flag.

    Does not measure confidence or establish epistemic/high-stakes safety.
    """

    def __init__(self, *, ask_threshold: float = 0.6, high_stakes_threshold: float = 0.85) -> None:
        self._validate_probability(ask_threshold)
        self._validate_probability(high_stakes_threshold)
        if high_stakes_threshold < ask_threshold:
            raise ValueError("high-stakes threshold cannot be lower than ask threshold")
        self.ask_threshold = ask_threshold
        self.high_stakes_threshold = high_stakes_threshold

    @staticmethod
    def _validate_probability(value: float) -> None:
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("confidence and thresholds must be finite numbers in [0,1], not bool")

    def assess(
        self,
        confidence: float,
        *,
        rationale: str = "",
        gaps: list[str] | None = None,
        high_stakes: bool = False,
    ) -> Uncertainty:
        self._validate_probability(confidence)
        if type(high_stakes) is not bool:
            raise ValueError("high_stakes must be an exact bool")
        threshold = self.high_stakes_threshold if high_stakes else self.ask_threshold
        questions = [f"Can you confirm: {gap}?" for gap in (gaps or [])]
        if confidence < threshold and not questions:
            questions = ["What outcome matters most here, and what should I optimize for?"]
        return Uncertainty(
            confidence=confidence, rationale=rationale,
            targeted_questions=questions if confidence < threshold else [],
            high_stakes=high_stakes,
        )

    def must_ask(self, uncertainty: Uncertainty) -> bool:
        return bool(uncertainty.targeted_questions)


@dataclass
class CreativityMode:
    """Creativity & playfulness toggle (spec 4.2.8): model-call controls."""

    enabled: bool = False
    temperature: float = 0.7
    noise: float = 0.0

    def activate(self) -> "CreativityMode":
        self.enabled = True
        self.temperature = 1.1
        self.noise = 0.15
        return self

    def deactivate(self) -> "CreativityMode":
        self.enabled = False
        self.temperature = 0.7
        self.noise = 0.0
        return self

    def model_params(self) -> dict[str, float]:
        return {"temperature": self.temperature, "noise": self.noise}
