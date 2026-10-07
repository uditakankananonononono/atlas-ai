"""Offline tests for module 11 (Calendar Intelligence): sync, solver,
conflict resolution, approval gating, analytics, tenant isolation."""

import asyncio
from datetime import date, datetime, time, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalRequest
from app.core.token_crypto import TokenCipher
from app.modules.m11_calendar_intelligence.caldav import HttpxCalDAVClient, parse_multistatus
from app.modules.m11_calendar_intelligence.google_calendar import (
    EventPage,
    SyncTokenExpiredError,
    WatchInfo,
)
from app.modules.m11_calendar_intelligence.ics import parse_ics_events
from app.modules.m11_calendar_intelligence.schemas import (
    CalDAVSourceCreate,
    GoogleSourceCreate,
    SchedulingPrefsSchema,
    SchedulingTaskCreate,
    WindowSchema,
)
from app.modules.m11_calendar_intelligence.service import (
    ApprovalNotGrantedError,
    ChannelVerificationError,
    Service,
)
from app.modules.m11_calendar_intelligence.solver import (
    BuiltInSolver,
    FixedEvent,
    InfeasibleScheduleError,
    SchedulingPrefs,
    TaskSpec,
    Window,
)
from app.modules.m11_calendar_intelligence.sql_repository import SqlCalendarRepository

MASTER = "test-master-secret"
UTC = timezone.utc


class FakeGoogleCalendarClient:
    def __init__(self):
        self.watch_calls = []
        self.pages = []  # list of EventPage or SyncTokenExpiredError
        self.sync_tokens_seen = []

    async def watch(self, access_token, calendar_id, *, channel_id, address, token):
        self.watch_calls.append((calendar_id, channel_id, token))
        return WatchInfo(channel_id=channel_id, resource_id="res-1",
                         expiration_ms=1731000000000)

    async def list_events(self, access_token, calendar_id, *, sync_token, time_min):
        self.sync_tokens_seen.append(sync_token)
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return page

    async def stop_channel(self, access_token, *, channel_id, resource_id):
        pass


class FakeCalDAVClient:
    def __init__(self, events):
        self.events = events

    async def fetch_events(self, calendar_url, start, end):
        return self.events


class FakeApprovalGate:
    def __init__(self):
        self.items = {}
        self.decisions = {}

    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        self.items[item.id] = item
        return item

    def status(self, approval_id: str) -> str:
        return self.decisions.get(approval_id, "pending")

    def payload(self, approval_id: str) -> dict:
        return self.items[approval_id].payload

    def approve(self, approval_id: str) -> None:
        self.decisions[approval_id] = "approved"


def make_service(tmp_path, tenant="tenant-a", google=None, caldav=None):
    engine = create_engine(f"sqlite:///{tmp_path}/{tenant}.db")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    repo = SqlCalendarRepository(tenant, sessions)
    gate = FakeApprovalGate()
    async def fixture_exchange(refresh_token):
        return "fixture-access"
    service = Service(
        repo, gate,
        google_access_token_provider=fixture_exchange, cipher=TokenCipher(tenant, master_secret=MASTER),
        google=google or FakeGoogleCalendarClient(), caldav=caldav,
    )
    return service, repo, gate


def dt(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=UTC)


MONDAY = date(2026, 9, 21)


# -- ICS parsing ------------------------------------------------------------

