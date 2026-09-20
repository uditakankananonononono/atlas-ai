"""Focused provider-boundary validation tests for M11 sync."""

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m11_calendar_intelligence.ics import IcsEvent
from app.modules.m11_calendar_intelligence.sync_validation import (
    InvalidSyncBatchError,
    validate_sync_batch,
)

UTC = timezone.utc


def at(hour: int, *, tz=UTC) -> datetime:
    return datetime(2026, 9, 21, hour, tzinfo=tz)


def test_normalizes_provider_events_to_utc_and_canonical_fields():
    india = timezone(timedelta(hours=5, minutes=30))
    event = IcsEvent(
        uid="  event-1 ", summary="  Planning  ",
        start=at(14, tz=india), end=at(15, tz=india),
        location="  Studio ", status="TENTATIVE",
    )

    result = validate_sync_batch([event])

    assert result[0].uid == "event-1"
    assert result[0].summary == "Planning"
    assert result[0].location == "Studio"
    assert result[0].status == "tentative"
    assert result[0].start == datetime(2026, 9, 21, 8, 30, tzinfo=UTC)
    assert result[0].start.utcoffset() == timedelta(0)


def test_cancelled_tombstone_without_times_is_valid():
    result = validate_sync_batch([
        IcsEvent(uid="gone", summary="", status="cancelled")
    ])
    assert result[0].start is None and result[0].end is None
    assert result[0].summary == "(no title)"


@pytest.mark.parametrize(
    "events,match",
    [
        ([IcsEvent(uid="", start=at(9), end=at(10))], "missing uid"),
        ([IcsEvent(uid="x", start=at(9), end=at(10)), IcsEvent(uid="x", start=at(11), end=at(12))], "duplicate uid"),
        ([IcsEvent(uid="x", start=datetime(2026, 9, 21, 9), end=at(10))], "naive start"),
        ([IcsEvent(uid="x", start=at(10), end=at(9))], "end must be after"),
        ([IcsEvent(uid="x", start=at(9), end=None)], "requires start and end"),
        ([IcsEvent(uid="x", start=at(9), end=at(10), status="mystery")], "unsupported status"),
        ([IcsEvent(uid="x", start=at(9), end=None, status="cancelled")], "both times or neither"),
    ],
)
def test_rejects_unsafe_provider_batches(events, match):
    with pytest.raises(InvalidSyncBatchError, match=match):
        validate_sync_batch(events)
