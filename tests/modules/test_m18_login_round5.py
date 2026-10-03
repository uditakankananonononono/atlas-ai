"""Round-5 fixes for the round-4 audit failures (F1-F4, M13 gaps). Real Chromium, local fixture site only."""
import time

import pytest

from test_m18_login_browser import setup, ready, _compose_with_values, setup_daemon  # noqa: F401
from app.modules.m13_browser_agent.security import values_digest
from app.modules.m13_browser_agent.session_bridge import protocol


def _port(recipe):
    return recipe.compose_url.split(':')[2].split('/')[0]


def _get_redirects(site, table):
    """Give the fixture site GET redirects (it only had POST ones)."""
    site.get_redirects = table
    if not getattr(site, '_orig_do_GET', None):
        site._orig_do_GET = site.do_GET

        def do_GET(self):
            if self.path in site.get_redirects:
                site.hits.append((self.headers['Host'], 'GET', self.path, ''))
                code, loc = site.get_redirects[self.path]
                self.send_response(code); self.send_header('Location', loc); self.end_headers(); return
            site._orig_do_GET(self)
        site.do_GET = do_GET


async def _run_expect_blocked(setup, post_redirect, get_table):
    factory, recipe, approvals, registry, paired, page, site, path = setup
    r, run = await ready(setup)
    _get_redirects(site, get_table)
    site.redirect = post_redirect
    try:
        await r.execute('tenant', run['id'], 'owner')
    except Exception:
        pass
    site.redirect = None
    return r, run, site


@pytest.mark.asyncio
@pytest.mark.parametrize('first', [301, 302, 303])
async def test_r5_f1_same_origin_redirect_chain_reaching_cross_origin_get_is_blocked(setup, first):
    port = _port(setup[1])
    r, run, site = await _run_expect_blocked(
        setup, (first, '/hop1'), {'/hop1': (302, f'http://localhost:{port}/sink')})
    assert [h for h in site.hits if h[0].startswith('localhost')] == [], site.hits
    blocked = (r.store.get('tenant', run['id']).get('guard') or {}).get('blocked', [])
    assert any('redirect' in item for item in blocked), blocked


@pytest.mark.asyncio
async def test_r5_f1_cross_origin_303_then_further_hops_are_judged(setup):
    port = _port(setup[1])
    r, run, site = await _run_expect_blocked(
        setup, (303, f'http://localhost:{port}/a'),
        {'/a': (302, f'http://127.0.0.1:{port}/b')})
    got = [h for h in site.hits if h[0].startswith('localhost')]
    assert all(h[1] == 'GET' and h[3] == '' for h in got)
    # the first cross-origin 303 GET is the one allowed hop; a following hop must not leave that origin
    assert len(got) <= 1


@pytest.mark.asyncio
async def test_r5_f1_normal_303_receipt_still_works(setup):
    r, run = await ready(setup)
    result = await r.execute('tenant', run['id'], 'owner')
    assert result['state'] == 'succeeded' and len(setup[6].posts) == 1


def _signed(paired, args):
    return protocol.submit_token(paired['command_secret'], approval_id=args['approval_id'],
                                 capture_sha256=args['capture_sha256'], selector=args['selector'],
                                 values_digest=args['values_digest'], deadline=args.get('deadline'))


@pytest.mark.asyncio
async def test_r5_f2_token_covers_deadline_and_replay_survives_restart(setup, tmp_path):
    from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon
    r, run = await ready(setup)
    result = await r.execute('tenant', run['id'], 'owner')
    assert result['state'] == 'succeeded'
    command = [c for c in setup[6].commands if c['kind'] == 'click_submit'][-1]
    args = dict(command['args'])
    assert 'expires_at' in args and 'deadline' not in args  # unified v3 token: signed integer expiry
    # Editing the expiry invalidates the token.
    page, paired = await _compose_with_values(setup)
    for selector, value in args['values'].items():
        await page.fill(selector, value)
    edited = dict(args, expires_at=int(time.time()) + 10_000)
    answer = await setup_daemon(setup).execute(protocol.make_command(protocol.CommandKind.CLICK_SUBMIT, edited))
    assert answer['ok'] is False and 'token' in answer['error'].lower(), answer
    # A restarted daemon process still refuses the consumed token.
    old = setup_daemon(setup)
    fresh = Daemon(old.config, old.identity)
    fresh.browser = old.browser
    answer = await fresh.execute(protocol.make_command(protocol.CommandKind.CLICK_SUBMIT, dict(args)))
    assert answer['ok'] is False and ('replay' in answer['error'].lower() or 'armed too long' in answer['error'].lower() or 'already reserved' in answer['error'].lower()), answer  # unified: durable reservation refuses first
    assert len(setup[6].posts) == 1


@pytest.mark.asyncio
async def test_r5_f2_consumed_cache_is_on_disk(setup):
    r, run = await ready(setup)
    await r.execute('tenant', run['id'], 'owner')
    import json
    from pathlib import Path
    daemon = setup_daemon(setup)
    assert daemon.consumed_path and Path(daemon.consumed_path).is_file()
    assert json.loads(Path(daemon.consumed_path).read_text())


