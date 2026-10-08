"""Real SQLite / encrypted credentials and mounted FastAPI M11 regression pins."""
import asyncio
from datetime import date, datetime, timezone
import os
import pytest
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.token_crypto import TokenCipher
from app.modules.m11_calendar_intelligence.service import Service
from app.modules.m11_calendar_intelligence.schemas import GoogleSourceCreate
from app.modules.m11_calendar_intelligence.google_calendar import EventPage, WatchInfo, UpstreamServiceError
from app.modules.m11_calendar_intelligence.sql_repository import SqlCalendarRepository
from app.modules.m11_calendar_intelligence import routes

D = date(2026, 10, 8)

def dt(s):
    return datetime.fromisoformat(s)

@pytest.fixture
def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/lane.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    repo = SqlCalendarRepository("owner", sessionmaker(bind=engine, expire_on_commit=False))
    service = Service(repo, object(), cipher=TokenCipher("owner", master_secret="fixture-only-secret"))
    yield service, repo
    engine.dispose()

def add(repo, uid, start, end, status="confirmed"):
    repo.upsert_event(event_id=uid, source_id="fixture", uid=uid, summary=uid,
                      start=dt(start), end=dt(end), location=None, status=status)

def client(service):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: service
    return TestClient(app)

def test_legacy_cross_midnight_is_clipped(setup):
    service, repo = setup
    add(repo, "a", "2026-10-07T23:30+00:00", "2026-10-08T00:30+00:00")
    report = service.meeting_load(D)
    assert report.days[0].meeting_minutes == 30
    assert report.days[0].longest_meeting_minutes == 30
    assert report.total_meeting_minutes == 30

def test_local_timezone_and_overlap_are_distinct_metrics(setup):
    service, repo = setup
    add(repo, "a", "2026-10-08T18:00+00:00", "2026-10-08T19:00+00:00")
    add(repo, "b", "2026-10-08T18:15+00:00", "2026-10-08T18:45+00:00")
    r = service.meeting_load(D, timezone_name="Asia/Kolkata")
    assert [d.meeting_minutes for d in r.days[:2]] == [45, 45]
    assert [d.occupied_seconds for d in r.days[:2]] == [1800, 1800]
    assert r.total_meeting_minutes == 90
    assert r.total_occupied_seconds == 3600
    assert r.total_overlapping_seconds == 1800

def test_fall_back_elapsed_service(setup):
    service, repo = setup
    add(repo, "a", "2026-11-01T05:15+00:00", "2026-11-01T06:45+00:00")
    d = service.meeting_load(date(2026,11,1), "America/New_York").days[0]
    assert (d.meeting_minutes, d.occupied_seconds, d.day_seconds) == (90, 5400, 90000)

def test_nested_gap_is_measured_after_union(setup):
    service, repo = setup
    for uid,a,b in [("a","09:00","11:00"),("b","09:30","10:00"),("c","11:10","12:00")]:
        add(repo, uid, f"2026-10-08T{a}+00:00", f"2026-10-08T{b}+00:00")
    assert service.meeting_load(D).days[0].short_gaps == 1

def test_more_than_500_and_tenant_isolation(setup):
    service, repo = setup
    for i in range(501):
        add(repo, str(i), "2026-10-08T09:00+00:00", "2026-10-08T09:01+00:00")
    foreign = SqlCalendarRepository("other", repo.sessions)
    add(foreign, "foreign", "2026-10-08T00:00+00:00", "2026-10-09T00:00+00:00")
    add(repo, "cancelled", "2026-10-08T00:00+00:00", "2026-10-09T00:00+00:00", "cancelled")
    d = service.meeting_load(D).days[0]
    assert d.meeting_count == 501
    assert (d.meeting_minutes, d.occupied_seconds, d.peak_concurrency) == (501,60,501)

def test_mounted_timezone_query_and_invalid_422(setup):
    service, repo = setup
    add(repo, "a", "2026-10-08T18:45+00:00", "2026-10-08T19:00+00:00")
    with client(service) as c:
        result = c.get("/calendar-intelligence/analytics/meeting-load", params={"week_start": str(D), "timezone": "Asia/Kolkata"})
        assert result.status_code == 200
        assert result.json()["timezone"] == "Asia/Kolkata"
        assert result.json()["days"][0]["meeting_minutes"] == 0
        assert result.json()["days"][1]["meeting_minutes"] == 15
        invalid = c.get("/calendar-intelligence/analytics/meeting-load", params={"week_start": str(D), "timezone": "bad/zone"})
        assert invalid.status_code == 422

class CalendarRecorder:
    def __init__(self):
        self.calls = []
    async def watch(self, access_token, calendar_id, **kw):
        self.calls.append(("watch", access_token))
        return WatchInfo(kw["channel_id"], "resource", None)
    async def list_events(self, access_token, calendar_id, **kw):
        self.calls.append(("list", access_token))
        return EventPage([], None)

