"""Real Chromium -> native PC Daemon -> DaemonConnection -> production runner.

Only the website and websocket transport are local test fixtures. No browser,
executor, approval, receipt or store is mocked. Human login is simulated by the
fixture owner's direct browser operation, outside Atlas's command channel.
"""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service
from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon, DeviceIdentity
from app.modules.m13_browser_agent.session_bridge.dispatch import BridgedSessions, ConnectionHub, DaemonConnection
from app.modules.m13_browser_agent.session_bridge.registry import BridgeRegistry
from app.modules.m18_side_hustle_scraper.login_runner import BrowserRecipe, LoginRunStore
from app.modules.m18_side_hustle_scraper.login_routes import build_login_runner


@pytest_asyncio.fixture
async def setup(tmp_path):
    class Site(BaseHTTPRequestHandler):
        posts = []
        keys = []
        commands = []
        extra_field = None
        submit_attr = None
        def log_message(self, *args): pass
        def do_GET(self):
            if self.path == '/throttle':
                self.send_response(429); self.end_headers(); return
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
            if self.path == '/captcha':
                html = 'captcha'
            else:
                html = '''<html><body><div id="account"></div><script>
                document.querySelector('#account').textContent=localStorage.getItem('owner')||'';
                </script><a class="source" href="/idea">Offer a small tutoring pilot and measure actual interest.</a>
                <form method="post" action="/publish"><p id="terms">Free publication. No fees.</p>
                <label>Public draft<textarea id="draft" name="draft"></textarea></label>
                <input name="audience" value="public"><input id="run_id" name="run_id"><button id="publish">Publish once</button></form>'''
                if self.submit_attr and self.path == '/compose':
                    html = html.replace('<button id="publish"', '<button id="publish" '+self.submit_attr[0]+'="'+self.submit_attr[1]+'"')
                if self.extra_field and self.path == '/compose':
                    html = html.replace('</form>', '<input name="'+self.extra_field+'" value="DO_NOT_COPY"></form>')
                if self.path == '/receipt' and self.posts:
                    html += '<div id="receipt">'+str(len(self.posts))+'</div><div id="published">'+self.posts[-1]+'</div><div id="receipt_account">owner</div><div id="receipt_run">'+self.keys[-1]+'</div>'
                html += '</body></html>'
            self.wfile.write(html.encode())
        def do_POST(self):
            from urllib.parse import parse_qs
            body = self.rfile.read(int(self.headers['Content-Length'])).decode()
            self.posts.append(parse_qs(body)['draft'][0])
            self.keys.append(parse_qs(body)['run_id'][0])
            self.send_response(303); self.send_header('Location', '/receipt'); self.end_headers()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Site)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    engine = create_engine(f'sqlite:///{tmp_path}/sql.db'); Base.metadata.create_all(engine)
    sql = sessionmaker(bind=engine, expire_on_commit=False)
    approvals, registry = Service(sql), BridgeRegistry(sql)
    identity = DeviceIdentity.load_or_create(tmp_path/'device.pem')
    challenge = registry.create_challenge('tenant')
    caps = ['navigate', 'extract', 'screenshot', 'read_values', 'fill', 'click_submit']
    paired = registry.confirm_pairing(challenge['server_nonce'], challenge['code'], name='Local owner', public_key=identity.public_key_pem(), capabilities=caps)
    config = DaemonConfig(device_id=paired['device_id'], command_secret=paired['command_secret'], capabilities=caps, pacing_seconds=0)
    daemon = Daemon(config, identity)
    pw = await async_playwright().start(); browser = await pw.chromium.launch(headless=True)
    daemon.browser._context = await browser.new_context()
    page = await daemon.browser.page('experiment')
    await page.goto(origin)
    # Owner login handoff, not an Atlas fill of any credential.
    await page.evaluate("localStorage.setItem('owner','owner')")
    await page.reload()
    class Wire:
        async def send_json(self, command):
            Site.commands.append(command)
            answer = await daemon.execute(command)
            await connection.handle_message(answer)
    connection = DaemonConnection(Wire(), paired['device_id'], 2)
    # Local fake-site tests do not need human-site pacing. Production clamps >=2s.
    connection.pacing_seconds = 0
    hub = ConnectionHub(); await hub.register(connection)
    sessions = BridgedSessions(registry, hub)
    recipe = BrowserRecipe('local_fixture', origin, origin+'/discover', origin+'/compose', '#account', '.source', '#draft', '#publish', '#terms', 'Free publication. No fees.', '#receipt', '#published', '#receipt_account', '#run_id', '#receipt_run', ('draft', 'audience', 'run_id'), True)
    store = LoginRunStore(tmp_path/'runs.db')
    def runner(recipes=None):
        return build_login_runner(store=store, sessions=sessions, approvals=approvals,
            recipes=recipes or {'local_fixture': recipe}, receipt_key=b'k'*32)
    yield runner, recipe, approvals, registry, paired, page, Site, tmp_path
    await browser.close(); await pw.stop(); server.shutdown(); thread.join(); server.server_close()


