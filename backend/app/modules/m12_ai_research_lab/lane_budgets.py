"""Budget policy and ledger: reserve -> commit/release around every spend.

Reservations make concurrent runs safe against overspend: a run reserves its
estimated cost up front, commits the actual cost when done, and releases the
reservation if it aborts. The ledger is backed by an injectable spend-store
seam (in-memory default; SQLite adapter in store.py).
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol, Tuple

from .lane_models import BudgetPolicy, BudgetStatus, micro_to_usd


class BudgetExceeded(RuntimeError):
    def __init__(self, scope: str, requested_micro: int, remaining_micro: int):
        self.scope = scope
        self.requested_micro = requested_micro
        self.remaining_micro = remaining_micro
        super().__init__(
            f"{scope} budget exceeded: requested ${micro_to_usd(requested_micro):.6f}, "
            f"remaining ${micro_to_usd(remaining_micro):.6f}"
        )


class SpendStore(Protocol):
    """Persistence seam for committed spend entries."""

    def add_spend(self, entry_id: str, run_id: str, amount_micro: int, ts_utc: str) -> None: ...
    def spend_between(self, start_utc: str, end_utc: str) -> int: ...


class InMemorySpendStore:
    def __init__(self) -> None:
        self._entries: List[Tuple[str, str, int, str]] = []
        self._lock = threading.Lock()

    def add_spend(self, entry_id: str, run_id: str, amount_micro: int, ts_utc: str) -> None:
        with self._lock:
            self._entries.append((entry_id, run_id, amount_micro, ts_utc))

    def spend_between(self, start_utc: str, end_utc: str) -> int:
        with self._lock:
            return sum(a for _, _, a, ts in self._entries if start_utc <= ts < end_utc)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _day_window(now: datetime) -> Tuple[str, str]:
    from datetime import timedelta

    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def _month_window(now: datetime) -> Tuple[str, str]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    return start.isoformat(), nxt.isoformat()


class BudgetLedger:
    """Thread-safe reservation/commit ledger over a SpendStore."""

    def __init__(self, policy: BudgetPolicy, store: Optional[SpendStore] = None,
                 clock=_utcnow) -> None:
        self._policy = policy
        self._store: SpendStore = store or InMemorySpendStore()
        self._clock = clock
        self._lock = threading.Lock()
        self._owner = uuid.uuid4().hex   # identifies this ledger instance as hold owner
        # run_id -> reserved micro-dollars (not yet committed)
        self._reservations: Dict[str, int] = {}

    @property
    def durable_holds(self) -> bool:
        """True only when the store gives atomic, crash-surviving holds. A store
        without them falls back to per-process in-memory reservations."""
        return all(callable(getattr(self._store, n, None)) for n in
                   ("reserve_hold", "drop_hold", "list_holds", "book_and_drop_hold"))

    @property
    def policy(self) -> BudgetPolicy:
        return self._policy

    def _totals(self) -> Tuple[int, int]:
        now = self._clock()
        d0, d1 = _day_window(now)
        m0, m1 = _month_window(now)
        return (
            self._store.spend_between(d0, d1),
            self._store.spend_between(m0, m1),
        )

    def _holds(self) -> Dict[str, int]:
        """Open holds. A store with durable holds survives a process crash, so a
        step whose effect may have started keeps counting against the cap."""
        h: Dict[str, int] = {}
        if self.durable_holds:
            h.update(self._store.list_holds())
        h.update(self._reservations)
        return h

    def _drop_hold(self, run_id: str, takeover: bool = False) -> None:
        """Drop this ledger's own hold. A hold owned by another ledger instance is
        left alone unless the caller is an explicit, authorized reconciliation."""
        self._reservations.pop(run_id, None)
        if self.durable_holds:
            self._store.drop_hold(run_id, None if takeover else self._owner)

    def _book(self, entry_id: str, run_id: str, amount: int) -> None:
        ts = self._clock().isoformat()
        if self.durable_holds:
            # spend insert + own-hold delete in one transaction (no double count window)
            self._store.book_and_drop_hold(entry_id, run_id, amount, ts, self._owner)
            self._reservations.pop(run_id, None)
        else:
            # no atomic store: in-memory reservations only (documented fallback)
            self._store.add_spend(entry_id, run_id, amount, ts)
            self._reservations.pop(run_id, None)

    def _reserved_total(self) -> int:
        return sum(self._holds().values())

    def status(self) -> BudgetStatus:
        with self._lock:
            spent_day, spent_month = self._totals()
            reserved = self._reserved_total()
            p = self._policy
            daily_remaining = (
                p.daily_limit_micro - spent_day - reserved
                if p.daily_limit_micro is not None else None
            )
            monthly_remaining = (
                p.monthly_limit_micro - spent_month - reserved
                if p.monthly_limit_micro is not None else None
            )
            warnings: List[str] = []
            if p.daily_limit_micro is not None and (
                spent_day + reserved >= p.warn_fraction * p.daily_limit_micro
            ):
                warnings.append("daily spend at or above warn threshold")
            if p.monthly_limit_micro is not None and (
                spent_month + reserved >= p.warn_fraction * p.monthly_limit_micro
            ):
                warnings.append("monthly spend at or above warn threshold")
            return BudgetStatus(
                spent_today_micro=spent_day,
                spent_month_micro=spent_month,
                reserved_micro=reserved,
                daily_limit_micro=p.daily_limit_micro,
                monthly_limit_micro=p.monthly_limit_micro,
                per_run_limit_micro=p.per_run_limit_micro,
                daily_remaining_micro=daily_remaining,
                monthly_remaining_micro=monthly_remaining,
                warnings=tuple(warnings),
            )

    def _check_limits_locked(self, amount_micro: int, run_id: str) -> None:
        p = self._policy
        spent_day, spent_month = self._totals()
        reserved_other = self._reserved_total() - self._holds().get(run_id, 0)
        if p.per_run_limit_micro is not None and amount_micro > p.per_run_limit_micro:
            raise BudgetExceeded("per_run", amount_micro, p.per_run_limit_micro)
        if p.daily_limit_micro is not None:
            remaining = p.daily_limit_micro - spent_day - reserved_other
            if amount_micro > remaining:
                raise BudgetExceeded("daily", amount_micro, max(remaining, 0))
        if p.monthly_limit_micro is not None:
            remaining = p.monthly_limit_micro - spent_month - reserved_other
            if amount_micro > remaining:
                raise BudgetExceeded("monthly", amount_micro, max(remaining, 0))

    def reserve(self, run_id: str, estimated_micro: int) -> str:
        """Reserve an estimated amount for a run. Raises BudgetExceeded."""
        if type(estimated_micro) is not int:
            raise ValueError("estimated_micro must be an integer")
        if estimated_micro < 0:
            raise ValueError("estimated_micro must be non-negative")
        if not run_id:
            raise ValueError("run_id must be non-empty")
        with self._lock:
            def check() -> None:
                if run_id in self._holds():
                    raise ValueError(f"run_id {run_id} already has an open reservation")
                self._check_limits_locked(estimated_micro, run_id)

            if self.durable_holds:
                # Limit check and hold insert in ONE store transaction, so separate
                # processes cannot both be admitted. Failure fails closed.
                self._store.reserve_hold(run_id, estimated_micro, check, self._owner)
            else:
                check()
            self._reservations[run_id] = estimated_micro
        return run_id

    def commit(self, run_id: str, actual_micro: int) -> str:
        """Commit actual spend for a run, clearing its reservation.

        The committed amount may differ from the reservation (estimates are
        estimates); limits are re-checked against the actual amount.
        """
        if type(actual_micro) is not int:
            raise ValueError("actual_micro must be an integer")
        if actual_micro < 0:
            raise ValueError("actual_micro must be non-negative")
        with self._lock:
            self._check_limits_locked(actual_micro, run_id)
            entry_id = f"spend-{uuid.uuid4().hex[:16]}"
            self._book(entry_id, run_id, actual_micro)
        return entry_id

    def record_incurred(self, run_id: str, actual_micro: int) -> str:
        """Book spend that has already happened, even past a limit.

        Unlike commit(), limits are not enforced: the usage was consumed, so
        refusing to book it would hide it. Clears the run's reservation. The
        overrun stays visible through status() remaining values going negative.
        """
        if type(actual_micro) is not int or actual_micro < 0:
            raise ValueError("actual_micro must be a nonnegative integer")
        with self._lock:
            entry_id = f"spend-{uuid.uuid4().hex[:16]}"
            self._book(entry_id, run_id, actual_micro)
        return entry_id

    def release(self, run_id: str, *, takeover: bool = False) -> None:
        """Drop a reservation without spending (run aborted). Idempotent. Only the
        owning ledger instance may drop a durable hold; takeover=True is for the
        explicit reconcile path after an authorized claim takeover/retry."""
        with self._lock:
            self._drop_hold(run_id, takeover)
