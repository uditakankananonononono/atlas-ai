"""Freshness ordering must compare instants, never ISO offset spellings."""
from datetime import datetime
from app.modules.m16_executive_dashboard.schemas import Event
from app.modules.m16_executive_dashboard.projector import fold

def event(id,at):
    return Event(id=id,sequence=int(id),topic='observed',aggregate_type='task',aggregate_id='a',payload={},occurred_at=datetime.fromisoformat(at))

def test_later_instant_with_earlier_local_clock_wins():
    first=event('1','2026-10-08T12:00:00+05:30')
    later=event('2','2026-10-08T08:00:00+00:00')
    data,_=fold({},[first,later])
    assert datetime.fromisoformat(data['freshness']['task/a'])==later.occurred_at

def test_older_offset_event_does_not_replace_later_utc_instant():
    later=event('1','2026-10-08T08:00:00+00:00')
    older=event('2','2026-10-08T12:00:00+05:30')
    data,_=fold({},[later,older])
    assert datetime.fromisoformat(data['freshness']['task/a'])==later.occurred_at