async def ready(setup, approve=True):
    factory, recipe, approvals, registry, paired, page, site, path = setup
    r = factory()
    run = r.create('tenant','owner',platform='local_fixture',account='owner',session_id=f"pc.{paired['device_id']}.experiment")
    await r.discover('tenant',run['id'])
    run = await r.preview('tenant',run['id'],'owner',hypothesis='Measure interest, not promised profit',draft='Tutoring pilot',max_minutes=20)
    if approve: approvals.decide(run['approval_id'],ApprovalStatus.APPROVED,'owner')
    return r, run


@pytest.mark.asyncio
async def test_real_login_discovery_preview_publish_readback_restart_duplicate(setup):
    r, run = await ready(setup)
    assert run['state'] == 'awaiting_approval' and run['sources'][0]['url'].endswith('/idea')
    assert run['limits']['cost'] == 0 and run['preview']['values']['[name="audience"]'] == 'public'
    result = await r.execute('tenant',run['id'],'owner')
    assert result['state'] == 'succeeded', result
    assert r.verify_receipt('tenant',result)['provider_id'] == '1'
    assert 'profit remain unverified' in result['outcome']
    restarted = setup[0]()
    assert (await restarted.execute('tenant',run['id'],'owner'))['state'] == 'succeeded'
    assert len(setup[6].posts) == 1
    # Preserve decisive pixels for manual visual inspection.
    from shutil import copyfile
    copyfile(run['preview_image'], '/tmp/m18-login-preview.png')


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['account','draft','audience','terms','action','button'])
async def test_changed_final_state_cannot_submit(setup, change):
    r, run = await ready(setup)
    scripts = {'account': "document.querySelector('#account').textContent='other'",
      'draft': "document.querySelector('#draft').value='different'",
      'audience': "document.querySelector('[name=audience]').value='private'",
      'terms': "document.querySelector('#terms').textContent='Fee: $10'",
      'action': "document.querySelector('form').action='/different'",
      'button': "document.querySelector('#publish').textContent='Buy now'"}
    await setup[5].evaluate(scripts[change])
    with pytest.raises(PermissionError): await r.execute('tenant',run['id'],'owner')
    assert not setup[6].posts


@pytest.mark.asyncio
async def test_no_approval_wrong_actor_and_revocation(setup):
    r, run = await ready(setup,False)
    with pytest.raises(PermissionError): await r.execute('tenant',run['id'],'owner')
    with pytest.raises(PermissionError): await r.execute('tenant',run['id'],'other')
    setup[2].decide(run['approval_id'],ApprovalStatus.DENIED,'owner')
    with pytest.raises(PermissionError): await r.execute('tenant',run['id'],'owner')
    setup[3].revoke('tenant',setup[4]['device_id'])
    with pytest.raises(RuntimeError): await r.execute('tenant',run['id'],'owner')
    assert not setup[6].posts


