"""Proactive check-in planning with quiet hours, ported from meemee
`companion/checkins.py` (C4 meemee-merge).

Semantics preserved from meemee@50e7605: local wall-clock quiet windows
(including overnight and all-day start==end), next-due computation that steps
out of quiet hours with a two-week guard, UTC slot naming, and planning that
reuses pending check-ins so polling never duplicates them. The store is an
in-memory preference/slot ledger; durable delivery stays with the host.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any


def _hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


@dataclass(frozen=True)
class QuietHours:
    start: str
    end: str


@dataclass(frozen=True)
class CheckInPreferences:
    cadence_minutes: int
    quiet_hours: QuietHours | None = None
    enabled: bool = True
    channel: str = "local"
    address: str = ""


def in_quiet_hours(moment: datetime, quiet: QuietHours) -> bool:
    """True when the local wall-clock time falls inside the quiet window."""
    local = moment.timetz().replace(tzinfo=None)
    start, end = _hhmm(quiet.start), _hhmm(quiet.end)
    if start == end:
        return True
    if start < end:
        return start <= local < end
    return local >= start or local < end


def next_due(prefs: CheckInPreferences, tz, after: datetime) -> datetime:
    """Next check-in instant strictly after `after`, honoring quiet hours."""
    if after.tzinfo is None or after.utcoffset() is None:
        raise ValueError("planning clock must include a timezone")
    candidate = (after.astimezone(timezone.utc) + timedelta(minutes=prefs.cadence_minutes)).astimezone(tz)
    if prefs.quiet_hours is None:
        return candidate.astimezone(timezone.utc)
    guard = 0
    while in_quiet_hours(candidate, prefs.quiet_hours):
        candidate = (candidate.astimezone(timezone.utc) + timedelta(minutes=15)).astimezone(tz)
        guard += 1
        if guard > 4 * 24 * 14:
            raise ValueError("quiet hours leave no deliverable slot in two weeks")
    return candidate.astimezone(timezone.utc)


def slot_name(due: datetime) -> str:
    return due.astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")


class CheckInScheduler:
    """Plans durable, idempotent check-in slots from per-user preferences."""

    def __init__(self):
        self.lock = threading.RLock()
        self._prefs: dict[str, CheckInPreferences] = {}
        self._pending: dict[str, dict[str, Any]] = {}

    def set_preferences(self, user_id: str, prefs: CheckInPreferences) -> None:
        with self.lock:
            self._prefs[user_id] = prefs

    def plan_user(self, user_id: str, after: datetime | None = None, tz=timezone.utc) -> dict[str, Any] | None:
        with self.lock:
            prefs = self._prefs.get(user_id)
            if prefs is None or not prefs.enabled:
                return None
            if prefs.quiet_hours is not None and prefs.quiet_hours.start == prefs.quiet_hours.end:
                # The defined all-day quiet preference has no eligible slot.
                return None
            pending = self._pending.get(user_id)
            if pending is not None:
                return dict(pending)
            moment = after or datetime.now(timezone.utc)
            due = next_due(prefs, tz, moment)
            row = {
                "user_id": user_id, "due": due, "slot": slot_name(due),
                "channel": prefs.channel, "address": prefs.address, "status": "queued",
            }
            self._pending[user_id] = row
            return dict(row)

    def complete(self, user_id: str, slot: str) -> bool:
        with self.lock:
            pending = self._pending.get(user_id)
            if pending is None or pending["slot"] != slot:
                return False
            del self._pending[user_id]
            return True

    def plan_all(self, after: datetime | None = None) -> list[dict[str, Any]]:
        planned = []
        for user_id in list(self._prefs):
            row = self.plan_user(user_id, after)
            if row is not None:
                planned.append(row)
        return planned
