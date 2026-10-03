"""Post-click HTTP status must classify like NAVIGATE, on real Chromium against a local server.

Local fixtures prove classification logic only; they are not evidence of real-site behavior.
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import pytest_asyncio

from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import BrowserHandle, Daemon, DeviceIdentity
from app.modules.m13_browser_agent.session_bridge import protocol
from app.modules.m13_browser_agent.session_bridge.protocol import CommandKind

STATUS_PAGES = {"/bare403": 403, "/bare503": 503, "/bare429": 429, "/ok": 200, "/ok-accepted-jobs": 200}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/start/"):
            target = "/" + path[len("/start/"):]
            body = (f'<html><body><a id="go" href="{target}">go</a>'
                    f'<form method="get" action="{target}"><button id="sub">s</button></form></body></html>')
            status = 200
        elif path == "/nonav":
            body = '<html><body><button id="js" onclick="document.title=\'x\'">x</button></body></html>'
            status = 200
        elif path in STATUS_PAGES:
            status = STATUS_PAGES[path]
            body = "<html><body>Thanks, request received</body></html>" if status == 200 else "<html><body>nope</body></html>"
        else:
            status, body = 404, "<html><body>missing</body></html>"
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


class HeadlessHandle(BrowserHandle):
    async def start(self):
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        self._context = await self._browser.new_context()

    async def stop(self):
        await self._context.close()
        await self._browser.close()
        await self._playwright.stop()


@pytest_asyncio.fixture
async def daemon(tmp_path):
    config = DaemonConfig(server_url="https://atlas.test", device_id="dev1", command_secret="topsecret",
                          key_path=str(tmp_path / "key.pem"), pacing_seconds=0,
                          capabilities=["navigate", "click_nav", "click_submit"])
    instance = Daemon(config, DeviceIdentity.load_or_create(tmp_path / "key.pem"))
    instance.browser = HeadlessHandle(config)
    await instance.browser.start()
    yield instance
    await instance.browser.stop()


_n = 0


def _id():
    global _n
    _n += 1
    return f"cmd-{_n}"


async def _arrive(daemon, server, target):
    answer = await daemon.execute(protocol.make_command(
        CommandKind.NAVIGATE, {"session": "s", "url": f"{server}/start{target}"}, command_id=_id()))
    assert answer["ok"] is True, answer


def _submit_args(approval, selector="#sub"):
    token = protocol.submit_token("topsecret", approval_id=approval, capture_sha256="c" * 64,
                                  selector=selector, values_digest="d" * 64, device_id="dev1",
                                  session="s", expires_at=2000000000)
    return {"session": "s", "selector": selector, "approval_id": approval, "capture_sha256": "c" * 64,
            "values_digest": "d" * 64, "token": token, "expires_at": 2000000000}


@pytest.mark.asyncio
@pytest.mark.parametrize("path,kind", [("/bare403", "policy"), ("/bare503", "policy"), ("/bare429", "rate_limit")])
async def test_click_nav_landing_on_error_status_is_blocked(daemon, server, path, kind):
    await _arrive(daemon, server, path)
    answer = await daemon.execute(protocol.make_command(
        CommandKind.CLICK_NAV, {"session": "s", "selector": "#go"}, command_id=_id()))
    assert answer["ok"] is False and answer["blocked"] == kind
    assert answer["receipt"]["phase"] == "blocked"


@pytest.mark.asyncio
@pytest.mark.parametrize("path,kind", [("/bare403", "policy"), ("/bare503", "policy"), ("/bare429", "rate_limit")])
async def test_click_submit_landing_on_error_status_is_blocked_and_uncertain(daemon, server, path, kind):
    await _arrive(daemon, server, path)
    answer = await daemon.execute(protocol.make_command(
        CommandKind.CLICK_SUBMIT, _submit_args(f"ap{path}"), command_id=_id()))
    assert answer["ok"] is False and answer["blocked"] == kind
    assert "effect may have occurred" in answer["error"] and "do not retry" in answer["error"]
    # the reservation stays: a second click with the same approval must not reach the browser
    again = await daemon.execute(protocol.make_command(
        CommandKind.CLICK_SUBMIT, _submit_args(f"ap{path}"), command_id=_id()))
    assert again["ok"] is False and "already reserved" in again["error"]


@pytest.mark.asyncio
async def test_click_to_ok_page_stays_ok_and_reports_status_without_page_content(daemon, server):
    await _arrive(daemon, server, "/ok")
    answer = await daemon.execute(protocol.make_command(
        CommandKind.CLICK_NAV, {"session": "s", "selector": "#go"}, command_id=_id()))
    assert answer["ok"] is True and answer.get("blocked") is None
    assert answer["result"]["http_status"] == 200
    assert "html_excerpt" not in answer["result"]
    assert "Thanks" not in str(answer)


@pytest.mark.asyncio
async def test_click_without_navigation_has_no_status_and_is_ok(daemon, server):
    answer = await daemon.execute(protocol.make_command(
        CommandKind.NAVIGATE, {"session": "s", "url": f"{server}/nonav"}, command_id=_id()))
    assert answer["ok"] is True
    answer = await daemon.execute(protocol.make_command(
        CommandKind.CLICK_NAV, {"session": "s", "selector": "#js"}, command_id=_id()))
    assert answer["ok"] is True
    assert answer["result"].get("http_status") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/bare403", "/bare503"])
async def test_navigate_bare_error_status_is_blocked(daemon, server, path):
    answer = await daemon.execute(protocol.make_command(
        CommandKind.NAVIGATE, {"session": "s", "url": f"{server}{path}"}, command_id=_id()))
    assert answer["ok"] is False and answer["blocked"] == "policy"
