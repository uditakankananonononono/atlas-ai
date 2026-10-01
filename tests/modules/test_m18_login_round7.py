"""Round-7 fixes for the round-6 audit. Real Chromium and a local fixture site only."""
import json
import shutil
import time
from pathlib import Path

import pytest

from test_m18_login_browser import setup, ready, _compose_with_values, setup_daemon  # noqa: F401
from test_m18_login_round5 import _get_redirects, _nav_click
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon
from app.modules.m13_browser_agent.session_bridge import protocol

BTN = "document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>');"
POSTBODY = "{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:'draft=UNAPPROVED&run_id=attack'}"


def _on_click(action, delay=0):
    inner = action if not delay else f"setTimeout(()=>{{{action}}},{delay})"
    return BTN + f"document.querySelector('#attack').addEventListener('click',()=>{{{inner}}});"


def _leaked(site):
    return bool(site.posts or site.post_paths or any('UNAPPROVED' in str(hit) for hit in site.hits))


V1 = {
    'fetch_400': _on_click(f"fetch('/publish',{POSTBODY})", 400),
    'fetch_1500': _on_click(f"fetch('/publish',{POSTBODY})", 1500),
    'submit_400': _on_click("document.querySelector('form').submit()", 400),
    'submit_1500': _on_click("document.querySelector('form').submit()", 1500),
    'beacon_1500': _on_click("navigator.sendBeacon('/publish','draft=UNAPPROVED&run_id=attack')", 1500),
    'syncxhr_400': _on_click("const x=new XMLHttpRequest();x.open('POST','/publish',false);x.setRequestHeader('content-type','application/x-www-form-urlencoded');x.send('draft=UNAPPROVED&run_id=attack')", 400),
    'pagehide': BTN + "addEventListener('pagehide',()=>fetch('/publish',{method:'POST',keepalive:true,headers:{'content-type':'application/x-www-form-urlencoded'},body:'draft=UNAPPROVED&run_id=attack'}));"
                "document.querySelector('#attack').addEventListener('click',()=>{location.href='/idea'});",
    'get_form_submit': _on_click("const f=document.querySelector('form');f.method='get';f.action='/publish';f.submit()", 100),
    'image_cross_origin': _on_click("new Image().src='http://localhost:'+location.port+'/pix?draft='+document.querySelector('#draft').value", 100),
    'fetch_get_no_cors': _on_click("fetch('http://localhost:'+location.port+'/pix?d='+document.querySelector('#draft').value,{mode:'no-cors'})", 100),
    'location_cross_origin': _on_click("location.href='http://localhost:'+location.port+'/idea?draft='+document.querySelector('#draft').value", 100),
    'popup_autopost': _on_click("const w=window.open('');w.document.write('<form method=post action='+location.origin+'/publish><input name=draft value=UNAPPROVED><input name=run_id value=attack></form><script>document.forms[0].submit()<\\/script>')"),
    'form_target_blank': _on_click("const f=document.querySelector('form');f.target='_blank';f.submit()"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(V1))
async def test_v1_context_level_guard_with_quiet_period(setup, name):
    page, _ = await _compose_with_values(setup)
    await page.fill('#draft', 'UNAPPROVED')
    await page.evaluate(V1[name])
    answer = await _nav_click(setup, '#attack')
    for _ in range(3):  # anything still in flight after the answer would show up here
        await page.wait_for_timeout(700)
    assert not _leaked(setup[6]), (name, answer, setup[6].hits)
    assert answer['ok'] is False and 'blocked' in answer['error'], (name, answer)


@pytest.mark.asyncio
async def test_v1_plain_links_still_work_and_new_pages_are_closed(setup):
    page, _ = await _compose_with_values(setup)
    await page.evaluate("document.body.insertAdjacentHTML('beforeend','<a id=\"lnk\" href=\"/idea?page=2\">l</a>')")
    answer = await _nav_click(setup, '#lnk')
    assert answer['ok'] is True and answer['result']['guard']['blocked'] == [], answer
    assert len(page.context.pages) == 1


def _args_pair(setup):
    return dict([c for c in setup[6].commands if c['kind'] == 'click_submit'][-1]['args'])


async def _used(setup):
    r, run = await ready(setup)
    assert (await r.execute('tenant', run['id'], 'owner'))['state'] == 'succeeded'
    args = _args_pair(setup)
    page, _ = await _compose_with_values(setup)
    for selector, value in args['values'].items():
        await page.fill(selector, value)
    return args


async def _replay(daemon, args):
    return await daemon.execute(protocol.make_command(protocol.CommandKind.CLICK_SUBMIT, args))


def _fresh(old):
    d = Daemon(old.config, old.identity); d.browser = old.browser
    return d


@pytest.mark.asyncio
async def test_v2a_pre_use_snapshot_restored_while_down_then_fresh_daemon(setup):
    old = setup_daemon(setup)
    snap = Path(old.consumed_path).read_text()
    args = await _used(setup)
    Path(old.consumed_path).write_text(snap)
    answer = await _replay(_fresh(old), args)
    assert answer['ok'] is False and len(setup[6].posts) == 1, answer


@pytest.mark.asyncio
async def test_v2l_older_post_use_snapshot_restored(setup):
    old = setup_daemon(setup)
    deadline = time.time() + 300
    assert old._consume_submit(('token:x1', 'approval:x1'), deadline) is None
    snap = Path(old.consumed_path).read_text()
    assert old._consume_submit(('token:x2', 'approval:x2'), deadline) is None
    Path(old.consumed_path).write_text(snap)
    fresh = _fresh(old)
    assert fresh._consume_submit(('token:x2', 'approval:x2'), deadline) is not None
    assert old._consume_submit(('token:x2', 'approval:x2'), deadline) is not None


@pytest.mark.asyncio
async def test_v2b_delete_record_and_lock_then_restart(setup):
    old = setup_daemon(setup)
    args = await _used(setup)
    Path(old.consumed_path).unlink(); Path(old.consumed_path + '.lock').unlink()
    answer = await _replay(_fresh(old), args)
    assert answer['ok'] is False and len(setup[6].posts) == 1, answer


@pytest.mark.asyncio
async def test_v2d_corrupt_then_restore_old_valid_snapshot_same_daemon(setup):
    old = setup_daemon(setup)
    snap = Path(old.consumed_path).read_text()
    args = await _used(setup)
    Path(old.consumed_path).write_text('garbage')
    assert (await _replay(old, args))['ok'] is False
    Path(old.consumed_path).write_text(snap)  # valid, signed, older
    answer = await _replay(old, args)
    assert answer['ok'] is False and len(setup[6].posts) == 1, answer


@pytest.mark.asyncio
async def test_v2e_second_daemon_other_consumed_path_same_device(setup, tmp_path):
    import dataclasses
    old = setup_daemon(setup)
    args = await _used(setup)
    other = Daemon(dataclasses.replace(old.config, consumed_path=str(tmp_path / 'elsewhere' / 'c.json')), old.identity)
    other.browser = old.browser
    answer = await _replay(other, args)
    assert answer['ok'] is False and len(setup[6].posts) == 1, answer


@pytest.mark.asyncio
async def test_v2_record_from_another_device_is_refused(setup, tmp_path):
    import dataclasses
    old = setup_daemon(setup)
    foreign = dataclasses.replace(old.config, device_id='someone-else', consumed_path=str(tmp_path / 'f.json'))
    Daemon(foreign, old.identity)
    shutil.copy(tmp_path / 'f.json', old.consumed_path)
    d = _fresh(old)
    assert d._store_error
    assert d._consume_submit(('token:y', 'approval:y'), time.time() + 100) is not None


def test_v3_parser_cases():
    from app.modules.m13_browser_agent.session_bridge.form_guard import parse_set_cookie
    url = 'http://127.0.0.1:1/x/y'
    now = 1_700_000_000.0
    p = lambda raw: parse_set_cookie(url, raw, now=now)
    assert 'delete' in p('a=1; Expires=Wed, 21 Oct 2015 07:28:00 GMT; Path=/')
    assert 'delete' in p('a=1; Max-Age=0')
    assert 'delete' in p('a=1; Max-Age=-5')
    assert p('a=1; Max-Age=60; Expires=Wed, 21 Oct 2015 07:28:00 GMT')['set']['expires'] == now + 60
    assert p('a="x,y z"; Path=/')['set']['value'] == '"x,y z"'
    assert p('a=1; Expires=Wed, 21 Oct 2099 07:28:00 GMT')['set']['expires'] > now
    assert p('a=1; Secure; Partitioned')['set']['partitionKey'] == 'http://127.0.0.1'
    assert p('a=1; Partitioned') is None  # Partitioned requires Secure
    assert p('__Host-a=1; Secure; Path=/') is not None and p('__Host-a=1; Path=/') is None
    assert p('a=1; Domain=evil.example') is None
    assert p('a=1; SameSite=None') is None
    assert parse_set_cookie('http://example.com/', 'a=1; Secure') is None


@pytest.mark.asyncio
async def test_v3_set_cookie_hop_semantics_in_chromium(setup):
    factory, recipe, approvals, registry, paired, page, site, path = setup
    from urllib.parse import parse_qs
    orig_post = site.do_POST
    await page.context.add_cookies([{'name': 'gone', 'value': 'old', 'domain': '127.0.0.1', 'path': '/'}])

    def do_POST(self):
        if self.path == '/publish':
            body = self.rfile.read(int(self.headers['Content-Length'])).decode()
            site.posts.append(parse_qs(body)['draft'][0]); site.keys.append(parse_qs(body)['run_id'][0])
            self.send_response(303)
            for header in ['gone=; Max-Age=0; Path=/', 'dead=1; Expires=Wed, 21 Oct 2015 07:28:00 GMT; Path=/',
                           'q="a,b c"; Path=/', 'part=1; Secure; Partitioned; Path=/; SameSite=None',
                           'sid=hop1; Path=/; HttpOnly']:
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
    assert 'gone' not in cookies and 'dead' not in cookies, cookies
    assert cookies['sid']['value'] == 'hop1' and cookies['sid']['httpOnly'] is True
    assert cookies['q']['value'] == '"a,b c"', cookies
    assert 'part' in cookies, cookies
