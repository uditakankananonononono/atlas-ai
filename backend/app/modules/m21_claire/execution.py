"""Idempotent, bounded execution primitives with explicit retry semantics."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Mapping


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    value: Any
    attempts: int
    replayed: bool


class AttemptsExhausted(RuntimeError):
    def __init__(self, attempts: int, last_error: Exception) -> None:
        super().__init__(f"execution failed after {attempts} attempt(s): {type(last_error).__name__}")
        self.attempts = attempts
        self.last_error = last_error


class IdempotencyConflict(RuntimeError):
    pass


class NotExecuted(Exception):
    """Raised by an executor that can PROVE no side effect began (e.g. it failed validating its inputs or connecting,
    before any write). The only failure a durable store treats as safe to retry. Any other exception after the body
    begins leaves the effect unknown: the exception class cannot establish that nothing landed."""


class EffectUnknown(RuntimeError):
    """A step's effect may have landed (intent recorded, no outcome). Never re-run it; the owner resolves it."""


@dataclass(slots=True)
class _Entry:
    fingerprint: str
    complete: bool = False
    result: Any = None


class IdempotencyStore:
    """Reference process-local store. Production adapters may implement the same methods."""

    def __init__(self) -> None:
        self._items: dict[str, _Entry] = {}
        self._lock = RLock()

    def claim(self, key: str, fingerprint: str) -> tuple[bool, Any]:
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                self._items[key] = _Entry(fingerprint)
                return True, None
            if entry.fingerprint != fingerprint:
                raise IdempotencyConflict("key was already used for a different reviewed action")
            if entry.complete:
                return False, entry.result
            raise IdempotencyConflict("an execution with this key is already in progress")

    def complete(self, key: str, result: Any) -> None:
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                raise KeyError(key)
            entry.result = result
            entry.complete = True

    def abandon(self, key: str) -> None:
        with self._lock:
            entry = self._items.get(key)
            if entry is not None and not entry.complete:
                del self._items[key]


class BoundedExecutor:
    def __init__(self, store: IdempotencyStore | None = None) -> None:
        self.store = store or IdempotencyStore()

    def run(self, *, key: str, fingerprint: str, operation: Callable[[Mapping[str, Any]], Any],
            parameters: Mapping[str, Any], max_attempts: int = 1,
            retryable: Callable[[Exception], bool] | None = None) -> ExecutionResult:
        if not key or not fingerprint:
            raise ValueError("key and fingerprint are required")
        if max_attempts < 1 or max_attempts > 5:
            raise ValueError("max_attempts must be between 1 and 5")
        claimed, prior = self.store.claim(key, fingerprint)
        if not claimed:
            return ExecutionResult(prior, 0, True)
        attempts = 0
        durable = hasattr(self.store, "mark_unknown")
        try:
            while attempts < max_attempts:
                attempts += 1
                try:
                    result = operation(dict(parameters))
                    self.store.complete(key, result)
                    return ExecutionResult(result, attempts, False)
                except Exception as exc:
                    never_ran = isinstance(exc, NotExecuted)
                    if durable and not never_ran:
                        # The body began and failed: the effect may have landed. Keep the intent, never re-run.
                        self.store.mark_unknown(key)
                        raise AttemptsExhausted(attempts, exc) from exc
                    if attempts >= max_attempts or retryable is None or not retryable(exc):
                        raise AttemptsExhausted(attempts, exc) from exc
        except AttemptsExhausted as exc:
            if not (durable and not isinstance(exc.last_error, NotExecuted)):
                self.store.abandon(key)
            raise
        except Exception:
            self.store.abandon(key)
            raise
        raise AssertionError("unreachable")
