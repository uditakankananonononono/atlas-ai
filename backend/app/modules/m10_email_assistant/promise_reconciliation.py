"""Fail-closed reconciliation for persisted, reviewed email promise state."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

_EXPLICIT_COMPLETION = re.compile(
    r"\b(?:i|we)\s+(?:have\s+|(?:'ve|'re)\s+)?(?:sent|submitted|uploaded|delivered|finished|completed|resolved|paid|booked|cancelled|canceled)\b",
    re.IGNORECASE,
)


def _sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class Direction(str, Enum):
    OWNER = "owner"
    OTHER = "other"


class PromiseState(str, Enum):
    OPEN = "open"
    COMPLETED = "completed"


class ReconciliationAction(str, Enum):
    COMPLETE = "complete"
    KEEP_OPEN = "keep_open"


class PersistedPromise(BaseModel):
    promise_id: str = Field(min_length=1, max_length=128)
    commitment: str = Field(min_length=1, max_length=1000)
    source_message_id: str = Field(min_length=1, max_length=200)
    source_excerpt: str = Field(min_length=1, max_length=2000)
    state: PromiseState = PromiseState.OPEN
    revision: int = Field(default=1, ge=1)
    last_review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class PromiseSnapshot(BaseModel):
    thread_id: str = Field(min_length=1, max_length=300)
    promises: list[PersistedPromise] = Field(max_length=1000)

    @model_validator(mode="after")
    def unique_promises(self):
        ids = [promise.promise_id for promise in self.promises]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate promise_id in persisted snapshot")
        return self


class UpdateMessage(BaseModel):
    message_id: str = Field(min_length=1, max_length=200)
    direction: Direction
    sent_at: datetime
    body: str = Field(min_length=1, max_length=20000)

    @model_validator(mode="after")
    def aware_time(self):
        if self.sent_at.tzinfo is None:
            raise ValueError("message sent_at must be timezone-aware")
        return self


class ReviewedDecision(BaseModel):
    decision_id: str = Field(min_length=1, max_length=200)
    promise_id: str = Field(min_length=1, max_length=128)
    action: ReconciliationAction
    reviewer_id: str = Field(min_length=1, max_length=200)
    reviewed_at: datetime
    evidence_message_id: str | None = Field(default=None, max_length=200)
    evidence_excerpt: str | None = Field(default=None, max_length=2000)
    previous_promise_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def valid_review(self):
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        if self.action == ReconciliationAction.COMPLETE:
            if not self.evidence_message_id or not self.evidence_excerpt:
                raise ValueError("complete requires message evidence and an exact excerpt")
        elif bool(self.evidence_message_id) != bool(self.evidence_excerpt):
            raise ValueError("keep_open evidence requires both message id and excerpt")
        return self


class PromiseReconciliationRequest(BaseModel):
    previous_snapshot: PromiseSnapshot
    previous_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    update_messages: list[UpdateMessage] = Field(default_factory=list, max_length=1000)
    reviewed_decisions: list[ReviewedDecision] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def unique_update_ids(self):
        message_ids = [message.message_id for message in self.update_messages]
        decision_ids = [decision.decision_id for decision in self.reviewed_decisions]
        promise_ids = [decision.promise_id for decision in self.reviewed_decisions]
        if len(message_ids) != len(set(message_ids)):
            raise ValueError("duplicate update message_id")
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("duplicate decision_id")
        if len(promise_ids) != len(set(promise_ids)):
            raise ValueError("at most one reviewed decision per promise per reconciliation")
        return self


def reconcile_promise_state(request: PromiseReconciliationRequest) -> dict:
    previous = request.previous_snapshot.model_dump(mode="json")
    actual_snapshot_sha = _sha256(previous)
    if actual_snapshot_sha != request.previous_snapshot_sha256:
        raise ValueError("previous snapshot hash mismatch")

    messages = {message.message_id: message for message in request.update_messages}
    promise_rows = {promise.promise_id: promise for promise in request.previous_snapshot.promises}
    output = {promise_id: promise.model_dump(mode="json") for promise_id, promise in promise_rows.items()}
    review_receipts: list[dict] = []

    for decision in sorted(request.reviewed_decisions, key=lambda item: item.decision_id):
        promise = promise_rows.get(decision.promise_id)
        if promise is None:
            raise ValueError(f"decision references unknown promise_id: {decision.promise_id}")
        promise_payload = promise.model_dump(mode="json")
        if _sha256(promise_payload) != decision.previous_promise_sha256:
            raise ValueError(f"previous promise hash mismatch: {decision.promise_id}")
        if promise.state == PromiseState.COMPLETED and decision.action == ReconciliationAction.COMPLETE:
            raise ValueError(f"promise is already completed: {decision.promise_id}")

        evidence_sha = None
        if decision.evidence_message_id:
            message = messages.get(decision.evidence_message_id)
            if message is None:
                raise ValueError(f"review evidence message is absent: {decision.evidence_message_id}")
            excerpt = decision.evidence_excerpt or ""
            if excerpt not in message.body:
                raise ValueError(f"review evidence excerpt is not exact: {decision.decision_id}")
            evidence_sha = _sha256(message.model_dump(mode="json"))
            if decision.action == ReconciliationAction.COMPLETE:
                if message.direction != Direction.OWNER:
                    raise ValueError("completion evidence must be owner-authored")
                if not _EXPLICIT_COMPLETION.search(excerpt):
                    raise ValueError("completion evidence is ambiguous; keep the promise open")

        next_state = PromiseState.COMPLETED if decision.action == ReconciliationAction.COMPLETE else PromiseState.OPEN
        receipt_payload = {
            **decision.model_dump(mode="json"),
            "evidence_message_sha256": evidence_sha,
            "resulting_state": next_state.value,
        }
        receipt_sha = _sha256(receipt_payload)
        output[decision.promise_id] = {
            **promise_payload,
            "state": next_state.value,
            "revision": promise.revision + 1,
            "last_review_sha256": receipt_sha,
        }
        review_receipts.append({**receipt_payload, "review_sha256": receipt_sha})

    reconciled_snapshot = {
        "thread_id": request.previous_snapshot.thread_id,
        "promises": [output[promise_id] for promise_id in sorted(output)],
    }
    reconciled_sha = _sha256(reconciled_snapshot)
    return {
        "valid": True,
        "previous_snapshot_sha256": actual_snapshot_sha,
        "reconciled_snapshot": reconciled_snapshot,
        "reconciled_snapshot_sha256": reconciled_sha,
        "review_count": len(review_receipts),
        "completed_count": sum(row["state"] == PromiseState.COMPLETED for row in output.values()),
        "review_receipts": review_receipts,
        "boundary": (
            "Atlas verifies a supplied persisted snapshot and explicit reviewed decisions. "
            "It completes only a named promise backed by an exact owner-authored completion excerpt; "
            "ambiguous updates fail closed. The caller must transactionally persist the returned snapshot. "
            "This does not authenticate actors, fetch source bytes, create tasks, draft, remind, or send."
        ),
    }
