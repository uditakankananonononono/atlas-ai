"""Focused RFC 5545 timezone tests for M11 calendar sync."""

from datetime import datetime, timedelta, timezone

from app.modules.m11_calendar_intelligence.ics import parse_ics_events
from app.modules.m11_calendar_intelligence.sync_validation import validate_sync_batch


def calendar(start: str, end: str) -> str:
    return f"""BEGIN:VCALENDAR
BEGIN:VEVENT
UID:tz-1
SUMMARY:Zoned call
DTSTART{start}
DTEND{end}
END:VEVENT
END:VCALENDAR
"""


def test_iana_tzid_is_preserved_then_sync_normalizes_the_instant():
    events = parse_ics_events(calendar(
        ";TZID=Asia/Kolkata:20260921T143000",
        ";TZID=Asia/Kolkata:20260921T153000",
    ))

    assert events[0].start.utcoffset() == timedelta(hours=5, minutes=30)
    synced = validate_sync_batch(events)
    assert synced[0].start == datetime(2026, 9, 21, 9, tzinfo=timezone.utc)
    assert synced[0].end == datetime(2026, 9, 21, 10, tzinfo=timezone.utc)


def test_tzid_observes_daylight_saving_offset_for_event_date():
    winter = parse_ics_events(calendar(
        ";TZID=America/New_York:20260121T090000",
        ";TZID=America/New_York:20260121T100000",
    ))[0]
    summer = parse_ics_events(calendar(
        ";TZID=America/New_York:20260721T090000",
        ";TZID=America/New_York:20260721T100000",
    ))[0]

    assert winter.start.utcoffset() == timedelta(hours=-5)
    assert summer.start.utcoffset() == timedelta(hours=-4)


def test_unknown_tzid_does_not_silently_claim_utc_instant():
    event = parse_ics_events(calendar(
        ";TZID=Mars/Olympus:20260921T090000",
        ";TZID=Mars/Olympus:20260921T100000",
    ))[0]
    assert event.start is None and event.end is None


def test_floating_time_keeps_documented_legacy_utc_interpretation():
    event = parse_ics_events(calendar(
        ":20260921T090000",
        ":20260921T100000",
    ))[0]
    assert event.start == datetime(2026, 9, 21, 9, tzinfo=timezone.utc)
