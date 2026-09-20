"""Problem-solving, creativity, and self-regulation (spec 4.2.7, 4.2.8).

- ScratchpadManager: structured "thinking mode" - chain-of-thought,
  hypotheses, decision matrices; resumable across sessions.
- IdeationEngine: divergent generation + convergent constraint evaluation +
  forced analogy from random long-term-memory concepts.
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
from dataclasses import dataclass, field
from typing import Any

from .embeddings import DeterministicEmbedding, EmbeddingProvider, cosine_similarity
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
    """Divergent + convergent creativity (spec 4.2.7)."""

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)

    def diverge(self, prompt: str, *, count: int = 10, templates: list[str] | None = None) -> list[Idea]:
        """Divergent thinking: many raw candidates. In production the model
        runs at high temperature; the deterministic fallback combines prompt
        tokens across strategy frames so ideation works offline."""
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
            ideas.append(Idea(text=frame.format(t=prompt), metadata={"frame": i % len(frames)}))
        self.random.shuffle(ideas)
        return ideas

    def converge(self, ideas: list[Idea], constraints: dict[str, Any]) -> list[Idea]:
        """Convergent thinking: score ideas against weighted constraints.
        constraints: {criterion: weight}; an idea earns a criterion's weight
        when its metadata flags that criterion."""
        for idea in ideas:
            score = 0.0
            for criterion, weight in constraints.items():
                if idea.metadata.get(criterion):
                    score += float(weight)
            idea.score = score
        return sorted(ideas, key=lambda i: i.score, reverse=True)

    def forced_analogy(self, prompt: str, random_concepts: list[str]) -> list[Idea]:
        """Serendipity engineering: force unusual associations between the
        problem and random LTM concepts."""
        return [
            Idea(text=f"{prompt} <- analogy -> {concept}", metadata={"analogy": concept})
            for concept in random_concepts
        ]


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
        self._retros[retro.id] = retro
        text = " ".join(went_well + went_poorly + lessons)
        self._vectors[retro.id] = self.embedder.embed(text)
        return retro

    def lessons_for(self, situation: str, *, limit: int = 3) -> list[tuple[Retrospective, float]]:
        vector = self.embedder.embed(situation)
        scored = [
            (self._retros[rid], cosine_similarity(vector, vec))
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
    """Uncertainty expression (spec 4.2.8): quantify confidence, ask
    targeted questions, never guess recklessly on high-stakes matters."""

    def __init__(self, *, ask_threshold: float = 0.6, high_stakes_threshold: float = 0.85) -> None:
        self.ask_threshold = ask_threshold
        self.high_stakes_threshold = high_stakes_threshold

    def assess(
        self,
        confidence: float,
        *,
        rationale: str = "",
        gaps: list[str] | None = None,
        high_stakes: bool = False,
    ) -> Uncertainty:
        confidence = max(0.0, min(1.0, confidence))
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
