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
        if durable:
            return self._run_durable(key, operation, parameters, max_attempts, retryable)
        try:
            while attempts < max_attempts:
                attempts += 1
                try:
                    result = operation(dict(parameters))
                    self.store.complete(key, result)
                    return ExecutionResult(result, attempts, False)
                except Exception as exc:
                    if attempts >= max_attempts or retryable is None or not retryable(exc):
                        raise AttemptsExhausted(attempts, exc) from exc
        except Exception:
            self.store.abandon(key)
            raise
        raise AssertionError("unreachable")

    def _run_durable(self, key: str, operation: Callable[[Mapping[str, Any]], Any],
                     parameters: Mapping[str, Any], max_attempts: int,
                     retryable: Callable[[Exception], bool] | None) -> ExecutionResult:
        """Fail closed: the journal row is removed ONLY on the explicit NotExecuted proof. Any other exception (the body
        failing, mark_unknown/complete raising a persistence error, anything raised after the body may have begun) leaves
        the row in place, so the next run sees EffectUnknown instead of repeating the effect."""
        attempts = 0
        while True:
            attempts += 1
            try:
                result = operation(dict(parameters))
            except NotExecuted as exc:
                if attempts < max_attempts and retryable is not None and retryable(exc):
                    continue
                self.store.abandon(key)  # proven never-ran; if this raises the row stays (fail closed)
                raise AttemptsExhausted(attempts, exc) from exc
            except Exception as exc:
                self.store.mark_unknown(key)  # if this raises, the intent row stays and the error propagates
                raise AttemptsExhausted(attempts, exc) from exc
            self.store.complete(key, result)  # if this raises the intent stays: effect landed, outcome unrecorded
            return ExecutionResult(result, attempts, False)
