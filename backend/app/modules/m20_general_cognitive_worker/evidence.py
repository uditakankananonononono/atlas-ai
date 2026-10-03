"""Evidence-based outcome estimation for planning, search and counterfactuals.

Nothing here invents a probability. An estimate is computed only from recorded
episodes: how often actions through a given tool actually succeeded
(``ActionRecord.succeeded``) in past episodes. Every estimate carries the
counts it was computed from and a Wilson 95% interval. When fewer than
``min_samples`` observations exist, the estimate is explicitly *unavailable*
(``value is None``) rather than filled with a default prior.

Scope, stated plainly: evidence is keyed by tool name. It does not look at
free-text meaning, arguments or risk tier, so two different tools with
different histories get different estimates, and two actions through the same
tool share one.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .schemas import Episode

WILSON_Z = 1.959963984540054  # 95%


@dataclass(frozen=True)
class OutcomeEstimate:
    """A success-rate estimate with its sample basis, or an explicit absence."""

    key: str | None
    successes: int
    samples: int
    min_samples: int
    value: float | None
    interval_low: float | None
    interval_high: float | None
    basis: str

    @property
    def available(self) -> bool:
        return self.value is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "key": self.key,
            "successes": self.successes,
            "samples": self.samples,
            "min_samples": self.min_samples,
            "value": self.value,
            "interval_95": (
                [self.interval_low, self.interval_high] if self.available else None
            ),
            "basis": self.basis,
        }


def wilson_interval(successes: int, samples: int) -> tuple[float, float]:
    if samples <= 0:
        raise ValueError("samples must be positive")
    p = successes / samples
    z2 = WILSON_Z ** 2
    denom = 1 + z2 / samples
    centre = (p + z2 / (2 * samples)) / denom
    half = WILSON_Z * math.sqrt(p * (1 - p) / samples + z2 / (4 * samples ** 2)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


class ToolEvidence:
    """Per-tool success counts built from recorded episode actions."""

    def __init__(
        self,
        episodes: Iterable[Episode] | Callable[[], Iterable[Episode]] = (),
        *,
        min_samples: int = 3,
    ) -> None:
        if min_samples < 1:
            raise ValueError("min_samples must be >= 1")
        self.min_samples = min_samples
        self._source = episodes

    def _episodes(self) -> list[Episode]:
        src = self._source() if callable(self._source) else self._source
        return list(src)

    def counts(self) -> dict[str, tuple[int, int]]:
        """tool -> (successes, samples), recomputed from the episodes each call."""
        out: dict[str, list[int]] = {}
        for episode in self._episodes():
            for action in episode.actions:
                row = out.setdefault(action.tool, [0, 0])
                row[1] += 1
                if action.succeeded:
                    row[0] += 1
        return {k: (v[0], v[1]) for k, v in out.items()}

    def for_tool(self, tool: str | None) -> OutcomeEstimate:
        if not tool:
            return OutcomeEstimate(
                None, 0, 0, self.min_samples, None, None, None,
                "not estimated: step has no tool, so no action history applies",
            )
        successes, samples = self.counts().get(tool, (0, 0))
        return self._build(tool, successes, samples)

    def for_action_text(self, text: str, *, tool: str | None = None) -> OutcomeEstimate:
        """Resolve free text to a known tool by exact tool-name token match.

        Only literal matches count (explicit ``tool`` or a known tool name
        appearing as a word/identifier in the text). Anything else is
        reported as unmatched, not guessed.
        """
        counts = self.counts()
        if tool:
            return self._build(tool, *counts.get(tool, (0, 0)))
        words = set(re.findall(r"[A-Za-z0-9_\-.]+", text.lower()))
        hits = sorted(t for t in counts if t.lower() in words)
        if len(hits) == 1:
            return self._build(hits[0], *counts[hits[0]])
        why = "no recorded tool is named in the action text" if not hits else (
            f"action text names several recorded tools {hits}; not guessing"
        )
        return OutcomeEstimate(
            None, 0, 0, self.min_samples, None, None, None, f"not estimated: {why}",
        )

    def _build(self, key: str, successes: int, samples: int) -> OutcomeEstimate:
        if samples < self.min_samples:
            return OutcomeEstimate(
                key, successes, samples, self.min_samples, None, None, None,
                f"not estimated: {samples} recorded action(s) for tool {key!r}, "
                f"need at least {self.min_samples}",
            )
        low, high = wilson_interval(successes, samples)
        return OutcomeEstimate(
            key, successes, samples, self.min_samples, successes / samples,
            round(low, 4), round(high, 4),
            f"observed success rate over {samples} recorded action(s) for tool {key!r}",
        )
