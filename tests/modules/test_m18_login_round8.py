"""Round-8 fixes for the round-7 audit. The auditor's vectors (test_aud_round7.py, test_aud_sw.py,
store harness) are turned into assertions here. Real Chromium and a local fixture site only."""
import json
import time
from pathlib import Path

import pytest

from test_m18_login_browser import setup, _compose_with_values, setup_daemon  # noqa: F401
from test_m18_login_round5 import _nav_click
from test_aud_round7 import V as AUD_VECTORS, SECRET, leaked
from test_aud_sw import SW
from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon, DeviceIdentity
from app.modules.m13_browser_agent.session_bridge.form_guard import parse_set_cookie


@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(AUD_VECTORS))
async def test_v1_v2_auditor_vector_never_reaches_the_server(setup, name):
    page, _ = await _compose_with_values(setup)
    site = setup[6]
    await page.fill('#draft', SECRET)
    await page.evaluate(AUD_VECTORS[name])
    site.hits.clear(); site.posts.clear(); site.post_paths.clear()
    await _nav_click(setup, '#attack')
    for _ in range(20 if '12s' in name else 9):  # the 6s and 12s timers fire long after the click window
        await page.wait_for_timeout(700)
    assert not leaked(site), (name, [h[1:3] for h in site.hits if h[2] != '/compose'][:6], site.posts)
    assert not site.posts and not site.post_paths


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['sw_post_during_click', 'sw_post_after_quiet', 'host_subdomain'])
async def test_service_worker_vectors_never_reach_the_server(setup, mode):
    page, _ = await _compose_with_values(setup); site = setup[6]
    orig = site.do_GET

    def do_GET(self):
        if self.path == '/sw.js':
            self.send_response(200); self.send_header('Content-Type', 'text/javascript'); self.end_headers(); self.wfile.write(SW); return
        return orig(self)
    site.do_GET = do_GET
    await page.fill('#draft', SECRET)
    await page.evaluate("navigator.serviceWorker.register('/sw.js').then(()=>navigator.serviceWorker.ready)")
    await page.wait_for_timeout(1500)
    BTN = "document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>');"
    code = {'sw_post_during_click': "navigator.serviceWorker.controller.postMessage('draft=UNAPPROVEDSECRET&run_id=attack')",
            'sw_post_after_quiet': "setTimeout(()=>navigator.serviceWorker.controller.postMessage('draft=UNAPPROVEDSECRET&run_id=attack'),6000)",
            'host_subdomain': "new Image().src='http://'+document.querySelector('#draft').value.toLowerCase()+'.localhost:'+location.port+'/'"}[mode]
    await page.evaluate(BTN + f"document.querySelector('#attack').addEventListener('click',()=>{{{code}}});")
    site.hits.clear(); site.posts.clear()
    await _nav_click(setup, '#attack')
    for _ in range(9):
        await page.wait_for_timeout(700)
    assert not site.posts and not [h for h in site.hits if h[2] != '/sw.js' and ('unapproved' in h[0].lower() or h[0].split(':')[0] != '127.0.0.1')], site.hits


@pytest.mark.asyncio
async def test_guard_does_not_touch_other_tabs_of_the_shared_browser(setup):
    page, _ = await _compose_with_values(setup)
    other = await page.context.new_page()
    await other.goto(setup[1].origin + '/compose')
    await page.evaluate("document.body.insertAdjacentHTML('beforeend','<a id=\"lnk\" href=\"/idea\">l</a>')")
    await _nav_click(setup, '#lnk')
    await other.fill('#draft', 'owner typed this'); await other.fill('#run_id', 'owner-run')
    await other.evaluate("fetch('/publish',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:'draft=owner&run_id=owner-run'})")
    await other.wait_for_timeout(500)
    assert setup[6].posts == ['owner'], 'the owner\'s own tab must keep working while a guard rests on the session page'
    await other.close()


@pytest.mark.asyncio
async def test_resting_guard_lifts_when_the_daemon_navigates(setup):
    page, _ = await _compose_with_values(setup)
    await page.evaluate("document.body.insertAdjacentHTML('beforeend','<a id=\"lnk\" href=\"/idea\">l</a>')")
    assert (await _nav_click(setup, '#lnk'))['ok'] is True
    daemon = setup_daemon(setup)
    from app.modules.m13_browser_agent.session_bridge import protocol
    nav = await daemon.execute(protocol.make_command(protocol.CommandKind.NAVIGATE, {'session': 'experiment', 'url': setup[1].compose_url}))
    assert nav['ok'] is True and 'experiment' not in daemon._resting


# ---- store (auditor harness cases) ------------------------------------------------------------
def mk(tmp, dev='dev1', cp='consumed.json', secret='s3cret' * 4):
    ident = DeviceIdentity.load_or_create(Path(tmp) / 'id.pem')
    cfg = DaemonConfig(device_id=dev, command_secret=secret, capabilities=['click_submit'], pacing_seconds=0,
                       consumed_path=str(Path(tmp) / cp))
    return Daemon(cfg, ident)


def K(n): return (f'token:{n}', f'approval:{n}')
def dl(): return time.time() + 300


def test_store_c1_snapshot_restore_with_primary_anchor_deleted(tmp_path):
    d = mk(tmp_path); snap = Path(d.consumed_path).read_text()
    assert d._consume_submit(K(1), dl()) is None
    Path(d.consumed_path).write_text(snap); d.anchor_paths()[0].unlink()
    assert mk(tmp_path)._consume_submit(K(1), dl()) is not None


