"""Hermetic real-engine adapter contracts, not evidence of live vendor accounts."""
import asyncio
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from app.modules.m01_opportunity_discovery.student_browser import (
    ADAPTERS, StudentBrowser, SQLCheckpoints, StudentBrowserCheckpoint, page_links, platform_url,
)
from app.modules.m01_opportunity_discovery.student_browser_routes import install_routes, get_student_browser
from app.modules.m01_opportunity_discovery.student_platforms import PlatformUnavailable
from app.modules.m13_browser_agent.application_flow import ApplicationFlow, BlockedError, WorkflowStateError
from app.modules.m13_browser_agent.application_store import InMemoryApplicationSessionStore
from app.modules.m13_browser_agent.service import Service as BrowserService

HTML = '<h1>My scholarships</h1><a href="/scholarships/stem-award/">STEM award</a><a href="/profile">Profile</a><form><label for="name">Full name</label><input id="name" name="full_name"><button id="send" type="submit">Submit</button></form>'

class Page:
    url = 'https://bold.org/scholarships/'
    html = HTML
    def __init__(self): self.values = {}; self.clicks = []
    async def goto(self, url, **kwargs): self.url = url; return SimpleNamespace(status=200)
    async def content(self): return self.html
    async def screenshot(self, **kwargs): return b'redacted-test-image'
    def locator(self, selector):
        page = self
        class Locator:
            async def fill(self, value): page.values[selector] = value
            async def input_value(self): return page.values[selector]
            async def click(self): page.clicks.append(selector)
        return Locator()

class Sessions:
    def __init__(self): self.pages = {}
    async def page(self, tenant, session, *args):
        return self.pages.setdefault((tenant, session), Page())

class Audit:
    def __init__(self): self.events = []
    async def append_audit(self, event): self.events.append(event)

@pytest.fixture
def browser(tmp_path, monkeypatch):
    # DNS fixed only for hermetic fake-page tests; production validator unchanged.
    monkeypatch.setattr('app.modules.m13_browser_agent.security._resolve', lambda *args: {'8.8.8.8'})
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    StudentBrowserCheckpoint.__table__.create(engine)
    checkpoints = SQLCheckpoints(sessionmaker(bind=engine, expire_on_commit=False))
    sessions = Sessions()
    flow = ApplicationFlow(BrowserService(sessions, None, Audit(), artifact_root=str(tmp_path)), InMemoryApplicationSessionStore())
    time = [1000.0]
    result = StudentBrowser(flow, checkpoints, lambda: time[0])
    result.time = time
    return result


def run(coro): return asyncio.run(coro)

def start(browser): return run(browser.start('t', 'a', 'bold', True, True))['session_id']


def test_all_platforms_have_explicit_capabilities():
    assert len(ADAPTERS) == 17
    assert ADAPTERS['simplify'].caveat and ADAPTERS['raiseme'].caveat

@pytest.mark.parametrize('url', ['http://bold.org/x', 'https://bold.org.evil.test/x', 'https://evil.test/x', 'https://user:pass@bold.org/x', 'https://bold.org:123/x'])
def test_origin_rejection(url):
    with pytest.raises(PermissionError): platform_url(ADAPTERS['bold'], url)


def test_real_dom_only_and_no_control_side_effects():
    links = page_links(ADAPTERS['bold'], 'https://bold.org/', HTML + '<a href="https://evil.test/scholarships/x">Bad</a><a href="/logout">Profile</a>')
    assert [x['kind'] for x in links] == ['opportunity', 'account_navigation']
    assert links[0]['source_url'] == 'https://bold.org/'
    assert not page_links(ADAPTERS['bold'], 'https://bold.org/', '<h1>scholarships</h1>')


def test_read_delta_persistence_and_rate(browser):
    sid = start(browser)
    first = run(browser.read('t', 'a', sid))
    assert len(first['new_opportunities']) == 1 and not first['alerts_sent']
    with pytest.raises(PlatformUnavailable): run(browser.read('t', 'a', sid))
    browser.time[0] += 60
    # New service instance uses persisted delta history, not process-local memory.
    other = StudentBrowser(browser.flow, browser.checkpoints, browser.clock)
    assert not run(other.read('t', 'a', sid))['new_opportunities']


def test_link_open_creates_new_record_and_rejects_stale(browser):
    sid = start(browser)
    link = run(browser.read('t', 'a', sid))['links'][0]
    browser.time[0] += 60
    child = run(browser.open('t', 'a', sid, link['id']))
    assert child['session_id'] != sid and child['url'] == link['url']
    browser.time[0] += 5
    browser.flow.browser.sessions.pages[('t', sid)].html = '<h1>No links</h1>'
    with pytest.raises(WorkflowStateError): run(browser.open('t', 'a', sid, link['id']))


def test_captcha_sticky_even_after_html_changes(browser):
    sid = start(browser)
    page = browser.flow.browser.sessions.pages[('t', sid)]
    page.html = '<div>Verify you are human</div>'
    with pytest.raises(BlockedError): run(browser.read('t', 'a', sid))
    browser.time[0] += 100
    page.html = HTML
    with pytest.raises(BlockedError): run(browser.read('t', 'a', sid))


def test_cross_owner_and_tenant_rejected(browser):
    sid = start(browser)
    with pytest.raises(PermissionError): run(browser.read('t', 'other', sid))
    with pytest.raises(KeyError): run(browser.read('other', 'a', sid))


