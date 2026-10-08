"""Exact calendar occupancy from aware event instants, with a JSON stdin CLI.

This module deliberately has no provider, database, auth or network dependencies.
It does not change Service.meeting_load or reinterpret its legacy minutes field.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
import json
import sys
from typing import Iterable
from zoneinfo import ZoneInfo

UTC = timezone.utc


@dataclass(frozen=True)
class OccupancyEvent:
    event_id: str
    start: datetime
    end: datetime
    busy: bool = True
    cancelled: bool = False


@dataclass(frozen=True)
class DayOccupancy:
    date: str
    day_seconds: float
    event_count: int
    occupied_seconds: float
    event_seconds: float
    overlapping_seconds: float
    peak_concurrency: int
    free_seconds: float


@dataclass(frozen=True)
class OccupancyReport:
    start_date: str
    timezone: str
    days: tuple[DayOccupancy, ...]
    occupied_seconds: float
    event_seconds: float
    overlapping_seconds: float


def _instant(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("event endpoints must be timezone-aware datetimes")
    utc = value.astimezone(UTC)
    # Reject fabricated ZoneInfo wall times within spring-forward gaps.
    if utc.astimezone(value.tzinfo).replace(tzinfo=None) != value.replace(tzinfo=None):
        raise ValueError("event endpoint is a nonexistent local wall time")
    return utc


def _day_boundary(day: date, zone: ZoneInfo) -> datetime:
    """First real instant of a civil date, including midnight gaps/skipped dates.

    Ambiguous midnight uses its earlier occurrence. For a nonexistent midnight,
    binary search the two fold mappings for the date boundary. A skipped date
    has the same boundary as the next date and therefore zero elapsed seconds.
    """
    naive = datetime.combine(day, time.min)
    candidates = sorted({naive.replace(tzinfo=zone, fold=f).astimezone(UTC) for f in (0, 1)})
    valid = [c for c in candidates if c.astimezone(zone).replace(tzinfo=None) == naive]
    if valid:
        return valid[0]
    lower, upper = candidates[0], candidates[-1]
    if lower == upper:
        raise ValueError("could not resolve civil day boundary")
    while upper - lower > timedelta(microseconds=1):
        middle = lower + (upper - lower) // 2
        if middle.astimezone(zone).date() >= day:
            upper = middle
        else:
            lower = middle
    return upper


def _microseconds(delta: timedelta) -> int:
    return ((delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds)


def calendar_occupancy(events: Iterable[OccupancyEvent], start_date: date,
                       timezone_name: str = "UTC", day_count: int = 7) -> OccupancyReport:
    """Clip events into local days and sweep endpoints, without sampling.

    Intervals are half-open [start, end). Busy, non-cancelled events count.
    event_seconds sums individual clipped durations; occupied_seconds measures
    their union. overlapping_seconds is elapsed time with at least two events,
    not the extra event-duration sum. No times are rounded to whole minutes.
    """
    if not isinstance(start_date, date) or isinstance(start_date, datetime):
        raise ValueError("start_date must be a date")
    if type(day_count) is not int or not 1 <= day_count <= 366:
        raise ValueError("day_count must be an integer between 1 and 366")
    zone = ZoneInfo(timezone_name)
    boundaries = [_day_boundary(start_date + timedelta(days=i), zone)
                  for i in range(day_count + 1)]
    if any(b < a for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError("timezone produced nonmonotonic date boundaries")
    intervals = []
    seen = set()
    for event in events:
        if not isinstance(event, OccupancyEvent):
            raise ValueError("events must be OccupancyEvent records")
        if not isinstance(event.event_id, str) or not event.event_id or event.event_id in seen:
            raise ValueError("event_id must be nonempty and unique")
        seen.add(event.event_id)
        if type(event.busy) is not bool or type(event.cancelled) is not bool:
            raise ValueError("busy and cancelled must be booleans")
        start, end = _instant(event.start), _instant(event.end)
        if end <= start:
            raise ValueError("event end must be after start")
        if event.busy and not event.cancelled and start < boundaries[-1] and end > boundaries[0]:
            intervals.append((start, end))
    days = []
    for i, (left, right) in enumerate(zip(boundaries, boundaries[1:])):
        changes: dict[datetime, int] = {}
        count = event_us = 0
        for start, end in intervals:
            start, end = max(start, left), min(end, right)
            if start >= end:
                continue
            count += 1
            event_us += _microseconds(end - start)
            changes[start] = changes.get(start, 0) + 1
            changes[end] = changes.get(end, 0) - 1
        active = peak = occupied_us = overlap_us = 0
        previous = left
        for instant, change in sorted(changes.items()):
            elapsed = _microseconds(instant - previous)
            if active:
                occupied_us += elapsed
            if active >= 2:
                overlap_us += elapsed
            active += change
            peak = max(peak, active)
            previous = instant
        day_us = _microseconds(right - left)
        days.append(DayOccupancy(
            (start_date + timedelta(days=i)).isoformat(), day_us / 1e6, count,
            occupied_us / 1e6, event_us / 1e6, overlap_us / 1e6, peak,
            (day_us - occupied_us) / 1e6))
    return OccupancyReport(start_date.isoformat(), timezone_name, tuple(days),
                           sum(d.occupied_seconds for d in days),
                           sum(d.event_seconds for d in days),
                           sum(d.overlapping_seconds for d in days))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--timezone", default="UTC")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, list):
            raise ValueError("stdin must be an event array")
        events = []
        for row in payload:
            if not isinstance(row, dict) or set(row) - {"event_id", "start", "end", "busy", "cancelled"}:
                raise ValueError("event objects have unknown fields or invalid shape")
            events.append(OccupancyEvent(
                row["event_id"], datetime.fromisoformat(row["start"]),
                datetime.fromisoformat(row["end"]), row.get("busy", True),
                row.get("cancelled", False)))
        result = calendar_occupancy(events, date.fromisoformat(args.start_date), args.timezone, args.days)
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        # Generic error classes only: never echo event payloads or credentials.
        print(json.dumps({"error": "invalid_calendar_input", "type": type(exc).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
