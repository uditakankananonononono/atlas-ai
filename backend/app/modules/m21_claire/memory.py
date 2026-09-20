"""Consent-aware storage interfaces and an in-memory reference implementation."""
from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Iterable

from .models import DecisionRecord, Preference


class ConsentError(PermissionError):
    pass


class DecisionStore:
    """Thread-safe store that never returns a decision outside its consent scope."""

    def __init__(self) -> None:
        self._records: dict[str, DecisionRecord] = {}
        self._preferences: dict[str, Preference] = {}
        self._lock = RLock()

    def put_decision(self, record: DecisionRecord) -> None:
        with self._lock:
            self._records[record.decision_id] = record

    def revoke_decision(self, decision_id: str, revoked: DecisionRecord) -> None:
        if decision_id != revoked.decision_id or revoked.revoked_at is None:
            raise ValueError("replacement must be the same revoked decision")
        with self._lock:
            if decision_id not in self._records:
                raise KeyError(decision_id)
            self._records[decision_id] = revoked

    def retrieve(
        self, *, subject: str, purpose: str, scope: str, now: datetime
    ) -> tuple[DecisionRecord, ...]:
        with self._lock:
            matches = [
                r for r in self._records.values()
                if r.subject == subject and r.is_usable(scope=scope, purpose=purpose, now=now)
            ]
        return tuple(sorted(matches, key=lambda r: r.decided_at, reverse=True))

    def require_one(self, *, subject: str, purpose: str, scope: str, now: datetime) -> DecisionRecord:
        matches = self.retrieve(subject=subject, purpose=purpose, scope=scope, now=now)
        if not matches:
            raise ConsentError(f"no consented decision for {subject!r} and scope {scope!r}")
        return matches[0]

    def put_preference(self, preference: Preference) -> None:
        if not preference.evidence:
            raise ValueError("preferences require evidence")
        with self._lock:
            self._preferences[preference.key] = preference

    def preference(self, key: str, *, purpose: str, now: datetime) -> Preference:
        with self._lock:
            preference = self._preferences.get(key)
        if preference is None or not preference.is_usable(purpose, now):
            raise ConsentError(f"preference {key!r} is not usable for {purpose!r}")
        return preference

    def usable_preferences(self, *, purpose: str, now: datetime) -> Iterable[Preference]:
        with self._lock:
            values = tuple(self._preferences.values())
        return tuple(p for p in values if p.is_usable(purpose, now))