def test_form_stage_real_engine_no_submit(browser):
    sid = start(browser)
    result = run(browser.stage('t', 'a', sid, {'full_name': 'Student'}, '#send'))
    assert result['preview']['#name']['matches'] and result['submitted'] is False
    assert not browser.flow.browser.sessions.pages[('t', sid)].clicks
    with pytest.raises(WorkflowStateError): run(browser.stage('t', 'a', sid, {'full_name': 'Student'}, '#missing'))


def test_permission_before_start(browser):
    with pytest.raises(PermissionError): run(browser.start('t', 'a', 'bold', False, True))
    with pytest.raises(PermissionError): run(browser.start('t', 'a', 'bold', True, False))
    assert not browser.flow.browser.sessions.pages


def test_http_mounted_read_and_strict_inputs(browser):
    router = APIRouter(); install_routes(router)
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_student_browser] = lambda: browser
    with TestClient(app) as client:
        base = '/opportunity-discovery/student-platforms'
        result = client.post(base + '/bold/browser-sessions', json={'owner_account_confirmed': True, 'terms_permit': True})
        assert result.status_code == 201, result.text
        sid = result.json()['session_id']
        assert client.post(base + '/browser-sessions/' + sid + '/read').status_code == 200
        assert client.post(base + '/bold/browser-sessions', json={'owner_account_confirmed': True, 'terms_permit': True, 'password': 'rejected'}).status_code == 422
        assert len(client.get(base + '/browser-capabilities').json()) == 17

@pytest.mark.parametrize('platform,path', [
    ('ripplematch', '/jobs/123'), ('simplify', '/p/12345'),
    ('raiseme', '/colleges/college-name'), ('fastweb', '/college-scholarships/scholarships/123-stem'),
    ('devpost', '/hackathons/123'), ('internshala', '/internship/detail/example'),
    ('mlh', '/events/123-name'), ('unigo', '/scholarships/stem'), ('kaggle', '/competitions/example'),
    ('scholarships360', '/example-award/'), ('scholarshiproar', '/example-award/'),
    ('scholarshipregion', '/example-award/'), ('opportunitiesforafricans', '/example-award/'),
    ('scholarshipunion', '/example-award/'), ('opportunitiesforyouth', '/example-award/'),
])
def test_each_platform_link_contract(platform, path):
    adapter = ADAPTERS[platform]
    url = 'https://' + adapter.hosts[0] + '/'
    rows = page_links(adapter, url, '<a href="' + path + '">Observed student opportunity</a>')
    assert len(rows) == 1 and rows[0]['kind'] == 'opportunity'


def test_challengerocket_and_devpost_card_contract():
    cr = page_links(ADAPTERS['challengerocket'], 'https://challengerocket.com/hackathons-and-challenges.html', '<div class="challenge-card__title"><a href="/some-real-event">Event</a></div><a href="/terms">Terms</a>')
    assert len(cr) == 1 and cr[0]['kind'] == 'opportunity'
    dp = page_links(ADAPTERS['devpost'], 'https://devpost.com/hackathons', '<a href="https://observed-hack.devpost.com/">Observed Hack</a><a href="https://help.devpost.com/">Help</a>')
    assert len(dp) == 1 and dp[0]['url'] == 'https://observed-hack.devpost.com/'


def test_no_stage_after_manual_external_navigation(browser):
    sid = start(browser)
    browser.flow.browser.sessions.pages[('t', sid)].url = 'https://evil.test/apply'
    with pytest.raises(PermissionError): run(browser.stage('t', 'a', sid, {'full_name': 'Student'}, '#send'))
    assert not browser.flow.browser.sessions.pages[('t', sid)].values


def test_controls_requiring_owner_handling_fail_before_fill(browser):
    sid = start(browser)
    page = browser.flow.browser.sessions.pages[('t', sid)]
    page.html = HTML + '<select id="college"><option>School</option></select>'
    with pytest.raises(WorkflowStateError): run(browser.stage('t', 'a', sid, {'full_name': 'Student'}, '#send'))
    assert not page.values


def test_session_block_also_stops_stage(browser):
    sid = start(browser)
    page = browser.flow.browser.sessions.pages[('t', sid)]
    page.html = '<h1>Too many requests</h1>'
    with pytest.raises(BlockedError): run(browser.read('t', 'a', sid))
    page.html = HTML
    with pytest.raises(BlockedError): run(browser.stage('t', 'a', sid, {'full_name': 'Student'}, '#send'))
    assert not page.values


def test_no_secrets_staged(browser):
    from app.modules.m13_browser_agent.application_flow import CredentialRejectedError
    sid = start(browser)
    with pytest.raises(CredentialRejectedError):
        run(browser.stage('t', 'a', sid, {'password': 'nope'}, '#send'))
    assert not browser.flow.browser.sessions.pages[('t', sid)].values


def test_checkpoint_atomic_pacing_reservation(browser):
    sid = start(browser)
    browser.checkpoints.reserve('t', sid, 'a', 1000, 60)
    with pytest.raises(PlatformUnavailable): browser.checkpoints.reserve('t', sid, 'a', 1000, 60)
    browser.checkpoints.reserve('t', sid, 'a', 1060, 60)