def test_store_c2_snapshot_and_primary_anchor_both_restored(tmp_path):
    d = mk(tmp_path); snap = Path(d.consumed_path).read_text(); a = d.anchor_paths()[0].read_text()
    assert d._consume_submit(K(1), dl()) is None
    Path(d.consumed_path).write_text(snap); d.anchor_paths()[0].write_text(a)
    assert mk(tmp_path)._consume_submit(K(1), dl()) is not None  # the secondary tree still knows


def test_store_c3_used_snapshot_restored_and_anchor_deleted(tmp_path):
    d = mk(tmp_path); assert d._consume_submit(K(0), dl()) is None
    snap = Path(d.consumed_path).read_text()
    assert d._consume_submit(K(1), dl()) is None
    Path(d.consumed_path).write_text(snap); d.anchor_paths()[0].unlink()
    assert mk(tmp_path)._consume_submit(K(1), dl()) is not None


def test_store_c8_anchor_directory_changed_is_refused(tmp_path, monkeypatch):
    d = mk(tmp_path); snap = Path(d.consumed_path).read_text()
    assert d._consume_submit(K(1), dl()) is None
    Path(d.consumed_path).write_text(snap)
    monkeypatch.setenv('ATLAS_PC_ANCHOR_DIR', str(tmp_path / 'anchors-moved'))
    d2 = Daemon(d.config, d.identity)
    assert d2._store_error and d2._consume_submit(K(1), dl()) is not None
    monkeypatch.setenv('ATLAS_PC_ANCHOR_DIR2', str(tmp_path / 'secondary-moved'))
    assert Daemon(d.config, d.identity)._consume_submit(K(1), dl()) is not None


def test_store_c5_c6_second_path_same_device_only_one_daemon_can_consume(tmp_path):
    a = mk(tmp_path); b = mk(tmp_path, cp='other.json'); t = dl() + 1
    ra = a._consume_submit(K(9), t); rb = b._consume_submit(K(9), t)
    assert [ra is None, rb is None].count(True) == 1, (ra, rb)


def test_store_c9_corrupt_then_restore_same_process(tmp_path):
    d = mk(tmp_path); assert d._consume_submit(K(0), dl()) is None
    snap1 = Path(d.consumed_path).read_text()
    Path(d.consumed_path).write_text('garbage')
    assert d._consume_submit(K(2), dl()) is not None
    Path(d.consumed_path).write_text(snap1)
    assert d._consume_submit(K(2), dl()) is not None


def test_store_c11_anchor_directory_read_only_never_double_spends(tmp_path):
    import os
    d = mk(tmp_path); os.chmod(d.anchor_paths()[0].parent, 0o500)
    try:
        first = d._consume_submit(K(1), dl())
    finally:
        os.chmod(d.anchor_paths()[0].parent, 0o700)
    second = d._consume_submit(K(1), dl())
    assert second is not None  # whatever happened to the first, the key is never accepted twice


def test_store_c12_unset_consumed_path_is_not_memory_only(tmp_path, monkeypatch):
    import app.modules.m13_browser_agent.pc_daemon.config as cfgmod
    monkeypatch.setattr(cfgmod, 'DEFAULT_STATE_DIR', tmp_path / 'state')
    ident = DeviceIdentity.load_or_create(tmp_path / 'id.pem')
    cfg = DaemonConfig(device_id='d', command_secret='x' * 32, capabilities=['click_submit'], pacing_seconds=0, consumed_path='')
    a = Daemon(cfg, ident); assert a._consume_submit(K(1), dl()) is None
    assert Daemon(cfg, ident)._consume_submit(K(1), dl()) is not None


# ---- cookies ----------------------------------------------------------------------------------
def test_cookie_empty_and_spaced_names_and_huge_max_age():
    url = 'http://127.0.0.1:1/x'
    now = 1_700_000_000.0
    p = lambda raw: parse_set_cookie(url, raw, now=now)
    assert p('=bare; Path=/')['set'] == {**p('=bare; Path=/')['set'], 'name': '', 'value': 'bare'}
    assert p('novalue')['set']['name'] == '' and p('novalue')['set']['value'] == 'novalue'
    assert p('a b=1')['set']['name'] == 'a b'
    assert p('=') is None
    assert p('a=1; Max-Age=99999999999999999999999')['set']['expires'] <= now + 400 * 86400


@pytest.mark.asyncio
async def test_cookie_chromium_stores_what_the_parser_returns(setup):
    factory, recipe, approvals, registry, paired, page, site, path = setup
    from test_m18_login_browser import ready
    from test_m18_login_round5 import _get_redirects
    from urllib.parse import parse_qs
    orig_post = site.do_POST

    def do_POST(self):
        if self.path == '/publish':
            body = self.rfile.read(int(self.headers['Content-Length'])).decode()
            site.posts.append(parse_qs(body)['draft'][0]); site.keys.append(parse_qs(body)['run_id'][0])
            self.send_response(303)
            for header in ['=emptyname; Path=/', 'spaced name=v; Path=/', 'big=1; Max-Age=99999999999999999999999; Path=/']:
                self.send_header('Set-Cookie', header)
            self.send_header('Location', '/hop'); self.end_headers(); return
        orig_post(self)
    site.do_POST = do_POST
    _get_redirects(site, {'/hop': (302, '/receipt')})
    r, run = await ready(setup)
    try:
        await r.execute('tenant', run['id'], 'owner')
    except Exception:
        pass
    assert len(site.posts) == 1
    cookies = {c['name']: c for c in await page.context.cookies()}
    assert 'big' in cookies and cookies['big']['expires'] > time.time(), cookies
    assert 'spaced name' in cookies, cookies
    assert '' in cookies and cookies['']['value'] == 'emptyname', cookies
