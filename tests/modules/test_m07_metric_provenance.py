from datetime import date, datetime, timezone, timedelta
import pytest
from app.modules.m07_brand_collaboration.metric_provenance import *

U = timezone.utc
def ev(at, metric="views", value=10, kind="metric"):
    return {"kind": kind, "occurred_at": at, "data": {"metric": metric, "value": value}}
S, E = date(2026, 1, 1), date(2026, 1, 31)

def test_verified_and_partial_and_unsupported():
    evs = [ev(datetime(2026,1,5,tzinfo=U)), ev(datetime(2026,1,6,tzinfo=U), value=15), ev(datetime(2026,1,7,tzinfo=U), "clicks", 3)]
    v = {x.metric: x for x in verify_metrics({"views": 25, "clicks": 4, "reach": 9}, evs, S, E)}
    assert v["views"].label == VERIFIED and v["views"].event_count == 2
    assert v["clicks"].label == PARTIAL and v["clicks"].ledger_total == 3
    assert v["reach"].label == UNSUPPORTED
    assert summary(v.values()) == {VERIFIED:1, PARTIAL:1, UNSUPPORTED:1, INVALID:0, "total":3}

def test_period_is_inclusive_utc_with_offsets():
    last_ok = datetime(2026,1,31,23,59,59,tzinfo=U)
    ist_in = datetime(2026,2,1,4,0,tzinfo=timezone(timedelta(hours=5,minutes=30)))  # Jan 31 22:30 UTC
    ist_out = datetime(2026,2,1,5,30,tzinfo=timezone(timedelta(hours=5,minutes=30)))  # Feb 1 00:00 UTC
    first = datetime(2026,1,1,0,0,tzinfo=U)
    r = verify_metrics({"views": 30}, [ev(last_ok), ev(ist_in), ev(first), ev(ist_out)], S, E)[0]
    assert r.label == VERIFIED and r.event_count == 3

def test_ignored_events():
    bad = [ev(datetime(2026,1,5), value=10), ev(datetime(2026,1,5,tzinfo=U), kind="deal"),
           ev(datetime(2026,1,5,tzinfo=U), value=True), ev(datetime(2026,1,5,tzinfo=U), value=float("nan"))]
    assert verify_metrics({"views": 10}, bad, S, E)[0].label == UNSUPPORTED

def test_invalid_claims_and_periods():
    assert verify_metrics({"a": -1, "b": float("inf")}, [], S, E)[0].label == INVALID
    with pytest.raises(PeriodError): verify_metrics({}, [], E, S)
    with pytest.raises(PeriodError): verify_metrics({}, [], S, date(2030,1,1), today=date(2026,10,8))
    assert utc_bounds(S, S)[1] - utc_bounds(S, S)[0] == timedelta(days=1)

def test_mutant_exclusive_end_is_caught():
    # an event on the end date must count; exclusive-end bug would make this UNSUPPORTED
    assert verify_metrics({"views": 10}, [ev(datetime(2026,1,31,12,tzinfo=U))], S, E)[0].label == VERIFIED