@pytest.mark.asyncio
async def test_crash_claim_never_repeats_click_and_readback_is_honest(setup):
    r, run = await ready(setup)
    # Emulate persisted pre-network crash state; restart must not dispatch submit.
    r.store.save('tenant',run,'submitting')
    restarted = setup[0]()
    assert (await restarted.execute('tenant',run['id'],'owner'))['state'] == 'submitting'
    assert (await restarted.reconcile('tenant',run['id']))['state'] == 'unknown'
    assert not setup[6].posts


@pytest.mark.asyncio
async def test_receipt_tampering_and_tenant_isolation(setup):
    r, run = await ready(setup)
    result = await r.execute('tenant',run['id'],'owner')
    result['receipt']['evidence']['provider_id']='forged'
    with pytest.raises(PermissionError): r.verify_receipt('tenant',result)
    with pytest.raises(KeyError): r.store.get('other',run['id'])
    with pytest.raises(ValueError): r.create('tenant','owner',platform='instagram',account='owner',session_id=run['session_id'])


@pytest.mark.asyncio
@pytest.mark.parametrize('path,reason',[('/captcha','challenge'),('/throttle','rate_limit')])
async def test_native_daemon_blocks_pause_without_evasion(setup,path,reason):
    from dataclasses import replace
    recipe = replace(setup[1], discovery_url=setup[1].origin+path)
    r = setup[0]({'local_fixture':recipe})
    run = r.create('tenant','owner',platform='local_fixture',account='owner',session_id=f"pc.{setup[4]['device_id']}.experiment")
    result = await r.discover('tenant',run['id'])
    assert result['state']=='paused' and result['pause_reason']==reason
    assert not setup[6].posts


def test_client_receipt_route_rejected_and_schema_closed(oidc_auth_headers):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m18_side_hustle_scraper.login_routes import router
    app=FastAPI();app.include_router(router)
    with TestClient(app) as client:
        response=client.post('/side-hustle-scraper/login-runs/any/receipts',headers=oidc_auth_headers(),json={'status':'succeeded'})
        assert response.status_code==409
    from app.modules.m18_side_hustle_scraper.login_routes import CreateIn
    from pydantic import ValidationError
    with pytest.raises(ValidationError): CreateIn(platform='x',account='a',session_id='pc.a.s',adapter='forged')


@pytest.mark.asyncio
async def test_race_after_server_approval_stops_at_native_device(setup):
    r, run = await ready(setup)
    original = r.sessions.authorize_submit
    async def arm_then_change(*args, **kwargs):
        await original(*args, **kwargs)
        await setup[5].evaluate("document.querySelector('#terms').textContent='Fee: $20'")
    r.sessions.authorize_submit = arm_then_change
    with pytest.raises(RuntimeError): await r.execute('tenant',run['id'],'owner')
    assert r.store.get('tenant',run['id'])['state']=='unknown'
    assert not setup[6].posts


@pytest.mark.asyncio
async def test_wrong_account_and_secret_fields_never_copied(setup):
    factory, recipe, approvals, registry, paired, page, site, path = setup
    r=factory()
    run=r.create('tenant','owner',platform='local_fixture',account='other',session_id=f"pc.{paired['device_id']}.experiment")
    with pytest.raises(PermissionError): await r.discover('tenant',run['id'])
    r, run=await ready(setup)
    await page.evaluate("const n=document.createElement('input');n.name='csrf_token';n.value='DO_NOT_COPY';document.querySelector('form').append(n)")
    with pytest.raises(PermissionError): await r.execute('tenant',run['id'],'owner')
    assert 'DO_NOT_COPY' not in json.dumps(r.store.get('tenant',run['id']))
    assert not site.posts


@pytest.mark.asyncio
async def test_concurrent_duplicate_and_post_submit_crash_reconcile(setup):
    r,run=await ready(setup)
    results=await asyncio.gather(r.execute('tenant',run['id'],'owner'),setup[0]().execute('tenant',run['id'],'owner'),return_exceptions=True)
    assert len(setup[6].posts)==1
    assert any(isinstance(result,dict) and result['state']=='succeeded' for result in results)
    # Simulate the final receipt-store crash after the actual effect.
    stored=r.store.get('tenant',run['id']);stored.pop('receipt')
    r.store.save('tenant',stored,'submitting')
    result=await setup[0]().reconcile('tenant',run['id'])
    assert result['state']=='succeeded' and len(setup[6].posts)==1


