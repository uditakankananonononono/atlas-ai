"""Deterministic calendar-event conflict detection.

The detector is provider-neutral and has no database or FastAPI dependency. It
uses half-open intervals, so an event ending exactly when another starts does
not conflict. Datetimes must be timezone-aware; silently assuming a timezone
would make cross-provider conflict results unsafe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable


class Availability(str, Enum):
    BUSY = "busy"
    TENTATIVE = "tentative"
    FREE = "free"


class ConflictSeverity(str, Enum):
    HARD = "hard"
    SOFT = "soft"


@dataclass(frozen=True)
class CalendarInterval:
    event_id: str
    source_id: str
    summary: str
    start: datetime
    end: datetime
    availability: Availability = Availability.BUSY
    status: str = "confirmed"

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id must not be empty")
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty")
        if self.start.tzinfo is None or self.start.utcoffset() is None:
            raise ValueError("event start must be timezone-aware")
        if self.end.tzinfo is None or self.end.utcoffset() is None:
            raise ValueError("event end must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("event end must be after start")

    @property
    def key(self) -> tuple[str, str]:
        return self.source_id, self.event_id


@dataclass(frozen=True)
class EventConflict:
    left: CalendarInterval
    right: CalendarInterval
    overlap_start: datetime
    overlap_end: datetime
    severity: ConflictSeverity

    @property
    def overlap_minutes(self) -> int:
        return int((self.overlap_end - self.overlap_start).total_seconds() // 60)

    @property
    def id(self) -> str:
        first, second = sorted((self.left.key, self.right.key))
        return f"{first[0]}:{first[1]}|{second[0]}:{second[1]}"


class DuplicateEventError(ValueError):
    """The same provider event key occurred more than once in one snapshot."""


def detect_conflicts(
    events: Iterable[CalendarInterval],
    *,
    minimum_overlap: timedelta = timedelta(0),
    across_sources_only: bool = False,
) -> list[EventConflict]:
    """Return all pairwise conflicts in deterministic order.

    Cancelled and free/transparent events do not block time. ``minimum_overlap``
    is inclusive: with 15 minutes configured, a 15-minute overlap is returned.
    Duplicate ``(source_id, event_id)`` keys are rejected because choosing one
    provider copy arbitrarily could hide a real conflict.
    """
    if minimum_overlap < timedelta(0):
        raise ValueError("minimum_overlap must not be negative")

    seen: set[tuple[str, str]] = set()
    blocking: list[CalendarInterval] = []
    for event in events:
        if event.key in seen:
            raise DuplicateEventError(
                f"duplicate event key {event.source_id!r}/{event.event_id!r}"
            )
        seen.add(event.key)
        if event.status.casefold() == "cancelled" or event.availability is Availability.FREE:
            continue
        blocking.append(event)

    blocking.sort(
        key=lambda event: (
            event.start.astimezone(timezone.utc),
            event.end.astimezone(timezone.utc),
            event.source_id,
            event.event_id,
        )
    )
    active: list[CalendarInterval] = []
    conflicts: list[EventConflict] = []

    for current in blocking:
        current_start = current.start.astimezone(timezone.utc)
        active = [
            event for event in active
            if event.end.astimezone(timezone.utc) > current_start
        ]
        for prior in active:
            if across_sources_only and prior.source_id == current.source_id:
                continue
            overlap_start = max(
                prior.start.astimezone(timezone.utc), current_start
            )
            overlap_end = min(
                prior.end.astimezone(timezone.utc),
                current.end.astimezone(timezone.utc),
            )
            overlap = overlap_end - overlap_start
            if overlap <= timedelta(0) or overlap < minimum_overlap:
                continue
            severity = (
                ConflictSeverity.SOFT
                if Availability.TENTATIVE in (prior.availability, current.availability)
                else ConflictSeverity.HARD
            )
            conflicts.append(
                EventConflict(
                    left=prior,
                    right=current,
                    overlap_start=overlap_start,
                    overlap_end=overlap_end,
                    severity=severity,
                )
            )
        active.append(current)

    return sorted(
        conflicts,
        key=lambda conflict: (
            conflict.overlap_start,
            conflict.overlap_end,
            conflict.id,
        ),
    )
