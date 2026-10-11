"""Budget enforcement for Atlas Module 14 (Project Builder).

Stdlib-only. The module's Budget contract (max_iterations, max_agent_calls,
max_runtime_seconds, max_cost_usd) is enforced by a ledger that records
consumption as a project runs and fails closed the moment any dimension is
exceeded. Deterministic and inspectable; the task runner checks the ledger
before every agent call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


class BudgetError(ValueError):
    """Base error for budget operations."""


class BudgetExceeded(BudgetError):
    """A budget dimension ran out.

    Raised BEFORE the overrun on the pre-execution gates (reserve/record
    paths). On the settle path an actual above the estimate is real spend
    that already happened: the ledger records it first, then raises - the
    overrun is reported, not prevented."""

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


class CallReservation:
    """Opaque single-use hold token issued by BudgetLedger.reserve_call.

    Identity only: the held amount lives in the issuing ledger's registry
    (immutable, never on the token), and the token is accepted exactly once,
    only by the ledger that issued it. Forged, replayed, cross-ledger or
    mutated tokens are rejected with no ledger change.
    """

    __slots__ = ("_ledger", "_token_id")

    def __init__(self, ledger, token_id: int):
        object.__setattr__(self, "_ledger", ledger)
        object.__setattr__(self, "_token_id", token_id)

    def __setattr__(self, name, value):
        raise AttributeError("CallReservation is immutable")


class BudgetLedger:
    """Records consumption against a BudgetLimits.

    Pre-execution gates raise before overruns; settle_call records an
    over-estimate actual truthfully after the spend, then raises."""

    def __init__(self, limits: BudgetLimits):
        self._reservations: dict[int, dict] = {}
        self._reservation_seq = 0
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

    def reserve_call(self, estimated_cost_usd: float, note: str = "") -> "CallReservation":
        """Conservatively pre-charge an estimate BEFORE an agent call runs.

        The hold binds the gate: if the estimate does not fit the remaining
        budget, BudgetExceeded is raised and nothing is charged, so the call
        never starts. settle_call reconciles with the recorded actual cost;
        release_call undoes the hold when the call never happened.

        Scope of the guarantee: over-budget EXECUTION is blocked only when the
        estimate covers the actual provider charge. A call whose actual cost
        exceeds the estimate still spends real money; settle_call records
        that over-estimate spend truthfully AFTER the fact - it is reported,
        not prevented. An enforceable executor-side cap is required to bound
        actual charges at runtime; this ledger alone does not provide one.
        """
        if type(estimated_cost_usd) not in (int, float) \
                or not math.isfinite(estimated_cost_usd) or estimated_cost_usd < 0:
            raise BudgetError("reserve estimate must be finite nonnegative numeric, not bool")
        self.record_agent_call(estimated_cost_usd, note=note or "reserve call")
        self._reservation_seq += 1
        reservation = CallReservation(self, self._reservation_seq)
        # The registry binds the ISSUED OBJECT itself, not just the integer
        # id: a hand-constructed CallReservation carrying a genuine active id
        # is a clone, and identity ("is") is what separates issuance from
        # forgery.
        self._reservations[self._reservation_seq] = {
            "amount": estimated_cost_usd, "state": "active", "token": reservation}
        return reservation

    def settle_call(self, reservation: "CallReservation", actual_cost_usd: float,
                    note: str = "") -> None:
        """Reconcile a hold with the actual cost the executor recorded.

        The ledger always records the truth: an actual above the reserved
        estimate is charged first (the spend already happened) and only then
        raises BudgetExceeded; an actual below it refunds the difference.
        """
        if type(actual_cost_usd) not in (int, float) \
                or not math.isfinite(actual_cost_usd) or actual_cost_usd < 0:
            raise BudgetError("actual cost must be finite nonnegative numeric, not bool")
        held = self._consume_reservation(reservation)
        delta = actual_cost_usd - held
        if delta == 0:
            return
        # 6-decimal rounding matches status() reporting and kills float residue
        self._cost_usd = round(self._cost_usd + delta, 6)
        self._record("cost_usd", delta, note or ("settle call overage" if delta > 0 else "settle call refund"))
        if delta > 0 and self._cost_usd > self.limits.max_cost_usd:
            raise BudgetExceeded("cost_usd", self.limits.max_cost_usd, self._cost_usd)

    def _consume_reservation(self, reservation: "CallReservation") -> float:
        """Validate and consume a single-use token; reject forgery/replay.

        Only tokens issued by THIS ledger's reserve_call are accepted, each
        exactly once. Any rejection leaves the ledger untouched.
        """
        if not isinstance(reservation, CallReservation) \
                or reservation._ledger is not self \
                or type(reservation._token_id) is not int:
            raise BudgetError("reservation was not issued by this ledger")
        entry = self._reservations.get(reservation._token_id)
        if entry is None or entry["token"] is not reservation:
            raise BudgetError("reservation was not issued by this ledger")
        if entry["state"] != "active":
            raise BudgetError("reservation already settled or released")
        entry["state"] = "consumed"
        return entry["amount"]

    def release_call(self, reservation: "CallReservation", note: str = "") -> None:
        """Undo a hold when the caller is CERTAIN the call never happened.

        For the unknown-spend path (executor raised) use abandon_call:
        release would refund budget that may already be spent.
        """
        held = self._consume_reservation(reservation)
        self._agent_calls -= 1
        self._cost_usd = round(self._cost_usd - held, 6)
        self._record("agent_calls", -1, note or "release call")
        if held:
            self._record("cost_usd", -held, note or "release call")

    def abandon_call(self, reservation: "CallReservation", note: str = "") -> None:
        """Retain a hold when the executor raised and spend is UNKNOWN.

        Conservative accounting: the reservation stays charged (the provider
        may have billed it) and the token is consumed, so no later settle or
        release can refund or double-count it.
        """
        held = self._consume_reservation(reservation)
        self._record("hold_retained", held,
                     note or "executor raised; hold retained as unknown spend")

    def can_afford_call(self, estimated_cost_usd: float = 0.0) -> bool:
        """Preflight check a runner can call before committing to an agent call."""
        if estimated_cost_usd < 0:
            raise BudgetError("estimated_cost_usd must be >= 0")
        return (
            self._agent_calls + 1 <= self.limits.max_agent_calls
            and self._cost_usd + estimated_cost_usd <= self.limits.max_cost_usd
        )