@pytest.mark.parametrize("action", ["watch", "sync"])
def test_refresh_exchange_precedes_calendar_bearer(setup, action):
    service, repo = setup
    recorder = CalendarRecorder()
    service.google = recorder
    seen = []
    async def exchange(refresh):
        seen.append(refresh)
        assert recorder.calls == []
        return "fixture-access"
    service._google_access_token_provider = exchange
    source = service.register_google_source(GoogleSourceCreate(account_email="owner@example.test", refresh_token="fixture-refresh"))
    assert "fixture-refresh" not in repo.get_source(source.id).encrypted_credentials
    asyncio.run(service.ensure_watch(source.id) if action == "watch" else service.sync_source(source.id))
    assert seen == ["fixture-refresh"]
    assert recorder.calls == [("watch" if action == "watch" else "list", "fixture-access")]

@pytest.mark.parametrize("token", [None, "", "fixture-refresh", " bad token ", 4])
def test_bad_exchange_token_stops_calendar(setup, token):
    service, repo = setup
    service.google = CalendarRecorder()
    async def exchange(refresh):
        return token
    service._google_access_token_provider = exchange
    source = service.register_google_source(GoogleSourceCreate(account_email="owner@example.test", refresh_token="fixture-refresh"))
    with pytest.raises(UpstreamServiceError):
        asyncio.run(service.sync_source(source.id))
    assert service.google.calls == []

def test_missing_exchange_stops_calendar(setup):
    service, repo = setup
    service.google = CalendarRecorder()
    source = service.register_google_source(GoogleSourceCreate(account_email="owner@example.test", refresh_token="fixture-refresh"))
    with pytest.raises(UpstreamServiceError):
        asyncio.run(service.sync_source(source.id))
    assert service.google.calls == []

def test_routes_construct_real_refresh_adapter(setup, monkeypatch):
    service, repo = setup
    monkeypatch.setenv("ATLAS_TOKEN_KEY", "fixture-only-secret")
    async def run():
        from app.auth.context import TenantContext
        provider = routes.get_service(TenantContext("owner", "actor", frozenset()))
        constructed = await anext(provider)
        try:
            assert callable(constructed._google_access_token_provider)
            assert constructed._google_access_token_provider.__self__.__class__.__name__ == "GoogleRefreshExchange"
        finally:
            await provider.aclose()
    asyncio.run(run())

@pytest.mark.parametrize("status,payload", [
    (400, {"access_token":"valid-looking", "token_type":"Bearer"}),
    (302, {"access_token":"valid-looking", "token_type":"Bearer"}),
    (503, {"access_token":"valid-looking", "token_type":"Bearer"}),
    (200, {"access_token":"fixture-refresh", "token_type":"Bearer"}),
    (200, {"access_token":"valid-looking", "token_type":"Basic"}),
    (200, {"access_token":"bad token", "token_type":"Bearer"}),
    (200, {"access_token":"", "token_type":"Bearer"}),
    (200, []),
])
def test_http_refresh_rejects_status_or_invalid_token(status, payload):
    from app.modules.m11_calendar_intelligence.google_refresh_lane import GoogleRefreshExchange
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(status, json=payload))) as http:
            with pytest.raises(UpstreamServiceError):
                await GoogleRefreshExchange(http, "fixture-id", "fixture-secret").access_token("fixture-refresh")
    asyncio.run(run())


def test_http_refresh_form_success_and_missing_config():
    from app.modules.m11_calendar_intelligence.google_refresh_lane import GoogleRefreshExchange
    from urllib.parse import parse_qs
    calls = []
    def handler(request):
        assert str(request.url) == "https://oauth2.googleapis.com/token"
        assert request.method == "POST"
        form = parse_qs(request.content.decode())
        assert form == {"grant_type":["refresh_token"], "refresh_token":["fixture-refresh"],
                        "client_id":["fixture-id"], "client_secret":["fixture-secret"]}
        calls.append(request.method)
        return httpx.Response(200, json={"access_token":"fixture-access", "token_type":"Bearer"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            assert await GoogleRefreshExchange(http, "fixture-id", "fixture-secret").access_token("fixture-refresh") == "fixture-access"
            with pytest.raises(UpstreamServiceError):
                await GoogleRefreshExchange(http, "", "").access_token("fixture-refresh")
    asyncio.run(run())
    assert calls == ["POST"]


def test_exchange_exception_stops_provider(setup):
    service, repo = setup
    service.google = CalendarRecorder()
    async def exchange(refresh):
        raise UpstreamServiceError("fixture-upstream-failed")
    service._google_access_token_provider = exchange
    source = service.register_google_source(GoogleSourceCreate(account_email="owner@example.test", refresh_token="fixture-refresh"))
    with pytest.raises(UpstreamServiceError):
        asyncio.run(service.ensure_watch(source.id))
    assert service.google.calls == []


def test_spring_midnight_gap_and_skipped_day_via_service(setup):
    service, repo = setup
    add(repo, "spring", "2026-03-08T06:30+00:00", "2026-03-08T07:30+00:00")
    d = service.meeting_load(date(2026,3,8), "America/New_York").days[0]
    assert (d.meeting_minutes, d.day_seconds) == (60,82800)
    assert service.meeting_load(date(2018,11,4), "America/Sao_Paulo").days[0].day_seconds == 82800
    assert service.meeting_load(date(2011,12,30), "Pacific/Apia").days[0].day_seconds == 0
