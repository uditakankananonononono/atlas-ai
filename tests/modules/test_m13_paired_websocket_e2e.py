"""Real WebSocket + real headless Chromium + local fixture site, in one event loop.

Local fixture only: this proves the paired transport path on this machine, not any real site.
"""
import asyncio
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import pytest_asyncio
import uvicorn
from fastapi import FastAPI

from app.core.database import Base, engine
from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import (
    BrowserHandle, Daemon, DeviceIdentity, pair_with_server)
from app.modules.m13_browser_agent.session_bridge import dispatch, routes

FORM = """<html><body><form method="post" action="/thanks">
<input id="name" name="name" value=""><input id="email" name="email" value=""><input id="pw" type="password" value="hunter2-canary">
<button id="send">Send</button></form></body></html>"""


FORM_SUBMIT = """<html><body><form method="post" action="/thanks">
<input id="name" name="name" value=""><input id="email" name="email" value=""><button id="send">Send</button></form></body></html>"""


class _Site(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?")[0]
        body = FORM if path == "/form" else FORM_SUBMIT if path == "/form-submit" else "<html><body>Thanks, received</body></html>"
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


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


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def paired(tmp_path):
    Base.metadata.create_all(engine)
    site = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=site.serve_forever, daemon=True).start()
    site_url = f"http://127.0.0.1:{site.server_address[1]}"
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    server_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    server_url = f"http://127.0.0.1:{port}"
    registry = routes.get_registry()
    challenge = registry.create_challenge("tenant-e2e")
    caps = ["navigate", "extract", "screenshot", "read_values", "fill", "click_nav", "click_submit", "close"]
    config = await asyncio.to_thread(
        pair_with_server, server_url, challenge["server_nonce"], challenge["code"], name="e2e-pc",
        capabilities=caps, pacing_seconds=dispatch.protocol.MIN_PACING_SECONDS, key_path=tmp_path / "key.pem", config_path=tmp_path / "cfg.json")
    config.pacing_seconds = 0
    config.consumed_path = str(tmp_path / "consumed.json")  # isolated store, never the real ~/.atlas-pc
    daemon = Daemon(config, DeviceIdentity.load_or_create(tmp_path / "key.pem"))
    daemon.browser = HeadlessHandle(config)
    daemon_task = asyncio.create_task(daemon.run())
    for _ in range(100):
        if dispatch.HUB.online(config.device_id):
            break
        await asyncio.sleep(0.1)
    assert dispatch.HUB.online(config.device_id)
    sessions = dispatch.BridgedSessions(registry)
    yield sessions, config, site_url
    daemon_task.cancel()
    server.should_exit = True
    await server_task
    site.shutdown()


@pytest.mark.asyncio
async def test_end_to_end_over_real_websocket(paired):
    sessions, config, site = paired
    sid = f"{dispatch.protocol.PC_SESSION_PREFIX}{config.device_id}.main"
    page = await sessions.page("tenant-e2e", sid)
    await page.goto(f"{site}/form-submit")
    await page.locator("#name").fill("Udita Phookan")
    assert await page.locator("#name").input_value() == "Udita Phookan"
    html = await sessions.extract("tenant-e2e", sid)
    assert 'id="name"' in html
    shot = await sessions.screenshot("tenant-e2e", sid)
    assert open(shot, "rb").read(4) == b"\x89PNG"
    await page.locator("#email").fill("udita@example.test")
    values = await sessions.read_values("tenant-e2e", sid, ["#name", "#email"])
    assert values == {"#name": "Udita Phookan", "#email": "udita@example.test"}
    # REAL preview-bound path: the reviewed preview is built from the live paired page over the websocket.
    from app.modules.m13_browser_agent.submit_binding import build_binding_preview, preview_digest
    preview = await build_binding_preview(sessions, "tenant-e2e", sid, "#send", values)
    await sessions.authorize_submit("tenant-e2e", sid, approval_id="ap-e2e", capture_sha256=preview_digest(preview),
                                    selector="#send", values=values, preview=preview)
    await page.locator("#send").click()
    assert "thanks" in (await sessions.page("tenant-e2e", sid)).url
    obs = page.last_click_observation
    assert obs["site_acceptance"] == "unconfirmed" and obs["http_status"] == 200
    assert obs["post_click_observation"]["bounded"] is True


@pytest.mark.asyncio
async def test_credential_field_values_are_never_returned(paired):
    sessions, config, site = paired
    sid = f"{dispatch.protocol.PC_SESSION_PREFIX}{config.device_id}.main"
    page = await sessions.page("tenant-e2e", sid)
    await page.goto(f"{site}/form")
    with pytest.raises(Exception) as caught:
        await sessions.read_values("tenant-e2e", sid, ["#pw"])
    assert "hunter2-canary" not in str(caught.value)
    # a normal field in the same page still reads fine
    await page.locator("#name").fill("Ada")
    assert await sessions.read_values("tenant-e2e", sid, ["#name"]) == {"#name": "Ada"}
