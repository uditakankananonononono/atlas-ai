"""Aggregate raw gap events into actionable CapabilityGap records."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .events import GapEventStore


@dataclass(frozen=True)
class CapabilityGap:
    module_slug: str
    signature: str
    occurrences: int
    kinds: tuple[str, ...]
    exemplars: tuple[Any, ...]
    detail: str
    first_seen: float
    last_seen: float
    severity: float  # occurrences weighted by recency, 0..1 scaled by caller

    @property
    def key(self) -> str:
        return f"{self.module_slug}:{self.signature}"


class GapDetector:
    """Groups events by signature and promotes recurring ones to gaps."""

    def __init__(self, store: GapEventStore, *, min_occurrences: int = 2) -> None:
        if min_occurrences < 1:
            raise ValueError("min_occurrences must be >= 1")
        self._store = store
        self._min = min_occurrences

    def detect(self, module_slug: str) -> list[CapabilityGap]:
        events = self._store.all(module_slug)
        groups: dict[str, list] = {}
        for ev in events:
            groups.setdefault(ev.signature, []).append(ev)
        gaps: list[CapabilityGap] = []
        now = time.time()
        for signature, group in groups.items():
            if len(group) < self._min:
                continue
            first = min(e.at for e in group)
            last = max(e.at for e in group)
            recency = 1.0 / (1.0 + max(0.0, now - last) / 86400.0)
            severity = min(1.0, (len(group) / (self._min * 10.0)) * (0.5 + 0.5 * recency))
            exemplars = tuple(e.exemplar for e in group if e.exemplar is not None)[:5]
            gaps.append(CapabilityGap(
                module_slug=module_slug, signature=signature,
                occurrences=len(group),
                kinds=tuple(sorted({e.kind for e in group})),
                exemplars=exemplars,
                detail=group[-1].detail, first_seen=first, last_seen=last,
                severity=round(severity, 4),
            ))
        return sorted(gaps, key=lambda g: (-g.severity, g.signature))
