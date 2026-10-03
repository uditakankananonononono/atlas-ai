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

STATUS_PAGES = {"/ok-q": 200, "/bare403": 403, "/bare503": 503, "/bare429": 429, "/ok": 200, "/ok-accepted-jobs": 200}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        # M18 only approves POST forms; the POST lands on the same status pages as the GET fixtures.
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/start/"):
            target = "/" + path[len("/start/"):]
            body = (f'<html><body><a id="go" href="{target}">go</a>'
                    f'<form method="post" action="{target}"><button id="sub">s</button></form></body></html>')
            status = 200
        elif path.startswith("/delayed/"):
            target = "/" + path[len("/delayed/"):]
            body = (f'<html><body><button id="sub" onclick="setTimeout(()=>{{location.href=\'{target}?token=SECRETQ\'}},400)">s'
                    '</button></body></html>')
            status = 200
        elif path.startswith("/late/"):
            target = "/" + path[len("/late/"):]
            body = (f'<html><body><button id="sub" onclick="setTimeout(()=>{{location.href=\'{target}\'}},1600)">s'
                    '</button></body></html>')
            status = 200
        elif path == "/secrets":
            body = ('<html><body><input id="plain" value="ok1">'
                    '<input id="otp" name="otp_code" value="123456">'
                    '<input id="masked" style="-webkit-text-security:disc" value="maskedsecret">'
                    '<textarea id="cvv" name="card_cvv">987</textarea>'
                    '<textarea id="note">fine</textarea></body></html>')
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
                          consumed_path=str(tmp_path / "consumed.json"),
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


class _PageSessions:
    """Adapts the daemon's real page to what the server-side preview builder reads (extract, form_facts)."""

    def __init__(self, page):
        self.page = page

    async def extract(self, tenant_id, session_id):
        return await self.page.content()

    async def form_facts(self, tenant_id, session_id, selector):
        from app.modules.m13_browser_agent.session_bridge import form_guard
        return await self.page.evaluate(form_guard.FORM_FACTS_JS, selector)


async def _submit_args(daemon, approval, selector="#sub"):
    """Args for a REAL preview-bound CLICK_SUBMIT: the reviewed preview is built from the live page by the
    same builder the server uses, the token binds its digest, device, session, action and expiry."""
    from app.modules.m13_browser_agent.security import values_digest
    from app.modules.m13_browser_agent.submit_binding import build_binding_preview, preview_digest
    page = await daemon.browser.page("s")
    preview = await build_binding_preview(_PageSessions(page), "t", "s", selector, {})
    capture = preview_digest(preview)
    digest = values_digest({})
    token = protocol.submit_token("topsecret", approval_id=approval, capture_sha256=capture,
                                  selector=selector, values_digest=digest, device_id="dev1",
                                  session="s", expires_at=2000000000)
    return {"session": "s", "selector": selector, "approval_id": approval, "capture_sha256": capture,
            "values_digest": digest, "token": token, "expires_at": 2000000000,
            "preview": preview, "values": {}, "readback_selectors": {}}


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
    args = await _submit_args(daemon, f"ap{path}")  # built once, from the page before the click
    answer = await daemon.execute(protocol.make_command(CommandKind.CLICK_SUBMIT, args, command_id=_id()))
    assert answer["ok"] is False and answer["blocked"] == kind
    assert "effect may have occurred" in answer["error"] and "do not retry" in answer["error"]
    assert answer["effect_uncertain"] is True
    # the reservation stays: a second click with the same approval must not reach the browser
    again = await daemon.execute(protocol.make_command(CommandKind.CLICK_SUBMIT, args, command_id=_id()))
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


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [CommandKind.CLICK_NAV, CommandKind.CLICK_SUBMIT])
async def test_delayed_js_navigation_to_403_is_blocked(daemon, server, kind):
    answer = await daemon.execute(protocol.make_command(
        CommandKind.NAVIGATE, {"session": "s", "url": f"{server}/delayed/bare403"}, command_id=_id()))
    assert answer["ok"] is True
    args = await _submit_args(daemon, "ap-delayed") if kind is CommandKind.CLICK_SUBMIT else {"session": "s", "selector": "#sub"}
    answer = await daemon.execute(protocol.make_command(kind, args, command_id=_id()))
    assert answer["ok"] is False and answer["blocked"] == "policy", answer
    if kind is CommandKind.CLICK_SUBMIT:
        assert "effect may have occurred" in answer["error"]
        again = await daemon.execute(protocol.make_command(kind, await _submit_args(daemon, "ap-delayed"), command_id=_id()))
        assert "already reserved" in again["error"]


@pytest.mark.asyncio
async def test_click_reports_bounded_observation_window(daemon, server):
    await _arrive(daemon, server, "/ok")
    answer = await daemon.execute(protocol.make_command(
        CommandKind.CLICK_NAV, {"session": "s", "selector": "#go"}, command_id=_id()))
    obs = answer["result"]["post_click_observation"]
    assert obs["bounded"] is True and obs["window_seconds"] > 0
    assert obs["note"].startswith("later navigations after this window are not observed")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [CommandKind.CLICK_NAV, CommandKind.CLICK_SUBMIT])
