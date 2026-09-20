"""Budget enforcement for Atlas Module 14 (Project Builder).

Stdlib-only. The module's Budget contract (max_iterations, max_agent_calls,
max_runtime_seconds, max_cost_usd) is enforced by a ledger that records
consumption as a project runs and fails closed the moment any dimension is
exceeded. Deterministic and inspectable; the task runner checks the ledger
before every agent call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


class BudgetError(ValueError):
    """Base error for budget operations."""


class BudgetExceeded(BudgetError):
    """A budget dimension ran out. Fail-closed: raised before the overrun act."""

    def __init__(self, dimension: str, limit: float, attempted: float):
        self.dimension = dimension
        self.limit = limit
        self.attempted = attempted
        super().__init__(
            f"budget exceeded: {dimension} limit {limit}, attempted {attempted}"
        )


@dataclass(frozen=True)
class BudgetLimits:
    max_iterations: int = 3
    max_agent_calls: int = 50
    max_runtime_seconds: int = 3600
    max_cost_usd: float = 25.0

    def __post_init__(self) -> None:
        if self.max_iterations < 1:
            raise BudgetError("max_iterations must be >= 1")
        if self.max_agent_calls < 1:
            raise BudgetError("max_agent_calls must be >= 1")
        if self.max_runtime_seconds < 1:
            raise BudgetError("max_runtime_seconds must be >= 1")
        if self.max_cost_usd < 0:
            raise BudgetError("max_cost_usd must be >= 0")


@dataclass(frozen=True)
class BudgetStatus:
    iterations_used: int
    agent_calls_used: int
    runtime_seconds_used: float
    cost_usd_used: float
    iterations_remaining: int
    agent_calls_remaining: int
    runtime_seconds_remaining: float
    cost_usd_remaining: float
    exhausted: bool
    exhausted_dimensions: Tuple[str, ...]


@dataclass(frozen=True)
class BudgetEvent:
    dimension: str
    amount: float
    at: str  # ISO-8601
    note: str = ""


class BudgetLedger:
    """Records consumption against a BudgetLimits; raises before overruns."""

    def __init__(self, limits: BudgetLimits):
        self.limits = limits
        self._iterations = 0
        self._agent_calls = 0
        self._runtime_seconds = 0.0
        self._cost_usd = 0.0
        self._events: list[BudgetEvent] = []

    def _stamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _record(self, dimension: str, amount: float, note: str) -> None:
        self._events.append(
            BudgetEvent(dimension=dimension, amount=amount, at=self._stamp(), note=note)
        )

    def record_iteration(self, note: str = "") -> None:
        if self._iterations + 1 > self.limits.max_iterations:
            raise BudgetExceeded("iterations", self.limits.max_iterations,
                                 self._iterations + 1)
        self._iterations += 1
        self._record("iterations", 1, note)

    def record_agent_call(self, cost_usd: float = 0.0, note: str = "") -> None:
        if cost_usd < 0:
            raise BudgetError("cost_usd must be >= 0")
        if self._agent_calls + 1 > self.limits.max_agent_calls:
            raise BudgetExceeded("agent_calls", self.limits.max_agent_calls,
                                 self._agent_calls + 1)
        if self._cost_usd + cost_usd > self.limits.max_cost_usd:
            raise BudgetExceeded("cost_usd", self.limits.max_cost_usd,
                                 self._cost_usd + cost_usd)
        self._agent_calls += 1
        self._cost_usd += cost_usd
        self._record("agent_calls", 1, note)
        if cost_usd:
            self._record("cost_usd", cost_usd, note)

    def record_runtime(self, seconds: float, note: str = "") -> None:
        if seconds < 0:
            raise BudgetError("seconds must be >= 0")
        if self._runtime_seconds + seconds > self.limits.max_runtime_seconds:
            raise BudgetExceeded("runtime_seconds", self.limits.max_runtime_seconds,
                                 self._runtime_seconds + seconds)
        self._runtime_seconds += seconds
        self._record("runtime_seconds", seconds, note)

    def status(self) -> BudgetStatus:
        exhausted = []
        if self._iterations >= self.limits.max_iterations:
            exhausted.append("iterations")
        if self._agent_calls >= self.limits.max_agent_calls:
            exhausted.append("agent_calls")
        if self._runtime_seconds >= self.limits.max_runtime_seconds:
            exhausted.append("runtime_seconds")
        if self._cost_usd >= self.limits.max_cost_usd:
            exhausted.append("cost_usd")
        return BudgetStatus(
            iterations_used=self._iterations,
            agent_calls_used=self._agent_calls,
            runtime_seconds_used=self._runtime_seconds,
            cost_usd_used=round(self._cost_usd, 6),
            iterations_remaining=self.limits.max_iterations - self._iterations,
            agent_calls_remaining=self.limits.max_agent_calls - self._agent_calls,
            runtime_seconds_remaining=(
                self.limits.max_runtime_seconds - self._runtime_seconds
            ),
            cost_usd_remaining=round(self.limits.max_cost_usd - self._cost_usd, 6),
            exhausted=bool(exhausted),
            exhausted_dimensions=tuple(exhausted),
        )

    def events(self) -> Tuple[BudgetEvent, ...]:
        return tuple(self._events)

    def can_afford_call(self, estimated_cost_usd: float = 0.0) -> bool:
        """Preflight check a runner can call before committing to an agent call."""
        if estimated_cost_usd < 0:
            raise BudgetError("estimated_cost_usd must be >= 0")
        return (
            self._agent_calls + 1 <= self.limits.max_agent_calls
            and self._cost_usd + estimated_cost_usd <= self.limits.max_cost_usd
        )
