"""DST-safe local-time scheduling: resolver, service gate, and HTTP route."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m06_social_media_manager.local_time import (
    AmbiguousLocalTimeError, InvalidTimezoneError, LocalTimeError, NonexistentLocalTimeError, resolve_local,
)
from tests.modules.test_m06_routes_extended import DUE, make_client, make_plan  # noqa: F401
from tests.modules.test_m06_schedule_verify_lane import REFS, SRC, _build

UTC = timezone.utc
NY = "America/New_York"


def test_fixed_offset_zone_ist():
    r = resolve_local(datetime(2026, 10, 8, 17, 30), "Asia/Kolkata")
    assert r.instant_utc == datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    assert r.utc_offset_minutes == 330 and not r.ambiguous and not r.in_gap and r.adjustment is None


def test_dst_summer_and_winter_offsets_differ():
    s = resolve_local(datetime(2026, 7, 1, 9, 0), NY)
    w = resolve_local(datetime(2026, 12, 1, 9, 0), NY)
    assert s.instant_utc.hour == 13 and s.utc_offset_minutes == -240
    assert w.instant_utc.hour == 14 and w.utc_offset_minutes == -300


def test_gap_rejected_by_default_and_shiftable():
    gap = datetime(2026, 3, 8, 2, 30)  # spring forward, 02:00 -> 03:00
    with pytest.raises(NonexistentLocalTimeError):
        resolve_local(gap, NY)
    r = resolve_local(gap, NY, on_gap="shift_forward")
    assert r.in_gap and r.adjustment == "shifted_forward_over_dst_gap"
    assert r.instant_utc == datetime(2026, 3, 8, 7, 30, tzinfo=UTC)
    assert r.local_resolved == "2026-03-08T03:30:00"


def test_fold_rejected_by_default_and_both_policies():
    fold = datetime(2026, 11, 1, 1, 30)  # fall back, 02:00 -> 01:00
    with pytest.raises(AmbiguousLocalTimeError):
        resolve_local(fold, NY)
    early = resolve_local(fold, NY, on_ambiguous="earlier")
    late = resolve_local(fold, NY, on_ambiguous="later")
    assert early.instant_utc == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert late.instant_utc == datetime(2026, 11, 1, 6, 30, tzinfo=UTC)
    assert late.instant_utc - early.instant_utc == timedelta(hours=1) and early.ambiguous


def test_edges_just_outside_gap_and_fold_are_plain():
    assert resolve_local(datetime(2026, 3, 8, 1, 59), NY).adjustment is None
    assert resolve_local(datetime(2026, 3, 8, 3, 0), NY).adjustment is None
    assert resolve_local(datetime(2026, 11, 1, 0, 59), NY).ambiguous is False
    assert resolve_local(datetime(2026, 11, 1, 2, 0), NY).ambiguous is False


@pytest.mark.parametrize("bad", ["", "  ", "Mars/Olympus", "local", "IST+5", "../etc/passwd"])
def test_unknown_timezone_is_an_error_never_utc(bad):
    with pytest.raises(InvalidTimezoneError):
        resolve_local(datetime(2026, 10, 8, 17, 30), bad)


def test_rejects_aware_input_and_bad_policy():
    with pytest.raises(LocalTimeError):
        resolve_local(datetime(2026, 10, 8, 17, 30, tzinfo=UTC), "Asia/Kolkata")
    with pytest.raises(LocalTimeError):
        resolve_local(datetime(2026, 10, 8, 17, 30), "Asia/Kolkata", on_gap="guess")


def test_service_files_approval_with_resolved_instant():
    svc, store, sch, repo, adapter, dec = _build()
    reqs, resolved = svc.request_schedule_local("p1", datetime(2026, 10, 8, 17, 30), "Asia/Kolkata", references=REFS)
    assert datetime.fromisoformat(reqs[0].payload["publish_at"]) == datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    assert repo.get_schedule(reqs[0].payload["schedule_id"]).publish_at == resolved.instant_utc


def test_service_bad_zone_or_gap_files_nothing():
    svc, store, sch, repo, *_ = _build()
    for args, exc in [(("Mars/Olympus", datetime(2026, 10, 8, 17, 30)), InvalidTimezoneError),
                      ((NY, datetime(2026, 3, 8, 2, 30)), NonexistentLocalTimeError),
                      ((NY, datetime(2026, 11, 1, 1, 30)), AmbiguousLocalTimeError)]:
        with pytest.raises(exc):
            svc.request_schedule_local("p1", args[1], args[0], references=REFS)
    assert store.items == [] and repo.list_schedules() == []
    assert svc.get_plan("p1").status == "draft"


def test_publishes_at_the_right_instant_only():
    svc, store, sch, repo, adapter, dec = _build()
    reqs, _ = svc.request_schedule_local("p1", datetime(2026, 10, 8, 17, 30), "Asia/Kolkata", references=REFS)
    dec.s[reqs[0].id] = "approved"
    sch.sync_decisions()
    # _build clock is 12:00Z; one minute earlier it must not be due, at 12:00Z it is.
    assert sch.execute_due(datetime(2026, 10, 8, 11, 59, tzinfo=UTC)) == []
    assert len(sch.execute_due(datetime(2026, 10, 8, 12, 0, tzinfo=UTC))) == 1


def test_route_success_and_errors():
    client, store, decisions, adapter, _repo = make_client()
    plan = make_plan(client)
    url = f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule-local'
    ok = client.post(url, json={"local_time": "2026-10-08T17:30:00", "timezone": "Asia/Kolkata"})
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["resolved"]["instant_utc"] == "2026-10-08T12:00:00+00:00" and body["resolved"]["utc_offset_minutes"] == 330
    assert body["approvals"][0]["payload"]["publish_at"] == "2026-10-08T12:00:00+00:00"
    n = len(store.items)
    for payload, code in [
        ({"local_time": "2026-10-08T17:30:00+05:30", "timezone": "Asia/Kolkata"}, 422),
        ({"local_time": "2026-10-08T17:30:00", "timezone": "Nowhere/City"}, 422),
        ({"local_time": "2026-03-08T02:30:00", "timezone": NY}, 422),
        ({"local_time": "2026-11-01T01:30:00", "timezone": NY}, 422),
        ({"local_time": "2026-11-01T01:30:00", "timezone": NY, "on_ambiguous": "maybe"}, 422),
    ]:
        assert client.post(url, json=payload).status_code == code, payload
    assert len(store.items) == n
    assert client.post(url, json={"local_time": "2026-11-01T01:30:00", "timezone": NY, "on_ambiguous": "later"}).status_code == 201
    assert client.post("/api/v1/social-media-manager/plans/nope/schedule-local",
                       json={"local_time": "2026-10-08T17:30:00", "timezone": "Asia/Kolkata"}).status_code == 404
