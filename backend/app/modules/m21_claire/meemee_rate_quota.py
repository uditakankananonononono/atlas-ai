"""Fixed-window rate limiting and daily quotas, ported from meemee
`rate_limit.py` and `quotas.py` (C4 meemee-merge).

Semantics preserved from meemee@50e7605: fixed-window counting with
(allowed, remaining, reset) triples, window rollover, cleanup; per-principal
daily job quotas with UTC-day rollover and atomic over-limit refusal. Hermetic
in-memory port with injected clocks (meemee's stores are SQLite; Claire's
durable backing belongs to the host).
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timezone
from typing import Callable


def validate_rate_config(limit: int, window_seconds: int) -> None:
    if type(limit) is not int or type(window_seconds) is not int or limit < 1 or window_seconds < 1:
        raise ValueError("rate limit and window must be positive integers")


class FixedWindowLimiter:
    """Fixed-window limiter; one instance is shared by the identities it keys."""

    def __init__(self, limit: int = 60, window_seconds: int = 60,
                 clock: Callable[[], float] = time.time):
        validate_rate_config(limit, window_seconds)
        self.limit, self.window = limit, window_seconds
        self.clock = clock
        self.lock = threading.RLock()
        self._counts: dict[tuple[str, int], int] = {}

    def hit(self, identity: str, now: float | None = None) -> tuple[bool, int, int]:
        timestamp = int(self.clock() if now is None else now)
        window_start = timestamp - timestamp % self.window
        reset = window_start + self.window
        with self.lock:
            key = (identity, window_start)
            count = self._counts.get(key, 0) + 1
            self._counts[key] = count
        return count <= self.limit, max(self.limit - count, 0), reset

    def cleanup(self, now: float | None = None) -> int:
        cutoff = int(self.clock() if now is None else now) - self.window * 2
        with self.lock:
            stale = [key for key in self._counts if key[1] < cutoff]
            for key in stale:
                del self._counts[key]
            return len(stale)


def quota_day(now: datetime | None = None) -> date:
    instant = now if now is not None else datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("quota clock must include a timezone")
    return instant.astimezone(timezone.utc).date()


def validate_quota_limit(value: int) -> None:
    if type(value) is not int or value < 1:
        raise ValueError("daily quota must be a positive integer")


class QuotaExceeded(ValueError):
    pass


class QuotaStore:
    """Per-principal daily quotas with UTC-day rollover."""

    def __init__(self, default_daily_jobs: int = 100):
        validate_quota_limit(default_daily_jobs)
        self.default = default_daily_jobs
        self.lock = threading.RLock()
        self._limits: dict[str, int] = {}
        self._usage: dict[tuple[str, str], int] = {}

    def limit(self, principal: str) -> int:
        with self.lock:
            return self._limits.get(principal, self.default)

    def set_limit(self, principal: str, daily_jobs: int) -> None:
        validate_quota_limit(daily_jobs)
        with self.lock:
            self._limits[principal] = daily_jobs

    def consume_job(self, principal: str, now: datetime | None = None) -> dict[str, int | str]:
        day = quota_day(now).isoformat()
        with self.lock:
            maximum = self.limit(principal)
            used = self._usage.get((principal, day), 0) + 1
            if used > maximum:
                raise QuotaExceeded(f"daily job quota exceeded ({maximum})")
            self._usage[(principal, day)] = used
        return {"day": day, "used": used, "limit": maximum, "remaining": maximum - used}

    def status(self, principal: str, now: datetime | None = None) -> dict[str, int | str]:
        day = quota_day(now).isoformat()
        with self.lock:
            maximum = self.limit(principal)
            used = self._usage.get((principal, day), 0)
        return {"day": day, "used": used, "limit": maximum, "remaining": max(maximum - used, 0)}

    def delete_principal(self, principal: str) -> dict[str, int]:
        with self.lock:
            usage = sum(1 for key in self._usage if key[0] == principal)
            self._usage = {key: value for key, value in self._usage.items() if key[0] != principal}
            limits = 1 if principal in self._limits else 0
            self._limits.pop(principal, None)
        return {"quota_usage": usage, "quota_limits": limits}
