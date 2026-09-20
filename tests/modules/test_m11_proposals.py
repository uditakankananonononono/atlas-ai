"""Focused tests for side-effect-free M11 scheduling proposals."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.modules.m11_calendar_intelligence.proposals import ProposalRequest, propose_slots
from app.modules.m11_calendar_intelligence.solver import FixedEvent, SchedulingPrefs, Window

UTC = timezone.utc
MONDAY = date(2026, 9, 21)


def at(hour: int, minute: int = 0, *, tz=UTC) -> datetime:
    return datetime(2026, 9, 21, hour, minute, tzinfo=tz)


def prefs(start=9 * 60, end=17 * 60) -> SchedulingPrefs:
    return SchedulingPrefs(
        working_hours={0: [Window(start, end)]},
        energy_curve={hour: (5 if hour < 12 else 2) for hour in range(24)},
    )


def test_proposes_ranked_free_slots_with_explainable_scores():
    candidates = propose_slots(
        ProposalRequest(at(9), at(17), 60, limit=2),
        [FixedEvent("busy", "standup", at(9), at(10))],
        prefs(),
    )

    assert [(item.start, item.end) for item in candidates] == [
        (at(10), at(11)),
        (at(10, 15), at(11, 15)),
    ]
    assert candidates[0].score > candidates[1].score
    assert "within working hours" in candidates[0].reasons


def test_buffers_block_slots_on_both_sides():
    candidates = propose_slots(
        ProposalRequest(
            at(9), at(12), 30, limit=20,
            buffer_before_minutes=15, buffer_after_minutes=15,
        ),
        [FixedEvent("busy", "call", at(10), at(11))],
        prefs(end=12 * 60),
    )

    intervals = {(item.start, item.end) for item in candidates}
    assert (at(9, 30), at(10)) not in intervals
    assert (at(11), at(11, 30)) not in intervals
    assert (at(9, 15), at(9, 45)) in intervals
    assert (at(11, 15), at(11, 45)) in intervals


def test_busy_events_in_other_timezones_are_normalized():
    india = timezone(timedelta(hours=5, minutes=30))
    busy = FixedEvent(
        "india", "call",
        datetime(2026, 9, 21, 14, 30, tzinfo=india),
        datetime(2026, 9, 21, 15, 30, tzinfo=india),
    )
    candidates = propose_slots(
        ProposalRequest(at(9), at(11), 30, limit=20), [busy], prefs(end=11 * 60)
    )

    assert all(not (item.start < at(10) and item.end > at(9)) for item in candidates)


def test_empty_result_is_explicit_when_duration_cannot_fit():
    result = propose_slots(
        ProposalRequest(at(9), at(10), 90), [], prefs(end=10 * 60)
    )
    assert result == []


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"earliest": datetime(2026, 9, 21, 9), "latest": at(10), "duration_minutes": 30}, "earliest"),
        ({"earliest": at(10), "latest": at(9), "duration_minutes": 30}, "latest must be after"),
        ({"earliest": at(9), "latest": at(10), "duration_minutes": 5}, "duration_minutes"),
        ({"earliest": at(9), "latest": at(10), "duration_minutes": 30, "granularity_minutes": 7}, "granularity"),
    ],
)
def test_invalid_requests_are_rejected(kwargs, match):
    with pytest.raises(ValueError, match=match):
        ProposalRequest(**kwargs)
