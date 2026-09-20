"""Validation and canonicalization at the calendar-provider sync boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Protocol


class SyncEvent(Protocol):
    uid: str
    summary: str
    start: datetime | None
    end: datetime | None
    location: str | None
    status: str


class InvalidSyncBatchError(ValueError):
    """A provider batch is unsafe to persist as delivered."""


@dataclass(frozen=True)
class ValidatedSyncEvent:
    uid: str
    summary: str
    start: datetime | None
    end: datetime | None
    location: str | None
    status: str


def _aware_utc(moment: datetime | None, *, field: str, uid: str) -> datetime | None:
    if moment is None:
        return None
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise InvalidSyncBatchError(f"event {uid!r} has naive {field}")
    return moment.astimezone(timezone.utc)


def validate_sync_batch(events: Iterable[SyncEvent]) -> list[ValidatedSyncEvent]:
    """Validate the entire batch before any row is written.

    Cancellation tombstones may omit times. Active events require both times
    and a positive duration. UIDs must be unique in a provider response so the
    final row cannot depend on response ordering.
    """
    validated: list[ValidatedSyncEvent] = []
    seen: set[str] = set()
    for event in events:
        uid = event.uid.strip()
        if not uid:
            raise InvalidSyncBatchError("provider event is missing uid")
        if uid in seen:
            raise InvalidSyncBatchError(f"provider batch contains duplicate uid {uid!r}")
        seen.add(uid)
        status = (event.status or "confirmed").strip().casefold()
        if status not in {"confirmed", "tentative", "cancelled"}:
            raise InvalidSyncBatchError(f"event {uid!r} has unsupported status {status!r}")
        start = _aware_utc(event.start, field="start", uid=uid)
        end = _aware_utc(event.end, field="end", uid=uid)
        if status != "cancelled":
            if start is None or end is None:
                raise InvalidSyncBatchError(f"active event {uid!r} requires start and end")
            if end <= start:
                raise InvalidSyncBatchError(f"event {uid!r} end must be after start")
        elif (start is None) != (end is None):
            raise InvalidSyncBatchError(
                f"cancelled event {uid!r} must provide both times or neither"
            )
        if start is not None and end is not None and end <= start:
            raise InvalidSyncBatchError(f"event {uid!r} end must be after start")
        validated.append(
            ValidatedSyncEvent(
                uid=uid,
                summary=(event.summary or "(no title)").strip() or "(no title)",
                start=start,
                end=end,
                location=(event.location.strip() if event.location else None),
                status=status,
            )
        )
    return validated
