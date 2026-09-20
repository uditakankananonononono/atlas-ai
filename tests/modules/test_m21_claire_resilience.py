from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.modules.m21_claire import (
    AttemptsExhausted, AuditIntegrityError, AuditJournal, BoundedExecutor,
    IdempotencyConflict, IdempotencyStore,
)

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def test_audit_journal_is_hash_chained_and_detects_tampering():
    journal = AuditJournal()
    journal.append("plan.created", "p1", data={"goal": "report"}, occurred_at=NOW)
    journal.append("action.approved", "p1", action_id="a1", data={"approver": "user"}, occurred_at=NOW)
    events = journal.events()
    assert AuditJournal.verify(events)
    tampered = [events[0], replace(events[1], data={"approver": "attacker"})]
    with pytest.raises(AuditIntegrityError, match="invalid hash"):
        AuditJournal.verify(tampered)


def test_bounded_executor_replays_completed_result_without_side_effect():
    calls = []
    executor = BoundedExecutor()
    op = lambda p: calls.append(p["x"]) or p["x"] * 2
    first = executor.run(key="p:a", fingerprint="review-hash", operation=op, parameters={"x": 4})
    second = executor.run(key="p:a", fingerprint="review-hash", operation=op, parameters={"x": 4})
    assert first.value == second.value == 8
    assert not first.replayed and second.replayed and second.attempts == 0
    assert calls == [4]


def test_same_idempotency_key_cannot_change_reviewed_action():
    executor = BoundedExecutor()
    executor.run(key="p:a", fingerprint="one", operation=lambda p: 1, parameters={})
    with pytest.raises(IdempotencyConflict):
        executor.run(key="p:a", fingerprint="two", operation=lambda p: 2, parameters={})


def test_retry_is_bounded_and_only_when_classifier_allows():
    calls = []
    def transient(_):
        calls.append(1)
        raise TimeoutError("temporary")
    with pytest.raises(AttemptsExhausted) as error:
        BoundedExecutor().run(key="k", fingerprint="f", operation=transient, parameters={},
                              max_attempts=3, retryable=lambda exc: isinstance(exc, TimeoutError))
    assert error.value.attempts == 3 and len(calls) == 3


def test_failed_claim_is_abandoned_for_explicit_later_retry():
    store = IdempotencyStore()
    executor = BoundedExecutor(store)
    with pytest.raises(AttemptsExhausted):
        executor.run(key="k", fingerprint="f", operation=lambda p: (_ for _ in ()).throw(ValueError("bad")), parameters={})
    assert executor.run(key="k", fingerprint="f", operation=lambda p: "ok", parameters={}).value == "ok"