NAV_CAPS = 'click_nav'


async def _nav_click(setup, selector):
    daemon = setup_daemon(setup)
    daemon._capabilities.add(NAV_CAPS)
    return await daemon.execute(protocol.make_command(protocol.CommandKind.CLICK_NAV, {'session': 'experiment', 'selector': selector}))


@pytest.mark.asyncio
@pytest.mark.parametrize('markup', [
    '<button id="x">go</button>',
    '<button id="x" type="submit">go</button>',
    '<input id="x" type="submit" value="go">',
    '<input id="x" type="image" alt="go">',
])
async def test_r5_f3_click_nav_refuses_submit_controls(setup, markup):
    page, paired = await _compose_with_values(setup)
    await page.evaluate("(m) => { document.querySelector('form').insertAdjacentHTML('beforeend', m); }", markup)
    answer = await _nav_click(setup, '#x')
    assert answer['ok'] is False and 'submit' in answer['error'].lower(), answer
    assert setup[6].posts == [] and setup[6].post_paths == []


@pytest.mark.asyncio
async def test_r5_f3_click_nav_refuses_form_attribute_and_label_and_child(setup):
    page, paired = await _compose_with_values(setup)
    await page.evaluate("""() => { document.body.insertAdjacentHTML('beforeend',
      '<button id="ext" form="f2">x</button><form id="f2" method="post" action="/publish"></form>' +
      '<label id="lab" for="inner">l</label><button id="b2" type="button">t</button>');
      document.querySelector('form').insertAdjacentHTML('beforeend', '<button id="wrap"><span id="kid">k</span></button>'); }""")
    for selector in ('#ext', '#kid', '#publish'):
        answer = await _nav_click(setup, selector)
        assert answer['ok'] is False and 'submit' in answer['error'].lower(), (selector, answer)
    assert setup[6].post_paths == []


@pytest.mark.asyncio
async def test_r5_f3_click_nav_still_allows_plain_controls(setup):
    page, paired = await _compose_with_values(setup)
    await page.evaluate("document.body.insertAdjacentHTML('beforeend','<button id=\"plain\" type=\"button\">p</button><a id=\"lnk\" href=\"/idea\">l</a>')")
    assert (await _nav_click(setup, '#plain'))['ok'] is True
    assert (await _nav_click(setup, '#lnk'))['ok'] is True


@pytest.mark.asyncio
async def test_r5_f3_consumed_arming_refuses_next_click_of_the_same_control(setup):
    from app.modules.m13_browser_agent.session_bridge.protocol import BridgeError
    r, run = await ready(setup)
    result = await r.execute('tenant', run['id'], 'owner')
    assert result['state'] == 'succeeded'
    page, paired = await _compose_with_values(setup)
    sessions = r.sessions
    bp = await sessions.page('tenant', f"pc.{paired['device_id']}.experiment")
    before = len(setup[6].post_paths)
    with pytest.raises(BridgeError):
        await bp.locator('#publish').click()
    assert len(setup[6].post_paths) == before


@pytest.mark.asyncio
async def test_r5_f3_server_side_generic_click_refuses_submit_controls():
    from app.modules.m13_browser_agent.service import Service as BrowserService
    from app.modules.m13_browser_agent import forms  # noqa: F401
    from playwright.async_api import async_playwright
    pw = await async_playwright().start(); browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.set_content('<form method="post" action="http://127.0.0.1:9/x"><button id="b">go</button></form><button id="p" type="button">p</button>')
    class S:
        async def page(self, *a): return page
    class St:
        async def append_audit(self, *a): pass
    svc = BrowserService(S(), None, St())
    try:
        with pytest.raises(PermissionError):
            await svc.click('t', 's', '#b')
        assert (await svc.click('t', 's', '#p'))['status'] == 'ok'
    finally:
        await browser.close(); await pw.stop()


@pytest.mark.asyncio
async def test_r5_f4_reissued_post_carries_browser_sec_fetch_headers(setup):
    factory, recipe, approvals, registry, paired, page, site, path = setup
    seen = []
    orig = site.do_POST
    def do_POST(self):
        if self.path == '/publish':
            seen.append({k.lower(): v for k, v in self.headers.items()})
        orig(self)
    site.do_POST = do_POST
    r, run = await ready(setup)
    result = await r.execute('tenant', run['id'], 'owner')
    site.do_POST = orig
    assert result['state'] == 'succeeded' and seen
    h = seen[0]
    assert h.get('sec-fetch-mode') == 'navigate' and h.get('sec-fetch-dest') == 'document', h
    assert h.get('sec-fetch-site') == 'same-origin' and h.get('sec-fetch-user') == '?1', h
    assert h.get('content-type', '').startswith('application/x-www-form-urlencoded')
    assert 'br' in h.get('accept-encoding', '') and h.get('sec-ch-ua'), h
