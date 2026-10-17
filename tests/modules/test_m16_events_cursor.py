import pytest
from fastapi import HTTPException
from app.modules.m16_executive_dashboard import routes

class FakeService:
    def __init__(self):self.asked=[]
    def events_after(self,cursor,limit=500):self.asked.append(cursor);return []

@pytest.mark.parametrize("cursor",[2**63,-(2**63)-1,10**30])
def test_events_cursor_outside_int64_is_422_without_query(cursor):
    svc=FakeService()
    with pytest.raises(HTTPException) as ei:routes.events(cursor,svc)
    assert ei.value.status_code==422 and svc.asked==[]

@pytest.mark.parametrize("cursor",[0,-1,-(2**63),2**63-1])
def test_events_cursor_in_range_reaches_service(cursor):
    svc=FakeService();assert routes.events(cursor,svc)==[] and svc.asked==[cursor]
