"""Round-6 fixes for the round-5 audit (V1 unmonitored clicks, V2 replayable consumed store,
Set-Cookie on guard hops). Real Chromium, local fixture site only; nothing is mocked."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from test_m18_login_browser import setup, ready, _compose_with_values, setup_daemon  # noqa: F401
from test_m18_login_round5 import _get_redirects, _nav_click
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon
from app.modules.m13_browser_agent.session_bridge import protocol


def _last_submit_args(setup):
    return dict([c for c in setup[6].commands if c['kind'] == 'click_submit'][-1]['args'])


async def _submit_once(setup):
    r, run = await ready(setup)
    assert (await r.execute('tenant', run['id'], 'owner'))['state'] == 'succeeded'
    args = _last_submit_args(setup)
    page, _ = await _compose_with_values(setup)
    for selector, value in args['values'].items():
        await page.fill(selector, value)
    return args


async def _replay(setup, daemon, args):
    return await daemon.execute(protocol.make_command(protocol.CommandKind.CLICK_SUBMIT, args))


@pytest.mark.asyncio
@pytest.mark.parametrize('script', [
    # timer-driven submit after a click on a non-form control
    "document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>');"
    "document.querySelector('#attack').addEventListener('click',()=>setTimeout(()=>document.querySelector('form').requestSubmit(),80))",
    # script POST that is not a form at all
    "document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>');"
    "document.querySelector('#attack').addEventListener('click',()=>fetch('/publish',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:'draft=UNAPPROVED&run_id=attack'}))",
    # sendBeacon
    "document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>');"
    "document.querySelector('#attack').addEventListener('click',()=>navigator.sendBeacon('/publish','draft=UNAPPROVED&run_id=attack'))",
    # form.submit() bypasses submit events entirely
    "document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>');"
    "document.querySelector('#attack').addEventListener('click',()=>document.querySelector('form').submit())",
])
async def test_v1_every_click_is_guarded(setup, script):
    page, _ = await _compose_with_values(setup)
    await page.fill('#draft', 'UNAPPROVED')
    await page.evaluate(script)
    answer = await _nav_click(setup, '#attack')
    assert not setup[6].posts and not setup[6].post_paths, (answer, setup[6].hits)
    assert answer['ok'] is False and 'blocked' in answer['error'], answer


@pytest.mark.asyncio
async def test_v1_plain_get_navigation_still_works_and_reports_clean(setup):
    page, _ = await _compose_with_values(setup)
    await page.evaluate("document.body.insertAdjacentHTML('beforeend','<a id=\"lnk\" href=\"/idea\">l</a>')")
    answer = await _nav_click(setup, '#lnk')
    assert answer['ok'] is True and answer['result']['guard']['blocked'] == [], answer
    assert answer['result']['url'].endswith('/idea')


@pytest.mark.asyncio
async def test_v2_unparseable_record_refuses_clearly_without_bricking(setup):
    old = setup_daemon(setup)
    args = await _submit_once(setup)
    Path(old.consumed_path).write_text('{not json')
    fresh = Daemon(old.config, old.identity)  # must not raise
    fresh.browser = old.browser
    answer = await _replay(setup, fresh, args)
    assert answer['ok'] is False and 'consumed-submit record' in answer['error'], answer
    assert len(setup[6].posts) == 1
    nav = await fresh.execute(protocol.make_command(protocol.CommandKind.NAVIGATE, {'session': 'experiment', 'url': setup[1].compose_url}))
    assert nav['ok'] is True, nav
    # Recovery path: move the bad file aside, restart. Old tokens stay refused.
    Path(old.consumed_path).rename(Path(old.consumed_path).with_suffix('.bad'))
    restarted = Daemon(old.config, old.identity); restarted.browser = old.browser
    answer = await _replay(setup, restarted, args)
    assert answer['ok'] is False and len(setup[6].posts) == 1, answer


@pytest.mark.asyncio
async def test_v2_record_deleted_under_a_running_daemon_refuses(setup):
    old = setup_daemon(setup)
    args = await _submit_once(setup)
    Path(old.consumed_path).unlink()
    answer = await _replay(setup, old, args)
    assert answer['ok'] is False and len(setup[6].posts) == 1, answer


@pytest.mark.asyncio
async def test_v2_restoring_an_older_valid_record_refuses(setup):
    old = setup_daemon(setup)
    snapshot = Path(old.consumed_path).read_text()  # valid, signed, before any use
    args = await _submit_once(setup)
    Path(old.consumed_path).write_text(snapshot)
    answer = await _replay(setup, old, args)
    assert answer['ok'] is False and 'backwards' in answer['error'], answer
    assert len(setup[6].posts) == 1


@pytest.mark.asyncio
async def test_v2_hand_edited_valid_json_with_wrong_mac_refuses(setup):
    old = setup_daemon(setup)
    args = await _submit_once(setup)
    raw = json.loads(Path(old.consumed_path).read_text())
    raw['consumed'] = {}
    Path(old.consumed_path).write_text(json.dumps(raw))
    answer = await _replay(setup, old, args)
    assert answer['ok'] is False and len(setup[6].posts) == 1, answer


@pytest.mark.asyncio
async def test_v2_two_processes_style_race_consumes_exactly_once(setup):
    old = setup_daemon(setup)
    daemons = [old] + [Daemon(old.config, old.identity) for _ in range(5)]
    from app.modules.m13_browser_agent.session_bridge.form_guard import ARM_TTL_SECONDS
    deadline = time.time() + ARM_TTL_SECONDS  # armed now, after the store exists
    keys = ('token:race', 'approval:race')
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda d: d._consume_submit(keys, deadline), daemons * 3))
    assert results.count(None) == 1, results


@pytest.mark.asyncio
async def test_minor_set_cookie_on_guard_redirect_hop_is_persisted(setup):
    factory, recipe, approvals, registry, paired, page, site, path = setup
    from urllib.parse import parse_qs
    orig_post = site.do_POST

    def do_POST(self):
        if self.path == '/publish':
            body = self.rfile.read(int(self.headers['Content-Length'])).decode()
            site.posts.append(parse_qs(body)['draft'][0]); site.keys.append(parse_qs(body)['run_id'][0])
            self.send_response(303); self.send_header('Set-Cookie', 'sid=hop1; Path=/; HttpOnly')
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
    cookies = {c['name']: c['value'] for c in await page.context.cookies()}
    assert cookies.get('sid') == 'hop1', cookies