@pytest.mark.asyncio
async def test_stale_receipt_cannot_claim_current_run(setup):
    r,run=await ready(setup)
    setup[6].posts.append('Tutoring pilot');setup[6].keys.append('older-run')
    await setup[5].goto(setup[1].origin+'/receipt')
    r.store.save('tenant',run,'submitting')
    result=await r.reconcile('tenant',run['id'])
    assert result['state']=='unknown' and 'receipt' not in result


@pytest.mark.asyncio
async def test_owner_stops_approved_run_before_effect(setup):
    r,run=await ready(setup)
    assert r.stop('tenant',run['id'],'owner')['state']=='stopped'
    with pytest.raises(PermissionError): await r.execute('tenant',run['id'],'owner')
    assert not setup[6].posts


def test_production_mount_and_legacy_client_receipts_rejected(oidc_auth_headers):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m18_side_hustle_scraper import router
    app=FastAPI();app.include_router(router,prefix='/api/v1')
    with TestClient(app) as client:
        for path in ('/runs/r/steps/s/receipts','/durable-runs/r/steps/s/receipts','/login-runs/r/receipts'):
            result=client.post('/api/v1/side-hustle-scraper'+path,headers=oidc_auth_headers(),json={'status':'succeeded'})
            assert result.status_code==409
        result=client.get('/api/v1/side-hustle-scraper/login-runs/r',headers=oidc_auth_headers())
        assert result.status_code==503  # missing production key, not fictional execution


@pytest.mark.asyncio
async def test_expired_experiment_cannot_submit_even_if_approved(setup):
    r,run=await ready(setup)
    run['expires_at']='2000-01-01T00:00:00+00:00'
    r.store.save('tenant',run,'awaiting_approval')
    assert (await r.execute('tenant',run['id'],'owner'))['state']=='expired'
    assert not setup[6].posts


@pytest.mark.parametrize('tenant,session', [
    ('../escape', 'pc.device.experiment'),
    ('/tmp/escape', 'pc.device.experiment'),
    ('tenant', 'pc.device.../../../escape'),
    ('tenant', 'pc.device./tmp/escape'),
    ('tenant', 'pc.device.name\\escape'),
    ('tenant', 'pc.device.%2e%2e%2fescape'),
    ('tenant', 'pc.device.name\x00'),
])
def test_create_rejects_path_components_before_persistence(tmp_path, tenant, session):
    from app.modules.m18_side_hustle_scraper.login_runner import LoginHustleRunner
    store = LoginRunStore(tmp_path/'runs.db')
    # No installed adapter needed: invalid identifiers must fail before lookup.
    r = LoginHustleRunner(store, None, None, {}, b'k'*32)
    with pytest.raises(ValueError, match='identifier|session'):
        r.create(tenant, 'owner', platform='local_fixture', account='owner', session_id=session)


@pytest.mark.parametrize('session', ['pc.d.../escape', 'pc.d./tmp/escape', 'pc.d.name\\escape'])
def test_create_schema_rejects_unsafe_session(session):
    from app.modules.m18_side_hustle_scraper.login_routes import CreateIn
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CreateIn(platform='local_fixture', account='owner', session_id=session)


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['api_key', 'cookie', 'bearer', 'private', 'unreviewed_custom'])
async def test_unknown_fields_never_read_persisted_or_approved(setup, field):
    r, run = await ready(setup, False)
    approval_before = json.dumps(setup[2].get(run['approval_id']), default=str)
    await setup[5].evaluate("name => {const n=document.createElement('input');n.name=name;n.value='DO_NOT_COPY';document.querySelector('form').append(n)}", field)
    with pytest.raises(PermissionError):
        await r.snapshot('tenant', run)
    assert 'DO_NOT_COPY' not in json.dumps(r.store.get('tenant', run['id']))
    assert approval_before == json.dumps(setup[2].get(run['approval_id']), default=str)
    assert not any(field in selector for command in setup[6].commands
                   if command['kind'] == 'read_values'
                   for selector in command['args']['selectors'])
    assert not setup[6].posts