async def test_landing_url_query_and_fragment_never_leave_the_pc(daemon, server, kind):
    answer = await daemon.execute(protocol.make_command(
        CommandKind.NAVIGATE, {"session": "s", "url": f"{server}/delayed/bare403"}, command_id=_id()))
    args = await _submit_args(daemon, "ap-q") if kind is CommandKind.CLICK_SUBMIT else {"session": "s", "selector": "#sub"}
    answer = await daemon.execute(protocol.make_command(kind, args, command_id=_id()))
    assert answer["ok"] is False
    assert "SECRETQ" not in str(answer) and "token=" not in str(answer)
    assert "/bare403" in answer["receipt"]["payload"]["url"] if "payload" in answer["receipt"] else True


@pytest.mark.asyncio
@pytest.mark.parametrize("selector", ["#otp", "#masked", "#cvv"])
async def test_read_values_refuses_unmarked_secret_looking_fields(daemon, server, selector):
    answer = await daemon.execute(protocol.make_command(
        CommandKind.NAVIGATE, {"session": "s", "url": f"{server}/secrets"}, command_id=_id()))
    assert answer["ok"] is True
    daemon._capabilities.add("read_values")
    answer = await daemon.execute(protocol.make_command(
        CommandKind.READ_VALUES, {"session": "s", "selectors": [selector]}, command_id=_id()))
    assert answer["ok"] is False
    assert not any(v in str(answer) for v in ("123456", "maskedsecret", "987"))
    ok = await daemon.execute(protocol.make_command(
        CommandKind.READ_VALUES, {"session": "s", "selectors": ["#plain", "#note"]}, command_id=_id()))
    assert ok["ok"] is True and ok["result"]["values"] == {"#plain": "ok1", "#note": "fine"}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [CommandKind.CLICK_NAV, CommandKind.CLICK_SUBMIT])
@pytest.mark.parametrize("query", ["next=/login", "challenge=1"])
async def test_url_markers_in_query_are_classified_but_not_returned(daemon, server, kind, query):
    STATUS_PAGES["/ok-q"] = 200
    args = await _submit_args(daemon, "ap-qm") if kind is CommandKind.CLICK_SUBMIT else {"session": "s", "selector": "#go"}
    page = await daemon.browser.page("s")
    await page.goto(f"{server}/ok-q?{query}")
    await page.set_content(f'<a id="go" href="{server}/ok-q?{query}">go</a><button id="sub" onclick="location.href=\'{server}/ok-q?{query}\'">s</button>')
    args["selector"] = "#go" if kind is CommandKind.CLICK_NAV else "#sub"
    answer = await daemon.execute(protocol.make_command(kind, args, command_id=_id()))
    assert answer["ok"] is False and answer["blocked"] in ("login_wall", "challenge"), answer
    assert "next=" not in str(answer) and "challenge=1" not in str(answer)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [CommandKind.CLICK_NAV, CommandKind.CLICK_SUBMIT])
async def test_late_navigation_beyond_window_is_never_reported_as_accepted(daemon, server, kind):
    answer = await daemon.execute(protocol.make_command(
        CommandKind.NAVIGATE, {"session": "s", "url": f"{server}/late/bare403"}, command_id=_id()))
    args = await _submit_args(daemon, "ap-late") if kind is CommandKind.CLICK_SUBMIT else {"session": "s", "selector": "#sub"}
    answer = await daemon.execute(protocol.make_command(kind, args, command_id=_id()))
    # the window cannot see a 1.6s-late navigation: ok is allowed, acceptance is not claimed
    assert answer["ok"] is True
    assert answer["result"]["site_acceptance"] == "unconfirmed"
    assert answer["receipt"]["payload"]["site_acceptance"] == "unconfirmed"
    if kind is CommandKind.CLICK_SUBMIT:
        import sqlite3
        db = sqlite3.connect(daemon.effects.path)
        state = db.execute("SELECT state FROM submit_effects WHERE approval_id='ap-late'").fetchone()[0]
        assert state == "click_observed_unconfirmed"


@pytest.mark.asyncio
async def test_effect_uncertain_flag_only_where_a_click_may_have_happened(daemon, server):
    await _arrive(daemon, server, "/ok")
    bad = await _submit_args(daemon, "ap-flag")
    bad["token"] = "wrong"
    answer = await daemon.execute(protocol.make_command(CommandKind.CLICK_SUBMIT, bad, command_id=_id()))
    assert answer["ok"] is False and answer["effect_uncertain"] is False  # explicit: refused before any click
    good = await _submit_args(daemon, "ap-flag2")
    first = await daemon.execute(protocol.make_command(CommandKind.CLICK_SUBMIT, good, command_id=_id()))
    assert first["ok"] is True
    again = await daemon.execute(protocol.make_command(CommandKind.CLICK_SUBMIT, good, command_id=_id()))
    assert again["ok"] is False and again["effect_uncertain"] is True  # already reserved: outcome unknown
