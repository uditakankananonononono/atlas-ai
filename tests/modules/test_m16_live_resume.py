"""M16 /live SSE resume via Last-Event-ID (authored, not run: pydantic/fastapi absent in author env)."""
import asyncio
from datetime import datetime,timezone
from app.modules.m16_executive_dashboard import routes
from app.modules.m16_executive_dashboard.schemas import Event

def _ev(n):return Event(id=f"e{n}",sequence=n,topic="t",aggregate_type="a",aggregate_id="x",payload={},occurred_at=datetime(2026,10,15,tzinfo=timezone.utc))

class FakeService:
    def __init__(self,events):self.events=events;self.asked=[]
    def events_after(self,cursor,limit=500):
        self.asked.append(cursor);return [e for e in self.events if e.sequence>cursor]

class FakeRequest:
    def __init__(self,headers,disconnect_after=2):self.headers=headers;self.n=0;self.limit=disconnect_after
    async def is_disconnected(self):
        self.n+=1;return self.n>self.limit

def _run(headers,cursor=0):
    svc=FakeService([_ev(1),_ev(2),_ev(3)]);req=FakeRequest(headers)
    async def go():
        resp=await routes.live(req,cursor=cursor,service=svc)
        return [c async for c in resp.body_iterator]
    return asyncio.run(go()),svc

def _ids(chunks):return [int(c.split("\n",1)[0][4:]) for c in chunks if c.startswith("id: ")]

def test_no_header_replays_from_cursor():
    chunks,_=_run({},cursor=1);assert _ids(chunks)==[2,3]

def test_last_event_id_header_resumes_after_it():
    chunks,svc=_run({"last-event-id":"2"},cursor=0);assert _ids(chunks)==[3];assert svc.asked[0]==2

def test_header_never_moves_backwards_past_cursor():
    chunks,svc=_run({"last-event-id":"1"},cursor=2);assert _ids(chunks)==[3];assert svc.asked[0]==2

def test_bad_header_values_are_ignored():
    for bad in ("abc","-1","","  ","2.5","\u0662","1e3","0x2"," -2","2 3","9"*19,"9"*20,"9"*5000,"9223372036854775808"):
        chunks,svc=_run({"last-event-id":bad},cursor=1);assert _ids(chunks)==[2,3],bad;assert svc.asked[0]==1

def test_header_at_int64_max_is_honored_and_whitespace_trimmed():
    chunks,svc=_run({"last-event-id":" 2 "},cursor=0);assert _ids(chunks)==[3];assert svc.asked[0]==2
    chunks,svc=_run({"last-event-id":"9223372036854775807"},cursor=0);assert _ids(chunks)==[] and svc.asked[0]==9223372036854775807

def test_leading_zeros_are_plain_digits():
    chunks,svc=_run({"last-event-id":"0002"},cursor=0);assert svc.asked[0]==2

def test_cursor_beyond_int64_is_refused_before_streaming():
    import pytest
    from fastapi import HTTPException
    svc=FakeService([_ev(1)]);req=FakeRequest({})
    with pytest.raises(HTTPException) as ei:asyncio.run(routes.live(req,cursor=2**63,service=svc))
    assert ei.value.status_code==422 and svc.asked==[]

def test_cursor_at_int64_max_still_streams_nothing():
    chunks,svc=_run({},cursor=2**63-1);assert _ids(chunks)==[] and svc.asked[0]==2**63-1

def test_cursor_below_int64_min_is_refused_before_streaming():
    import pytest
    from fastapi import HTTPException
    svc=FakeService([_ev(1)]);req=FakeRequest({})
    with pytest.raises(HTTPException) as ei:asyncio.run(routes.live(req,cursor=-(2**63)-1,service=svc))
    assert ei.value.status_code==422 and svc.asked==[]

def test_in_range_negative_cursors_still_stream_everything():
    for c in (-1,-(2**63)):
        chunks,svc=_run({},cursor=c);assert _ids(chunks)==[1,2,3] and svc.asked[0]==c
