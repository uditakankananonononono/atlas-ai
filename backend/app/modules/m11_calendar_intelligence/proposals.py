"""Side-effect-free candidate generation for scheduling proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .solver import FixedEvent, SchedulingPrefs


@dataclass(frozen=True)
class ProposalRequest:
    earliest: datetime
    latest: datetime
    duration_minutes: int
    limit: int = 5
    buffer_before_minutes: int = 0
    buffer_after_minutes: int = 0
    granularity_minutes: int = 15

    def __post_init__(self) -> None:
        for name, value in (("earliest", self.earliest), ("latest", self.latest)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.latest <= self.earliest:
            raise ValueError("latest must be after earliest")
        if not 15 <= self.duration_minutes <= 24 * 60:
            raise ValueError("duration_minutes must be between 15 and 1440")
        if not 1 <= self.limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if self.buffer_before_minutes < 0 or self.buffer_after_minutes < 0:
            raise ValueError("buffers must not be negative")
        if self.granularity_minutes not in (5, 10, 15, 30, 60):
            raise ValueError("unsupported granularity_minutes")


@dataclass(frozen=True)
class SchedulingCandidate:
    start: datetime
    end: datetime
    score: float
    reasons: tuple[str, ...]


def _utc(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc)


def _ceil(moment: datetime, minutes: int) -> datetime:
    discard = timedelta(
        minutes=moment.minute % minutes,
        seconds=moment.second,
        microseconds=moment.microsecond,
    )
    return moment if discard == timedelta(0) else moment + timedelta(minutes=minutes) - discard


def _energy_score(start: datetime, end: datetime, prefs: SchedulingPrefs) -> float:
    cursor = start
    scores: list[int] = []
    while cursor < end:
        scores.append(prefs.energy_at(cursor.hour))
        cursor += timedelta(minutes=15)
    return sum(scores) / len(scores) if scores else 0.0


def propose_slots(
    request: ProposalRequest,
    busy_events: Iterable[FixedEvent],
    prefs: SchedulingPrefs,
) -> list[SchedulingCandidate]:
    """Rank free candidates while preserving the request's display timezone.

    Working-hour windows are interpreted in the timezone carried by
    ``request.earliest``. Busy events may use any aware timezone.
    """
    timezone_hint = request.earliest.tzinfo
    assert timezone_hint is not None
    busy = sorted(
        ((_utc(item.start), _utc(item.end)) for item in busy_events),
        key=lambda pair: (pair[0], pair[1]),
    )
    duration = timedelta(minutes=request.duration_minutes)
    before = timedelta(minutes=request.buffer_before_minutes)
    after = timedelta(minutes=request.buffer_after_minutes)
    step = timedelta(minutes=request.granularity_minutes)
    candidates: list[SchedulingCandidate] = []

    day = request.earliest.date()
    while day <= request.latest.date():
        for window in prefs.working_hours.get(day.weekday(), []):
            local_start = datetime.combine(day, datetime.min.time(), tzinfo=timezone_hint) + timedelta(
                minutes=window.start_minute
            )
            local_end = datetime.combine(day, datetime.min.time(), tzinfo=timezone_hint) + timedelta(
                minutes=window.end_minute
            )
            cursor = _ceil(max(local_start, request.earliest), request.granularity_minutes)
            ceiling = min(local_end, request.latest)
            while cursor + duration <= ceiling:
                end = cursor + duration
                blocked_start = _utc(cursor - before)
                blocked_end = _utc(end + after)
                if not any(blocked_start < event_end and blocked_end > event_start for event_start, event_end in busy):
                    energy = _energy_score(cursor, end, prefs)
                    reasons = (
                        f"energy fit {energy:.1f}/5",
                        "within working hours",
                        "no busy-event overlap including buffers",
                    )
                    # Energy dominates. Epoch term gives deterministic earlier tie-breaking.
                    score = round(energy * 100 - _utc(cursor).timestamp() / 1e9, 6)
                    candidates.append(SchedulingCandidate(cursor, end, score, reasons))
                cursor += step
        day += timedelta(days=1)

    candidates.sort(key=lambda item: (-item.score, _utc(item.start), _utc(item.end)))
    return candidates[: request.limit]
