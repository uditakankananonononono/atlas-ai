"""Per-host pacing, adaptive backoff and circuit breaking.

Collectors never sleep inside the limiter; they ask for the wait they owe a
host and pass it to an injected sleeper. Tests record waits instead of
sleeping, which keeps the suite instant while proving human-speed pacing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Optional

from .lane_models import FetchPolicy, utcnow

Failure = tuple[str, Optional[int]]  # (reason, http status)


@dataclass
class HostState:
    last_request_at: Optional[datetime] = None
    interval: float = 0.0                 # adaptive min interval (seconds)
    consecutive_failures: int = 0
    circuit_open_until: Optional[datetime] = None
    total_requests: int = 0
    total_failures: int = 0


class HostRateLimiter:
    def __init__(
        self,
        policy: FetchPolicy | None = None,
        *,
        clock: Callable[[], datetime] = utcnow,
        circuit_failure_threshold: int = 5,
        circuit_cooldown_seconds: float = 300.0,
        max_interval_seconds: float = 60.0,
    ):
        self.policy = policy or FetchPolicy()
        self._clock = clock
        self._states: Dict[str, HostState] = {}
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_cooldown_seconds = circuit_cooldown_seconds
        self.max_interval_seconds = max_interval_seconds

    def _state(self, host: str) -> HostState:
        state = self._states.get(host)
        if state is None:
            state = HostState(interval=self.policy.min_request_interval_seconds)
            self._states[host] = state
        return state

    def check(self, host: str) -> float:
        """Seconds the caller must wait before it may request this host now."""
        now = self._clock()
        state = self._state(host)
        if state.circuit_open_until is not None and now < state.circuit_open_until:
            return (state.circuit_open_until - now).total_seconds()
        if state.last_request_at is None:
            return 0.0
        elapsed = (now - state.last_request_at).total_seconds()
        return max(0.0, state.interval - elapsed)

    def circuit_open(self, host: str) -> bool:
        state = self._states.get(host)
        now = self._clock()
        return bool(state and state.circuit_open_until and now < state.circuit_open_until)

    def record_request(self, host: str) -> None:
        state = self._state(host)
        state.last_request_at = self._clock()
        state.total_requests += 1

    def record_success(self, host: str) -> None:
        state = self._state(host)
        state.consecutive_failures = 0
        state.circuit_open_until = None
        # decay back toward the polite floor after clean fetches
        state.interval = max(self.policy.min_request_interval_seconds, state.interval * 0.75)

    def record_failure(self, host: str, failure: Failure) -> None:
        reason, status = failure
        now = self._clock()
        state = self._state(host)
        state.consecutive_failures += 1
        state.total_failures += 1
        if status in (429, 500, 502, 503, 504) or status is None:
            state.interval = min(self.max_interval_seconds, max(state.interval * 2, self.policy.backoff_base_seconds))
        if state.consecutive_failures >= self.circuit_failure_threshold:
            state.circuit_open_until = datetime.fromtimestamp(
                now.timestamp() + self.circuit_cooldown_seconds, tz=now.tzinfo
            )

    def honor_retry_after(self, host: str, retry_after_seconds: float) -> None:
        state = self._state(host)
        now = self._clock()
        until = datetime.fromtimestamp(now.timestamp() + max(0.0, retry_after_seconds), tz=now.tzinfo)
        if state.circuit_open_until is None or until > state.circuit_open_until:
            state.circuit_open_until = until

    def snapshot(self) -> dict[str, dict]:
        return {
            host: {
                "interval": s.interval,
                "consecutive_failures": s.consecutive_failures,
                "total_requests": s.total_requests,
                "total_failures": s.total_failures,
                "circuit_open": self.circuit_open(host),
            }
            for host, s in self._states.items()
        }
