"""Focused offline tests for M11 calendar conflict detection."""

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m11_calendar_intelligence.conflicts import (
    Availability,
    CalendarInterval,
    ConflictSeverity,
    DuplicateEventError,
    detect_conflicts,
)

UTC = timezone.utc


def moment(hour: int, minute: int = 0, *, tz=UTC) -> datetime:
    return datetime(2026, 9, 21, hour, minute, tzinfo=tz)


def event(event_id: str, start: datetime, end: datetime, **kwargs) -> CalendarInterval:
    return CalendarInterval(
        event_id=event_id,
        source_id=kwargs.pop("source_id", "primary"),
        summary=kwargs.pop("summary", event_id),
        start=start,
        end=end,
        **kwargs,
    )


def test_detects_all_nested_pairwise_conflicts_deterministically():
    events = [
        event("outer", moment(9), moment(12)),
        event("late", moment(10), moment(11)),
        event("early", moment(9, 30), moment(10, 30)),
    ]

    conflicts = detect_conflicts(reversed(events))

    assert [(item.left.event_id, item.right.event_id) for item in conflicts] == [
        ("outer", "early"),
        ("early", "late"),
        ("outer", "late"),
    ]
    assert [item.overlap_minutes for item in conflicts] == [60, 30, 60]


def test_boundary_touching_events_do_not_conflict():
    assert detect_conflicts([
        event("first", moment(9), moment(10)),
        event("second", moment(10), moment(11)),
    ]) == []


def test_timezone_offsets_are_compared_as_instants():
    india = timezone(timedelta(hours=5, minutes=30))
    conflicts = detect_conflicts([
        event("utc", moment(9), moment(10), source_id="google"),
        event(
            "india",
            datetime(2026, 9, 21, 14, 0, tzinfo=india),
            datetime(2026, 9, 21, 15, 0, tzinfo=india),
            source_id="caldav",
        ),
    ])

    assert len(conflicts) == 1
    assert conflicts[0].overlap_minutes == 30
    assert conflicts[0].overlap_start == moment(9)


def test_cancelled_and_free_events_are_ignored_and_tentative_is_soft():
    conflicts = detect_conflicts([
        event("busy", moment(9), moment(11)),
        event("cancelled", moment(9), moment(11), status="cancelled"),
        event("free", moment(9), moment(11), availability=Availability.FREE),
        event("maybe", moment(10), moment(12), availability=Availability.TENTATIVE),
    ])

    assert len(conflicts) == 1
    assert conflicts[0].right.event_id == "maybe"
    assert conflicts[0].severity is ConflictSeverity.SOFT


def test_minimum_overlap_and_cross_source_filter():
    events = [
        event("a", moment(9), moment(10), source_id="one"),
        event("b", moment(9, 50), moment(11), source_id="two"),
        event("c", moment(9, 45), moment(10, 15), source_id="one"),
    ]

    conflicts = detect_conflicts(
        events,
        minimum_overlap=timedelta(minutes=15),
        across_sources_only=True,
    )

    assert [item.id for item in conflicts] == ["one:c|two:b"]


@pytest.mark.parametrize(
    "start,end,match",
    [
        (datetime(2026, 9, 21, 9), moment(10), "timezone-aware"),
        (moment(10), moment(10), "after start"),
        (moment(11), moment(10), "after start"),
    ],
)
def test_invalid_intervals_are_rejected(start, end, match):
    with pytest.raises(ValueError, match=match):
        event("bad", start, end)


def test_duplicate_provider_event_keys_are_rejected():
    with pytest.raises(DuplicateEventError, match="duplicate event key"):
        detect_conflicts([
            event("same", moment(9), moment(10)),
            event("same", moment(11), moment(12)),
        ])