@pytest.mark.asyncio
async def test_first_run_can_repreview_after_second_run_uses_browser(setup):
    r, first = await ready(setup)
    _, second = await ready(setup, False)
    with pytest.raises(PermissionError):
        await r.execute('tenant', first['id'], 'owner')
    refreshed = await r.preview('tenant', first['id'], 'owner', hypothesis='Recheck interest',
                                draft='Reviewed first-run draft', max_minutes=20)
    assert refreshed['approval_id'] != first['approval_id']
    assert refreshed['state'] == 'awaiting_approval'
    assert setup[2].get(refreshed['approval_id'])['status'] == 'pending'
    with pytest.raises(PermissionError):
        await r.execute('tenant', first['id'], 'owner')
    setup[2].decide(refreshed['approval_id'], ApprovalStatus.APPROVED, 'owner')
    assert (await r.execute('tenant', first['id'], 'owner'))['state'] == 'succeeded'
    assert setup[6].posts == ['Reviewed first-run draft']
    assert r.store.get('tenant', second['id'])['state'] == 'awaiting_approval'


def test_screenshot_path_refuses_symlink_escape(tmp_path):
    from app.modules.m13_browser_agent.session_bridge.dispatch import screenshot_path
    root = tmp_path/'root'
    root.mkdir()
    outside = tmp_path/'outside'
    outside.mkdir()
    (root/'tenant').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='root'):
        screenshot_path('tenant', 'pc.device.experiment', root=root)
    assert not list(outside.iterdir())


@pytest.mark.parametrize('tenant,session', [('..', 'pc.device.name'), ('tenant', 'pc.device.../escape')])
def test_screenshot_path_refuses_unsafe_components(tmp_path, tenant, session):
    from app.modules.m13_browser_agent.session_bridge.dispatch import screenshot_path
    with pytest.raises(ValueError):
        screenshot_path(tenant, session, root=tmp_path)


@pytest.mark.asyncio
async def test_recipe_field_allowlist_is_shown_to_reviewer(setup):
    r, run = await ready(setup, False)
    expected = ['draft', 'audience', 'run_id']
    assert run['preview']['allowed_fields'] == expected
    assert setup[2].get(run['approval_id'])['payload']['preview']['allowed_fields'] == expected


@pytest.mark.asyncio
async def test_device_refuses_field_added_after_server_approval(setup):
    r, run = await ready(setup)
    original = r.sessions.authorize_submit
    async def arm_then_add(*args, **kwargs):
        await original(*args, **kwargs)
        await setup[5].evaluate("const n=document.createElement('input');n.name='api_key';n.value='DO_NOT_COPY';document.querySelector('form').append(n)")
    r.sessions.authorize_submit = arm_then_add
    with pytest.raises(RuntimeError):
        await r.execute('tenant', run['id'], 'owner')
    assert r.store.get('tenant', run['id'])['state'] == 'unknown'
    assert not setup[6].posts


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['api_key', 'cookie', 'bearer', 'private', 'custom_field'])
async def test_initial_preview_refuses_unknown_fields_before_fill_or_approval(setup, field):
    factory, recipe, approvals, registry, paired, page, site, path = setup
    r = factory()
    run = r.create('tenant', 'owner', platform='local_fixture', account='owner',
                   session_id=f"pc.{paired['device_id']}.experiment")
    await r.discover('tenant', run['id'])
    site.extra_field = field
    site.commands.clear()
    with pytest.raises(PermissionError):
        await r.preview('tenant', run['id'], 'owner', hypothesis='Bounded test', draft='Draft', max_minutes=10)
    assert not any(command['kind'] in {'fill', 'read_values', 'screenshot'} for command in site.commands)
    assert r.store.get('tenant', run['id'])['state'] == 'blueprint_ready'
    assert 'DO_NOT_COPY' not in json.dumps(r.store.get('tenant', run['id']))
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    with approvals._sessions() as db:
        assert db.query(ApprovalRequestRow).count() == 0
    assert not site.posts


