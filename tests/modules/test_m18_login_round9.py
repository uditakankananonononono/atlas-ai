"""Round-9 fixes for the round-8 audit. The auditor's vectors (test_zz_auditor_r8.py, the store file and
cookie_diff_chromium.py) are turned into assertions. Real Chromium and a local fixture site only."""
import asyncio
import json
import time
from pathlib import Path

import pytest

from test_m18_login_browser import setup, _compose_with_values, setup_daemon  # noqa: F401
from test_m18_login_round5 import _nav_click
from test_aud_round7 import SECRET, leaked
from test_zz_auditor_r8 import TWO_DOC, V2, UDP
from test_m18_login_round8 import mk, K, dl
from app.modules.m13_browser_agent.session_bridge.form_guard import parse_set_cookie


async def _drain_udp():
    packets = []
    try:
        while True:
            packets.append(UDP.recvfrom(2000)[0][:12])
    except Exception:  # noqa: BLE001
        pass
    return packets


@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(V2))
async def test_v2_vectors_never_reach_the_server(setup, name):
    page, _ = await _compose_with_values(setup); site = setup[6]
    await page.fill('#draft', SECRET)
    await page.evaluate(V2[name])
    site.hits.clear(); site.posts.clear(); site.post_paths.clear()
    await _drain_udp()
    await _nav_click(setup, '#attack')
    for _ in range(20 if '12s' in name else 14):
        await page.wait_for_timeout(700)
    assert not leaked(site), (name, [h[0][:9] + h[2][:40] for h in site.hits if h[2] != '/compose'][:6])
    assert not site.posts and not site.post_paths, (name, site.posts)
    assert await _drain_udp() == [], 'UDP/ICE packets left the browser'


@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(TWO_DOC))
async def test_second_document_vectors_never_reach_the_server(setup, name):
    page, _ = await _compose_with_values(setup); site = setup[6]
    await page.fill('#draft', SECRET)
    await page.evaluate(f"sessionStorage.setItem('s',{json.dumps(SECRET)}); window.name={json.dumps(SECRET)};document.body.insertAdjacentHTML('beforeend','<a id=attack href=\"/compose\">go</a>')")
    site.html_hook = lambda html, h=TWO_DOC[name]: html.replace('<body>', '<body>' + h)
    site.hits.clear(); site.posts.clear(); site.post_paths.clear()
    try:
        await _nav_click(setup, '#attack')
        for _ in range(14):
            await page.wait_for_timeout(700)
    finally:
        site.html_hook = None
    assert not leaked(site), (name, [h[0][:9] + h[2][:40] for h in site.hits if h[2] != '/compose'][:6])
    assert not site.posts and not site.post_paths


@pytest.mark.asyncio
async def test_owner_tab_in_the_owner_context_cannot_be_reached_by_broadcastchannel(setup):
    """The session page is in its own context; the owner's tab lives in the owner's context."""
    page, _ = await _compose_with_values(setup); site = setup[6]
    daemon = setup_daemon(setup)
    assert daemon.browser.isolated and page.context is not daemon.browser._context
    owner_tab = await daemon.browser._context.new_page()
    await owner_tab.goto(setup[1].origin + '/compose')
    await owner_tab.evaluate("(()=>{window.__bc=new BroadcastChannel('x');__bc.onmessage=e=>fetch('/publish',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:e.data})})()")
    await page.fill('#draft', SECRET)
    await page.evaluate("const bc=new BroadcastChannel('x');" + "document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>');document.querySelector('#attack').addEventListener('click',()=>setTimeout(()=>bc.postMessage('draft=UNAPPROVEDSECRET&run_id=a'),500))")
    site.posts.clear(); site.post_paths.clear()
    await _nav_click(setup, '#attack')
    await page.wait_for_timeout(2500)
    assert not site.posts and not site.post_paths
    await owner_tab.close()


def test_launch_args_contain_the_network_containment_flags():
    from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
    from app.modules.m13_browser_agent.pc_daemon.daemon import BrowserHandle
    args = BrowserHandle(DaemonConfig(browser_args=['--x'])).launch_args()
    assert '--disable-quic' in args and '--force-webrtc-ip-handling-policy=disable_non_proxied_udp' in args and '--x' in args


# ---- store -----------------------------------------------------------------------------------------
def test_store_D_old_record_old_primary_secondary_deleted_is_refused(tmp_path):
    d = mk(tmp_path); snap = Path(d.consumed_path).read_text(); a = d.anchor_paths()[0].read_text()
    assert d._consume_submit(K(1), dl()) is None
    Path(d.consumed_path).write_text(snap); d.anchor_paths()[0].write_text(a); d.anchor_paths()[1].unlink()
    assert mk(tmp_path)._consume_submit(K(1), dl()) is not None


def test_store_either_anchor_missing_for_a_used_record_is_refused(tmp_path):
    for index in (0, 1):
        sub = tmp_path / f'case{index}'; sub.mkdir()
        d = mk(sub); assert d._consume_submit(K(1), dl()) is None
        d.anchor_paths()[index].unlink()
        assert mk(sub)._consume_submit(K(2), dl()) is not None
        assert d._consume_submit(K(3), dl()) is not None


# ---- cookies: Chromium is the oracle ---------------------------------------------------------------
@pytest.mark.asyncio
async def test_cookie_parser_agrees_with_chromium_on_the_auditor_cases():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from playwright.async_api import async_playwright
    from cookie_diff_chromium import CASES, norm

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            i = int(self.path.strip('/')) if self.path.strip('/').isdigit() else None
            self.send_response(200); self.send_header('Content-Type', 'text/html')
            if i is not None:
                self.send_header('Set-Cookie', CASES[i].encode('utf-8', 'surrogateescape').decode('latin-1'))
            self.end_headers(); self.wfile.write(b'ok')
    srv = ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{srv.server_port}'
    diffs = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for i, raw in enumerate(CASES):
            real = await browser.new_context(); p = await real.new_page(); await p.goto(f'{base}/{i}')
            real_cookies = [norm(c) for c in await real.cookies()]; await real.close()
            mine = await browser.new_context()
            parsed = parse_set_cookie(f'{base}/{i}', raw)
            mine_cookies = []
            if isinstance(parsed, dict) and 'set' in parsed:
                try:
                    await mine.add_cookies([parsed['set']]); mine_cookies = [norm(c) for c in await mine.cookies()]
                except Exception as error:  # noqa: BLE001
                    mine_cookies = f'ADDERR {str(error)[:60]}'
            elif parsed is None or isinstance(parsed, dict):
                mine_cookies = []
            await mine.close()
            if real_cookies != mine_cookies:
                diffs.append((raw, real_cookies, mine_cookies))
        await browser.close()
    srv.shutdown()
    assert not diffs, diffs
