"""Tamper-evident execution audit journal for Claire."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Any, Mapping

from .models import utcnow


@dataclass(frozen=True, slots=True)
class AuditEvent:
    sequence: int
    event_type: str
    plan_id: str
    action_id: str | None
    occurred_at: datetime
    data: Mapping[str, Any]
    previous_hash: str
    event_hash: str


class AuditIntegrityError(RuntimeError):
    pass


class AuditJournal:
    """Append-only hash chain; callers can persist exported events externally."""

    GENESIS = "0" * 64

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = RLock()

    @staticmethod
    def _canonical(payload: Mapping[str, Any]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()

    @classmethod
    def _hash(cls, *, sequence: int, event_type: str, plan_id: str, action_id: str | None,
              occurred_at: datetime, data: Mapping[str, Any], previous_hash: str) -> str:
        payload = {
            "sequence": sequence, "event_type": event_type, "plan_id": plan_id,
            "action_id": action_id, "occurred_at": occurred_at.isoformat(),
            "data": data, "previous_hash": previous_hash,
        }
        return hashlib.sha256(cls._canonical(payload)).hexdigest()

    def append(self, event_type: str, plan_id: str, *, action_id: str | None = None,
               data: Mapping[str, Any] | None = None, occurred_at: datetime | None = None) -> AuditEvent:
        if not event_type.strip() or not plan_id.strip():
            raise ValueError("event_type and plan_id are required")
        timestamp = occurred_at or utcnow()
        if timestamp.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        with self._lock:
            sequence = len(self._events) + 1
            previous = self._events[-1].event_hash if self._events else self.GENESIS
            body = dict(data or {})
            digest = self._hash(sequence=sequence, event_type=event_type, plan_id=plan_id,
                                action_id=action_id, occurred_at=timestamp, data=body, previous_hash=previous)
            event = AuditEvent(sequence, event_type, plan_id, action_id, timestamp, body, previous, digest)
            self._events.append(event)
            return event

    def events(self, *, plan_id: str | None = None) -> tuple[AuditEvent, ...]:
        with self._lock:
            snapshot = tuple(self._events)
        return snapshot if plan_id is None else tuple(e for e in snapshot if e.plan_id == plan_id)

    @classmethod
    def verify(cls, events: tuple[AuditEvent, ...] | list[AuditEvent]) -> bool:
        previous = cls.GENESIS
        for expected, event in enumerate(events, start=1):
            if event.sequence != expected or event.previous_hash != previous:
                raise AuditIntegrityError(f"broken chain at sequence {expected}")
            actual = cls._hash(sequence=event.sequence, event_type=event.event_type,
                               plan_id=event.plan_id, action_id=event.action_id,
                               occurred_at=event.occurred_at, data=event.data, previous_hash=event.previous_hash)
            if actual != event.event_hash:
                raise AuditIntegrityError(f"invalid hash at sequence {expected}")
            previous = event.event_hash
        return True
