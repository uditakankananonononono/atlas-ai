"""Multitasking and concurrency (spec 4.2.6): one GCW instance manages
multiple independent task contexts, time-slicing between them with a
round-robin scheduler whose priority blends deadline proximity and
user-assigned importance. Each context owns a working-memory partition.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .schemas import TaskContext, TaskState

ACTIVE_STATES = {
    TaskState.PENDING, TaskState.PLANNING, TaskState.RUNNING, TaskState.RUMINATING,
}


class ContextScheduler:
    """Priority round-robin over active task contexts."""

    def __init__(self) -> None:
        self._contexts: dict[str, TaskContext] = {}
        self._cursor: int = 0

    def add(self, context: TaskContext) -> TaskContext:
        self._contexts[context.id] = context
        return context

    def remove(self, context_id: str) -> bool:
        return self._contexts.pop(context_id, None) is not None

    def get(self, context_id: str) -> TaskContext | None:
        return self._contexts.get(context_id)

    def priority(self, context: TaskContext, *, now: datetime | None = None) -> float:
        """Higher runs first: user importance dominates, deadline proximity
        adds urgency as the deadline approaches."""
        now = now or datetime.now(timezone.utc)
        importance_score = max(1, min(5, context.importance)) * 10.0
        urgency = 0.0
        if context.deadline is not None:
            seconds_left = (context.deadline - now).total_seconds()
            if seconds_left <= 0:
                urgency = 50.0
            else:
                urgency = min(50.0, 5000.0 / max(seconds_left / 60.0, 1.0))
        return importance_score + urgency

    def active(self) -> list[TaskContext]:
        return [c for c in self._contexts.values() if c.state in ACTIVE_STATES]

    def next_context(self, *, now: datetime | None = None) -> TaskContext | None:
        """Round-robin within the highest priority tier."""
        active = self.active()
        if not active:
            return None
        active.sort(key=lambda c: self.priority(c, now=now), reverse=True)
        top_priority = self.priority(active[0], now=now)
        tier = [c for c in active if self.priority(c, now=now) == top_priority]
        self._cursor = (self._cursor + 1) % len(tier)
        return tier[self._cursor]

    def order(self, *, now: datetime | None = None) -> list[TaskContext]:
        return sorted(self.active(), key=lambda c: self.priority(c, now=now), reverse=True)

    def cognitive_load(self) -> dict[str, float]:
        """Cognitive load balancing signal (features doc, category 1): share
        of attention each context claims, from importance and urgency."""
        active = self.active()
        if not active:
            return {}
        weights = {c.id: self.priority(c) for c in active}
        total = sum(weights.values()) or 1.0
        return {cid: round(w / total, 4) for cid, w in weights.items()}

    def __len__(self) -> int:
        return len(self._contexts)