@pytest.mark.asyncio
@pytest.mark.parametrize('markup', [
    '<input name="audience" value="duplicate">',
    '<input value="unnamed">',
    '<input name="draft" form="other" value="external">',
])
async def test_unreviewable_controls_refused(setup, markup):
    r, run = await ready(setup, False)
    await setup[5].evaluate("html => document.querySelector('form').insertAdjacentHTML('beforeend', html)", markup)
    with pytest.raises(PermissionError):
        await r.snapshot('tenant', run)
    assert not setup[6].posts


# ---- audit fixes: F1 submit-control overrides, F2 arming, F3 identifier cap, F4 revoke ----

OVERRIDES = ["formaction='/evil'", "formmethod='get'", "formenctype='text/plain'", "formtarget='_blank'"]


@pytest.mark.asyncio
@pytest.mark.parametrize('attr', OVERRIDES)
async def test_f1_submit_control_override_refused_at_preview(setup, attr):
    factory, recipe, approvals, registry, paired, page, site, path = setup
    r = factory()
    run = r.create('tenant', 'owner', platform='local_fixture', account='owner',
                   session_id=f"pc.{paired['device_id']}.experiment")
    await r.discover('tenant', run['id'])
    name, value = attr.split('=')
    site.submit_attr = (name, value.strip("'"))
    with pytest.raises(PermissionError):
        await r.preview('tenant', run['id'], 'owner', hypothesis='Bounded test', draft='Draft', max_minutes=10)
    assert r.store.get('tenant', run['id'])['state'] == 'blueprint_ready'
    assert not site.posts


@pytest.mark.asyncio
@pytest.mark.parametrize('attr', ['formaction', 'formmethod', 'formenctype', 'formtarget'])
async def test_f1_device_refuses_override_added_after_approval(setup, attr):
    r, run = await ready(setup)
    original = r.sessions.authorize_submit
    async def arm_then_override(*args, **kwargs):
        await original(*args, **kwargs)
        await setup[5].evaluate("a => document.querySelector('#publish').setAttribute(a, a=='formaction' ? '/evil' : a=='formmethod' ? 'get' : a=='formtarget' ? '_blank' : 'text/plain')", attr)
    r.sessions.authorize_submit = arm_then_override
    with pytest.raises(RuntimeError):
        await r.execute('tenant', run['id'], 'owner')
    assert not setup[6].posts
    assert r.store.get('tenant', run['id'])['state'] == 'unknown'


@pytest.mark.asyncio
async def test_f2_intervening_click_cannot_consume_arming_or_unverify_submit(setup):
    r, run = await ready(setup)
    original = r.sessions.authorize_submit
    async def arm_then_click_elsewhere(*args, **kwargs):
        await original(*args, **kwargs)
        other = await r.sessions.page('tenant', run['session_id'], True)
        with pytest.raises(Exception):
            await other.locator('#draft').click()
    r.sessions.authorize_submit = arm_then_click_elsewhere
    setup[6].commands.clear()
    result = await r.execute('tenant', run['id'], 'owner')
    assert result['state'] == 'succeeded', result
    submits = [c for c in setup[6].commands if c['kind'] == 'click_submit']
    navs = [c for c in setup[6].commands if c['kind'] == 'click_nav']
    assert len(submits) == 1 and submits[0]['args']['selector'] == '#publish'
    assert not any(c['args']['selector'] == '#publish' for c in navs)
    assert setup[6].posts == ['Tutoring pilot']