def test_ics_parses_events_folding_allday_and_status():
    text = (
        "BEGIN:VCALENDAR\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:evt-1\r\n"
        "SUMMARY:Long meeting name that is folded acr\r\n"
        " oss lines\r\n"
        "DTSTART:20260921T090000Z\r\n"
        "DTEND:20260921T100000Z\r\n"
        "LOCATION:Office\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:evt-2\r\n"
        "SUMMARY:All day\r\n"
        "DTSTART;VALUE=DATE:20260922\r\n"
        "STATUS:CANCELLED\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    events = parse_ics_events(text)
    assert len(events) == 2
    assert events[0].summary == "Long meeting name that is folded across lines"
    assert events[0].start == dt(MONDAY, 9) and events[0].location == "Office"
    assert events[1].start == dt(date(2026, 9, 22), 0) and events[1].status == "cancelled"


def test_caldav_multistatus_parse():
    xml = """<?xml version="1.0"?>
    <d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
      <d:response>
        <d:href>/cal/user/evt1.ics</d:href>
        <d:propstat><d:prop><c:calendar-data>BEGIN:VCALENDAR
BEGIN:VEVENT
UID:evt-9
SUMMARY:Caldav sync
DTSTART:20260921T140000Z
DTEND:20260921T150000Z
END:VEVENT
END:VCALENDAR</c:calendar-data></d:prop></d:propstat>
      </d:response>
    </d:multistatus>"""
    events = parse_multistatus(xml)
    assert len(events) == 1 and events[0].uid == "evt-9" and events[0].summary == "Caldav sync"


def test_caldav_client_report_round_trip():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "REPORT"
        assert request.headers["Depth"] == "1"
        assert b"time-range" in request.content
        return httpx.Response(207, text="""<?xml version="1.0"?>
        <d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
          <d:response><d:propstat><d:prop><c:calendar-data>BEGIN:VCALENDAR
BEGIN:VEVENT
UID:evt-r
SUMMARY:Report event
DTSTART:20260921T140000Z
DTEND:20260921T150000Z
END:VEVENT
END:VCALENDAR</c:calendar-data></d:prop></d:propstat></d:response>
        </d:multistatus>""")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            caldav = HttpxCalDAVClient(client, "user@example.com", "app-password")
            events = await caldav.fetch_events(
                "https://caldav.example.com/cal/", dt(MONDAY, 0), dt(MONDAY + timedelta(days=7), 0))
            assert [e.uid for e in events] == ["evt-r"]

    asyncio.run(run())


# -- Google watch + sync ------------------------------------------------------

def test_watch_notification_sync_and_tamper_rejection(tmp_path):
    from app.modules.m11_calendar_intelligence.ics import IcsEvent

    google = FakeGoogleCalendarClient()
    google.pages = [
        EventPage(events=[IcsEvent(uid="g1", summary="Standup", start=dt(MONDAY, 9),
                                   end=dt(MONDAY, 9, 30))], next_sync_token="tok2"),
        EventPage(events=[IcsEvent(uid="g1", summary="Standup", start=dt(MONDAY, 9),
                                   end=dt(MONDAY, 9, 30), status="cancelled")],
                  next_sync_token="tok3"),
    ]
    service, repo, gate = make_service(tmp_path, google=google)
    source = service.register_google_source(GoogleSourceCreate(
        account_email="me@example.com", calendar_id="primary", refresh_token="rt"))
    watched = asyncio.run(service.ensure_watch(source.id))
    assert watched.watch_expiration is not None

    channel_id = google.watch_calls[0][1]
    token = google.watch_calls[0][2]

    with pytest.raises(ChannelVerificationError):
        asyncio.run(service.handle_google_notification(
            channel_id=channel_id, channel_token="forged", resource_state="exists"))

    result = asyncio.run(service.handle_google_notification(
        channel_id=channel_id, channel_token=token, resource_state="exists"))
    assert result.upserted == 1 and result.cancelled == 0
    assert repo.get_source(source.id).sync_token == "tok2"

    result2 = asyncio.run(service.handle_google_notification(
        channel_id=channel_id, channel_token=token, resource_state="exists"))
    assert result2.cancelled == 1
    cancelled = repo.list_events(include_cancelled=True)
    assert cancelled[0].status == "cancelled"
    assert google.sync_tokens_seen == [None, "tok2"]  # incremental after first


def test_sync_token_expiry_triggers_full_resync(tmp_path):
    from app.modules.m11_calendar_intelligence.ics import IcsEvent

    google = FakeGoogleCalendarClient()
    google.pages = [
        SyncTokenExpiredError("gone"),
        EventPage(events=[IcsEvent(uid="g1", summary="Full", start=dt(MONDAY, 9),
                                   end=dt(MONDAY, 10))], next_sync_token="fresh"),
    ]
    service, repo, gate = make_service(tmp_path, google=google)
    source = service.register_google_source(GoogleSourceCreate(
        account_email="me@example.com", calendar_id="primary", refresh_token="rt"))
    repo.update_sync_token(source.id, "stale-token")
    result = asyncio.run(service.sync_source(source.id))
    assert result.full_resync is True and result.upserted == 1
    assert repo.get_source(source.id).sync_token == "fresh"


def test_caldav_source_sync(tmp_path):
    from app.modules.m11_calendar_intelligence.ics import IcsEvent

    caldav = FakeCalDAVClient(events=[
        IcsEvent(uid="c1", summary="Apple cal", start=dt(MONDAY, 11), end=dt(MONDAY, 12))])
    service, repo, gate = make_service(tmp_path, caldav=caldav)
    source = service.register_caldav_source(CalDAVSourceCreate(
        account_email="me@icloud.com", calendar_url="https://caldav.icloud.com/cal/",
        username="me", password="app-pw"))
    result = asyncio.run(service.sync_source(source.id))
    assert result.upserted == 1
    assert service.list_events()[0].summary == "Apple cal"


def test_tenant_isolation(tmp_path):
    service_a, repo_a, _ = make_service(tmp_path, tenant="tenant-a")
    service_b, repo_b, _ = make_service(tmp_path, tenant="tenant-b")
    source = service_a.register_google_source(GoogleSourceCreate(
        account_email="me@example.com", calendar_id="primary", refresh_token="rt"))
    assert repo_b.get_source(source.id) is None
    assert service_b.list_sources() == []


# -- solver -------------------------------------------------------------------

def prefs(**overrides):
    base = SchedulingPrefs.default()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_solver_places_within_working_hours_before_deadline():
    task = TaskSpec(id="t1", title="Write essay", duration_minutes=120,
                    deadline=dt(MONDAY + timedelta(days=2), 17))
    placements = BuiltInSolver().solve([task], [], prefs(), MONDAY)
    block = [p for p in placements if p.kind == "task"][0]
    assert block.start.weekday() in range(7)
    assert 9 <= block.start.hour < 17
    assert block.end <= dt(MONDAY + timedelta(days=2), 17)


def test_solver_avoids_fixed_events():
    fixed = [FixedEvent(id="e1", summary="All day workshop",
                        start=dt(MONDAY, 9), end=dt(MONDAY, 17))]
    task = TaskSpec(id="t1", title="Deep work", duration_minutes=60,
                    deadline=dt(MONDAY + timedelta(days=1), 17))
    placements = BuiltInSolver().solve([task], fixed, prefs(), MONDAY)
    block = [p for p in placements if p.kind == "task"][0]
    assert block.start >= dt(MONDAY, 17)  # Monday fully busy


def test_solver_inserts_travel_buffer_between_locations():
    fixed = [FixedEvent(id="e1", summary="Office meeting",
                        start=dt(MONDAY, 9), end=dt(MONDAY, 10), location="Office")]
    task = TaskSpec(id="t1", title="Home work", duration_minutes=30,
                    deadline=dt(MONDAY, 17), location="Home", priority=5)
    p = prefs(travel_minutes_default=30)
    placements = BuiltInSolver().solve([task], fixed, p, MONDAY)
    block = [x for x in placements if x.kind == "task"][0]
    assert block.start >= dt(MONDAY, 10, 30)


def test_solver_schedules_prep_block_immediately_before():
    task = TaskSpec(id="t1", title="Interview", duration_minutes=60,
                    deadline=dt(MONDAY, 17), prep_minutes=45)
    placements = BuiltInSolver().solve([task], [], prefs(), MONDAY)
    prep = [p for p in placements if p.kind == "prep"][0]
    work = [p for p in placements if p.kind == "task"][0]
    assert prep.end == work.start
    assert (prep.end - prep.start) == timedelta(minutes=45)


def test_solver_prefers_high_energy_slots():
    task = TaskSpec(id="t1", title="Hard problem", duration_minutes=60,
                    deadline=dt(MONDAY, 17))
    energy = {h: 1 for h in range(24)}
    energy.update({15: 5, 16: 5})
    placements = BuiltInSolver().solve([task], [], prefs(energy_curve=energy), MONDAY)
    block = [p for p in placements if p.kind == "task"][0]
    assert block.start.hour == 15


def test_solver_protects_focus_blocks():
    focus = {MONDAY.weekday(): [Window(9 * 60, 12 * 60)]}
    task = TaskSpec(id="t1", title="Task", duration_minutes=60,
                    deadline=dt(MONDAY, 17), priority=5)
    placements = BuiltInSolver().solve([task], [], prefs(focus_blocks=focus), MONDAY)
    block = [p for p in placements if p.kind == "task"][0]
    assert block.start >= dt(MONDAY, 12)


def test_solver_splits_splittable_tasks():
    fixed = [FixedEvent(id=f"e{i}", summary="meeting",
                        start=dt(MONDAY, 10 + 2 * i), end=dt(MONDAY, 10 + 2 * i + 1))
             for i in range(3)]  # busy 10-11, 12-13, 14-15 -> free 9-10, 11-12, 13-14, 15-17
    task = TaskSpec(id="t1", title="Long task", duration_minutes=180,
                    deadline=dt(MONDAY, 17), splittable=True, min_block_minutes=60)
    placements = BuiltInSolver().solve([task], fixed, prefs(), MONDAY)
    blocks = [p for p in placements if p.kind == "task"]
    assert len(blocks) == 3  # 3 x 60-minute chunks into the one-hour gaps
    assert sum(int((b.end - b.start).total_seconds() // 60) for b in blocks) == 180


def test_solver_raises_on_infeasible():
    task = TaskSpec(id="t1", title="Impossible", duration_minutes=20 * 60,
                    deadline=dt(MONDAY, 17))
    with pytest.raises(InfeasibleScheduleError) as excinfo:
        BuiltInSolver().solve([task], [], prefs(), MONDAY)
    assert excinfo.value.task_id == "t1"


# -- planning + approval gating ------------------------------------------------

def test_plan_propose_apply_is_approval_gated(tmp_path):
    service, repo, gate = make_service(tmp_path)
    task = service.create_task(SchedulingTaskCreate(
        title="Write essay", duration_minutes=60, deadline=dt(MONDAY + timedelta(days=2), 17)))
    plan = service.plan_week(MONDAY)
    assert plan.status == "draft" and len(plan.blocks) == 1

    proposal = service.propose_plan(plan.id)
    assert proposal.action_type == "apply_calendar_plan"
    assert gate.items[proposal.approval_id].module_id == 11
    assert gate.items[proposal.approval_id].payload["tenant_id"] == "tenant-a"

    with pytest.raises(ApprovalNotGrantedError):
        service.apply_plan(proposal.approval_id)

    gate.approve(proposal.approval_id)
    applied = service.apply_plan(proposal.approval_id)
    assert applied.status == "applied"
    assert repo.get_task(task.id).status == "scheduled"


def test_apply_plan_with_unknown_approval_rejected(tmp_path):
    service, _, _ = make_service(tmp_path)
    with pytest.raises(ApprovalNotGrantedError):
        service.apply_plan("nonexistent")


# -- conflict resolution ----------------------------------------------------------

def test_conflict_generates_alternatives_and_gated_apply(tmp_path):
    service, repo, gate = make_service(tmp_path)
    tiny = SchedulingPrefsSchema(
        working_hours={0: [WindowSchema(start="09:00", end="10:00")]},  # Monday only, 1h
        energy_curve={h: 3 for h in range(24)},
    )
    service.save_prefs(tiny)

    today = datetime.now(UTC).date()
    days_ahead = (0 - today.weekday()) % 7 or 7
    monday = today + timedelta(days=days_ahead)

    service.create_task(SchedulingTaskCreate(
        title="Existing high priority", duration_minutes=60,
        deadline=dt(monday, 17), priority=5))
    conflict_task = SchedulingTaskCreate(
        title="New deadline", duration_minutes=60,
        deadline=dt(monday, 12), priority=3)
    report, proposal = service.request_reschedule(conflict_task)
    assert report is not None and proposal is not None
    kinds = {alt.kind for alt in report.alternatives}
    assert "extend_hours" in kinds
    assert proposal.action_type == "apply_reschedule"

    with pytest.raises(ApprovalNotGrantedError):
        service.apply_reschedule(proposal.approval_id)
    gate.approve(proposal.approval_id)
    applied = service.apply_reschedule(proposal.approval_id)
    assert applied.title == "New deadline" and applied.status == "scheduled"


def test_no_conflict_returns_no_proposal(tmp_path):
    service, _, _ = make_service(tmp_path)
    today = datetime.now(UTC).date()
    days_ahead = (0 - today.weekday()) % 7 or 7
    monday = today + timedelta(days=days_ahead)
    report, proposal = service.request_reschedule(SchedulingTaskCreate(
        title="Fits fine", duration_minutes=60, deadline=dt(monday, 17)))
    assert report is None and proposal is None


# -- analytics -----------------------------------------------------------------------

def test_meeting_load_report(tmp_path):
    from app.modules.m11_calendar_intelligence.ics import IcsEvent

    caldav = FakeCalDAVClient(events=[
        IcsEvent(uid="c1", summary="A", start=dt(MONDAY, 9), end=dt(MONDAY, 10)),
        IcsEvent(uid="c2", summary="B", start=dt(MONDAY, 10, 15), end=dt(MONDAY, 11)),
        IcsEvent(uid="c3", summary="C", start=dt(MONDAY + timedelta(days=1), 14),
                 end=dt(MONDAY + timedelta(days=1), 15, 30)),
    ])
    service, repo, _ = make_service(tmp_path, caldav=caldav)
    source = service.register_caldav_source(CalDAVSourceCreate(
        account_email="me@icloud.com", calendar_url="https://cal.example.com/",
        username="me", password="pw"))
    asyncio.run(service.sync_source(source.id))
    report = service.meeting_load(MONDAY)
    monday_load = report.days[0]
    assert monday_load.meeting_minutes == 105 and monday_load.meeting_count == 2
    assert monday_load.short_gaps == 1  # 15-minute gap between A and B
    assert report.days[1].meeting_minutes == 90
    assert report.total_meeting_minutes == 195

def test_meeting_load_clips_cross_midnight_and_week_edges():
 from types import SimpleNamespace
 class Repo:
  def list_events(self,**kwargs):
   return [SimpleNamespace(start=datetime(2026,10,4,23,30,tzinfo=UTC),end=datetime(2026,10,5,0,30,tzinfo=UTC)),
           SimpleNamespace(start=datetime(2026,10,5,23,30,tzinfo=UTC),end=datetime(2026,10,6,0,30,tzinfo=UTC)),
           SimpleNamespace(start=datetime(2026,10,11,23,30,tzinfo=UTC),end=datetime(2026,10,12,0,30,tzinfo=UTC))]
 service=Service(Repo(),FakeApprovalGate(),cipher=None)
 report=service.meeting_load(date(2026,10,5))
 assert report.total_meeting_minutes==120
 assert [d.meeting_minutes for d in report.days]==[60,30,0,0,0,0,30]
 assert report.days[0].longest_meeting_minutes==30

def test_google_watch_and_sync_must_exchange_refresh_token_before_bearer_use(tmp_path):
 class StrictGoogle(FakeGoogleCalendarClient):
  async def watch(self, access_token, *args, **kwargs):
   assert access_token=='short-lived-access'
   return await super().watch(access_token,*args,**kwargs)
  async def list_events(self, token, *args, **kwargs):
   assert token=='short-lived-access'
   return EventPage(events=[],next_sync_token='next')
 google=StrictGoogle();service,repo,gate=make_service(tmp_path,google=google)
 source=service.register_google_source(GoogleSourceCreate(account_email='a@example.com',refresh_token='persistent-refresh',calendar_id='primary'))
 calls=[]
 async def exchange(refresh):
  calls.append(refresh);return 'short-lived-access'
 service._google_access_token_provider=exchange
 asyncio.run(service.ensure_watch(source.id))
 asyncio.run(service.sync_source(source.id))
 assert calls==['persistent-refresh','persistent-refresh']


def test_meeting_load_buckets_follow_user_timezone():
 from types import SimpleNamespace
 from zoneinfo import ZoneInfo
 class Repo:
  def list_events(self,**kwargs):
   return [SimpleNamespace(start=datetime(2026,10,4,19,0,tzinfo=UTC),end=datetime(2026,10,4,20,0,tzinfo=UTC))]
 service=Service(Repo(),FakeApprovalGate(),cipher=None)
 # Monday 00:30-01:30 Asia/Calcutta, despite Sunday UTC timestamps.
 report=service.meeting_load(date(2026,10,5),timezone_name='Asia/Calcutta')
 assert report.days[0].meeting_minutes==60
 assert report.total_meeting_minutes==60
 assert report.timezone_name=='Asia/Calcutta'


def test_meeting_load_dst_elapsed_minutes_and_http_timezone_contract():
 from types import SimpleNamespace
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.modules.m11_calendar_intelligence.routes import router,get_service
 class Repo:
  def list_events(self,**kwargs):
   return [SimpleNamespace(start=datetime(2026,11,1,4,0,tzinfo=UTC),end=datetime(2026,11,2,5,0,tzinfo=UTC))]
 service=Service(Repo(),FakeApprovalGate(),cipher=None)
 result=service.meeting_load(date(2026,10,26),timezone_name='America/New_York')
 assert result.days[-1].meeting_minutes==1500
 app=FastAPI();app.include_router(router)
 # Isolated HTTP fixture, not production tenant/auth acceptance.
 app.dependency_overrides[get_service]=lambda:service
 with TestClient(app) as client:
  url='/calendar-intelligence/analytics/meeting-load'
  assert client.get(url,params={'week_start':'2026-10-26'}).status_code==422
  assert client.get(url,params={'week_start':'2026-10-26','timezone_name':'invalid/zone'}).status_code==422
  response=client.get(url,params={'week_start':'2026-10-26','timezone_name':'America/New_York'})
  assert response.status_code==200
  assert response.json()['total_meeting_minutes']==1500
  assert response.json()['timezone_name']=='America/New_York'

def test_google_refresh_failure_never_reaches_calendar_client(tmp_path):
 google=FakeGoogleCalendarClient();service,repo,_=make_service(tmp_path,google=google)
 source=service.register_google_source(GoogleSourceCreate(account_email='a@example.com',refresh_token='persistent-refresh',calendar_id='primary'))
 async def fail(refresh):raise RuntimeError('exchange failed')
 service._google_access_token_provider=fail
 with pytest.raises(RuntimeError,match='exchange failed'):asyncio.run(service.ensure_watch(source.id))
 assert google.watch_calls==[]
 service._google_access_token_provider=None
 with pytest.raises(RuntimeError,match='not configured'):asyncio.run(service.sync_source(source.id))
 assert google.sync_tokens_seen==[]

def test_runtime_service_wires_exchange_with_mock_http(monkeypatch):
 from types import SimpleNamespace
 from app.modules.m11_calendar_intelligence import routes
 original_client=httpx.AsyncClient
 requests=[]
 def handler(request):
  requests.append(request)
  assert request.url==httpx.URL('https://oauth2.googleapis.com/token')
  assert b'refresh_token=persistent-refresh' in request.content
  assert b'client_id=fixture-client' in request.content
  return httpx.Response(200,json={'access_token':'short-lived-access'})
 monkeypatch.setenv('ATLAS_GOOGLE_CLIENT_ID','fixture-client')
 monkeypatch.setenv('ATLAS_GOOGLE_CLIENT_SECRET','fixture-secret')
 monkeypatch.setattr(routes.httpx,'AsyncClient',lambda **kwargs:original_client(transport=httpx.MockTransport(handler),**kwargs))
 monkeypatch.setattr(routes,'TokenCipher',lambda tenant:SimpleNamespace())
 monkeypatch.setattr(routes,'SqlCalendarRepository',lambda tenant:SimpleNamespace(tenant_id=tenant))
 async def run():
  iterator=routes.get_service(SimpleNamespace(tenant_id='fixture-tenant'))
  svc=await anext(iterator)
  assert await svc._google_access_token_provider('persistent-refresh')=='short-lived-access'
  await iterator.aclose()
 asyncio.run(run())
 assert len(requests)==1

@pytest.mark.parametrize('value',['persistent-refresh','', ' ', None,123])
def test_service_rejects_invalid_exchanged_token_before_provider(tmp_path,value):
 google=FakeGoogleCalendarClient();svc,repo,_=make_service(tmp_path,google=google)
 source=svc.register_google_source(GoogleSourceCreate(account_email='a@example.com',refresh_token='persistent-refresh',calendar_id='primary'))
 async def exchange(refresh):return value
 svc._google_access_token_provider=exchange
 with pytest.raises(ValueError,match='invalid access token'):asyncio.run(svc.ensure_watch(source.id))
 assert google.watch_calls==[]
 with pytest.raises(ValueError,match='invalid access token'):asyncio.run(svc.sync_source(source.id))
 assert google.sync_tokens_seen==[]

@pytest.mark.parametrize('status,body',[(200,{'access_token':'persistent-refresh'}),(200,{'access_token':''}),(200,{'access_token':' '}),(200,{'access_token':123}),(200,{}),(400,{'error':'invalid_grant'}),(503,{}),(400,{'access_token':'valid-looking-token'}),(503,{'access_token':'valid-looking-token'})])
def test_http_exchange_rejects_bad_response(status,body):
 from app.modules.m11_calendar_intelligence.google_calendar import exchange_refresh_token,UpstreamServiceError
 async def run():
  async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(status,json=body))) as client:
   with pytest.raises(UpstreamServiceError):await exchange_refresh_token(client,'persistent-refresh',client_id='id',client_secret='secret')
 asyncio.run(run())

@pytest.mark.parametrize('client_id,client_secret',[('', 'secret'),('id',''),('','')])
def test_http_exchange_missing_config_makes_no_request(client_id,client_secret):
 from app.modules.m11_calendar_intelligence.google_calendar import exchange_refresh_token,UpstreamServiceError
 calls=[]
 def handler(req):calls.append(req);return httpx.Response(200,json={'access_token':'at'})
 async def run():
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
   with pytest.raises(UpstreamServiceError,match='configuration'):await exchange_refresh_token(client,'refresh',client_id=client_id,client_secret=client_secret)
 asyncio.run(run())
 assert calls==[]


def test_apply_reschedule_replay_is_refused_without_duplicating(tmp_path):
    # One approved reschedule must apply exactly once: a replay of the same
    # approval id raises instead of creating a duplicate task and plan blocks.
    service, repo, gate = make_service(tmp_path)
    tiny = SchedulingPrefsSchema(
        working_hours={0: [WindowSchema(start="09:00", end="10:00")]},
        energy_curve={h: 3 for h in range(24)},
    )
    service.save_prefs(tiny)
    today = datetime.now(UTC).date()
    days_ahead = (0 - today.weekday()) % 7 or 7
    monday = today + timedelta(days=days_ahead)
    service.create_task(SchedulingTaskCreate(
        title="Existing high priority", duration_minutes=60,
        deadline=dt(monday, 17), priority=5))
    report, proposal = service.request_reschedule(SchedulingTaskCreate(
        title="New deadline", duration_minutes=60,
        deadline=dt(monday, 12), priority=3))
    assert proposal is not None
    gate.approve(proposal.approval_id)
    first = service.apply_reschedule(proposal.approval_id)
    assert first.status == "scheduled"
    with pytest.raises(ApprovalNotGrantedError, match="consumed"):
        service.apply_reschedule(proposal.approval_id)
    scheduled = [t.title for t in repo.list_tasks(status="scheduled")]
    assert scheduled.count("New deadline") == 1