@pytest.mark.asyncio
async def test_f2_lost_arming_fails_closed_before_any_unverified_click_and_recovers(setup):
    r, run = await ready(setup)
    original = r.sessions.authorize_submit
    async def arm_then_lose(*args, **kwargs):
        await original(*args, **kwargs)
        r.sessions._armed.clear()
    r.sessions.authorize_submit = arm_then_lose
    setup[6].commands.clear()
    with pytest.raises(PermissionError):
        await r.execute('tenant', run['id'], 'owner')
    assert not setup[6].posts
    assert not any(c['args'].get('selector') == '#publish' for c in setup[6].commands)
    burned = r.store.get('tenant', run['id'])
    assert burned['state'] == 'approval_burned'
    # Recovery: nothing was dispatched, so a fresh reviewed preview and approval may continue.
    r.sessions.authorize_submit = original
    fresh = await r.preview('tenant', run['id'], 'owner', hypothesis='Retry after burned approval', draft='Tutoring pilot', max_minutes=20)
    assert fresh['approval_id'] != run['approval_id'] and fresh['state'] == 'awaiting_approval'
    setup[2].decide(fresh['approval_id'], ApprovalStatus.APPROVED, 'owner')
    assert (await r.execute('tenant', run['id'], 'owner'))['state'] == 'succeeded'
    assert setup[6].posts == ['Tutoring pilot']


@pytest.mark.asyncio
async def test_f2_click_verified_as_submit_or_run_is_unknown(setup):
    r, run = await ready(setup)
    # Device answers a click without echoing the approved submit identity.
    original = r.sessions._execute
    async def strip(tenant, device, name, kind, args, timeout=60.0):
        result = await original(tenant, device, name, kind, args, timeout=timeout)
        result.pop('approval_id', None)
        return result
    r.sessions._execute = strip
    with pytest.raises(PermissionError):
        await r.execute('tenant', run['id'], 'owner')
    assert r.store.get('tenant', run['id'])['state'] == 'unknown'


def test_f3_identifier_cap_matches_daemon_page_key():
    from app.modules.m13_browser_agent.session_bridge.protocol import validate_identifier, make_pc_session
    assert validate_identifier('a' * 120) == 'a' * 120
    for n in (121, 128):
        with pytest.raises(ValueError):
            validate_identifier('a' * n)
        with pytest.raises(ValueError):
            make_pc_session('dev', 'a' * n)


@pytest.mark.asyncio
async def test_f4_reprieview_revokes_superseded_approval(setup):
    r, first = await ready(setup)
    old = first['approval_id']
    assert setup[2].get(old)['status'] == 'approved'
    second = await r.preview('tenant', first['id'], 'owner', hypothesis='Recheck', draft='Changed draft', max_minutes=20)
    assert second['approval_id'] != old
    assert setup[2].get(old)['status'] == 'denied'
    with pytest.raises(Exception):
        setup[2].consume_effect(old, module_id=18, action_type='login_publish',
                                payload=r.payload(first), user_id='tenant', effect_id='x', actor='owner')
    assert setup[2].get(second['approval_id'])['status'] == 'pending'


@pytest.mark.asyncio
@pytest.mark.parametrize('attr', OVERRIDES)
async def test_f1_daemon_preclick_independently_refuses_submit_override(setup, attr):
    from app.modules.m18_side_hustle_scraper.login_runner import LoginHustleRunner
    factory, recipe, approvals, registry, paired, page, site, path = setup
    name, value = attr.split('=')
    site.submit_attr = (name, value.strip("'"))
    r = factory()
    real = LoginHustleRunner.form_selectors
    def lax(soup, button, rec):  # simulate a server that missed the override
        form = button.find_parent('form')
        return [f'[name="{n.get("name")}"]' for n in form.select('input,textarea,select,button[name]')]
    LoginHustleRunner.form_selectors = staticmethod(lax)
    try:
        run = r.create('tenant', 'owner', platform='local_fixture', account='owner',
                       session_id=f"pc.{paired['device_id']}.experiment")
        await r.discover('tenant', run['id'])
        run = await r.preview('tenant', run['id'], 'owner', hypothesis='Bounded', draft='Draft', max_minutes=10)
        approvals.decide(run['approval_id'], ApprovalStatus.APPROVED, 'owner')
        with pytest.raises(RuntimeError):
            await r.execute('tenant', run['id'], 'owner')
    finally:
        LoginHustleRunner.form_selectors = real
    assert not site.posts
