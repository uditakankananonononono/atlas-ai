"""Dispatch tests: BridgedSessions over a scripted in-process daemon transport."""
import base64

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m13_browser_agent.session_bridge import protocol
from app.modules.m13_browser_agent.session_bridge.dispatch import (
    BridgedSessions, DeviceOffline, HybridSessions)
from app.modules.m13_browser_agent.session_bridge.protocol import (
    BlockKind, BridgeError, CommandKind, PlatformBlocked)
from app.modules.m13_browser_agent.session_bridge.registry import BridgeRegistry


class FakeConnection:
    """Stands in for a daemon websocket: records commands, answers from a script."""

    def __init__(self):
        self.commands = []
        self.state = {"url": "about:blank", "values": {"#name": "Ada"}}
        self.pacing_seconds = 2.0

    async def execute(self, kind, args, timeout=60.0):
        self.commands.append({"kind": kind, "args": args})
        if kind is CommandKind.NAVIGATE:
            self.state["url"] = args["url"]
            return {"url": args["url"], "http_status": 200}
        if kind is CommandKind.EXTRACT:
            return {"html": "<html>mirror</html>", "url": self.state["url"]}
        if kind is CommandKind.READ_VALUES:
            return {"values": {s: self.state["values"].get(s, "") for s in args["selectors"]},
                    "url": self.state["url"]}
        if kind is CommandKind.SCREENSHOT:
            return {"png_base64": base64.b64encode(b"\x89PNG-fake").decode(), "url": self.state["url"]}
        if kind is CommandKind.FILL:
            self.state["values"][args["selector"]] = args["value"]
            return {"url": self.state["url"]}
        if kind in (CommandKind.CLICK_NAV, CommandKind.CLICK_SUBMIT):
            return {"url": self.state["url"]}
        if kind is CommandKind.CLOSE:
            return {"closed": True}
        return {}


class FakeHub:
    def __init__(self, connection=None):
        self.connection = connection or FakeConnection()

    def online(self, device_id):
        return self.connection is not None

    def get(self, device_id):
        return self.connection


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'bridge.db'}")
    Base.metadata.create_all(engine)
    registry = BridgeRegistry(sessionmaker(bind=engine, expire_on_commit=False))
    challenge = registry.create_challenge("t")
    device = registry.confirm_pairing(
        challenge["server_nonce"], challenge["code"], name="laptop",
        public_key="-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n",
        capabilities=["navigate", "extract", "screenshot", "read_values", "fill",
                      "click_nav", "click_submit", "close"])
    hub = FakeHub()
    sessions = BridgedSessions(registry, hub)
    session_id = protocol.make_pc_session(device["device_id"], "main")
    return sessions, hub, device, session_id


@pytest.mark.asyncio
async def test_page_ops_roundtrip_through_transport(env):
    sessions, hub, device, session_id = env
    page = await sessions.page("t", session_id)
    response = await page.goto("https://example.com/form")
    assert response.status == 200
    assert page.url == "https://example.com/form"
    assert await page.content() == "<html>mirror</html>"
    assert await page.locator("#name").input_value() == "Ada"
    await page.locator("#name").fill("Grace")
    assert hub.connection.state["values"]["#name"] == "Grace"


@pytest.mark.asyncio
async def test_screenshot_writes_bytes_to_path(env, tmp_path):
    sessions, hub, device, session_id = env
    page = await sessions.page("t", session_id)
    target = tmp_path / "shot.png"
    await page.screenshot(path=str(target), full_page=True,
                          mask=[page.locator("#secret")])
    assert target.read_bytes() == b"\x89PNG-fake"
    shot = hub.connection.commands[-1]
    assert shot["kind"] is CommandKind.SCREENSHOT
    assert shot["args"]["mask"] == ["#secret"]


@pytest.mark.asyncio
async def test_click_defaults_to_nav_and_armed_click_becomes_submit(env):
    sessions, hub, device, session_id = env
    page = await sessions.page("t", session_id)
    await page.locator("#open-dialog").click()
    assert hub.connection.commands[-1]["kind"] is CommandKind.CLICK_NAV
    assert "token" not in hub.connection.commands[-1]["args"]

    values = {"#name": "Ada"}
    await sessions.authorize_submit("t", session_id, approval_id="a1",
                                    capture_sha256="c" * 64, selector="#go", values=values)
    await page.locator("#go").click()
    command = hub.connection.commands[-1]
    assert command["kind"] is CommandKind.CLICK_SUBMIT
    from app.modules.m13_browser_agent.security import values_digest
    assert protocol.verify_submit_token(
        device["command_secret"], approval_id="a1", capture_sha256="c" * 64,
        selector="#go", values_digest=values_digest(values), token=command["args"]["token"])

    # The armed token is one-shot: the next click is a nav click again.
    await page.locator("#go").click()
    assert hub.connection.commands[-1]["kind"] is CommandKind.CLICK_NAV


@pytest.mark.asyncio
async def test_offline_and_ungranted_devices_fail_closed(tmp_path, env):
    sessions, hub, device, session_id = env
    hub.connection = None
    with pytest.raises(DeviceOffline):
        await sessions.page("t", session_id)

    engine = create_engine(f"sqlite:///{tmp_path/'bridge2.db'}")
    Base.metadata.create_all(engine)
    registry = BridgeRegistry(sessionmaker(bind=engine, expire_on_commit=False))
    challenge = registry.create_challenge("t")
    limited = registry.confirm_pairing(
        challenge["server_nonce"], challenge["code"], name="reader-only",
        public_key="-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n",
        capabilities=["extract"])
    restricted = BridgedSessions(registry, FakeHub())
    read_session = protocol.make_pc_session(limited["device_id"], "main")
    page = await restricted.page("t", read_session)
    with pytest.raises(BridgeError, match="not granted"):
        await page.locator("#go").click()


@pytest.mark.asyncio
async def test_hybrid_sessions_route_by_prefix(env):
    sessions, hub, device, session_id = env

    class ServerBackend:
        async def page(self, tenant_id, sid, persistent=False):
            return f"server-page:{sid}"

    hybrid = HybridSessions(ServerBackend(), sessions)
    assert await hybrid.page("t", "plain-session") == "server-page:plain-session"
    bridged = await hybrid.page("t", session_id)
    await bridged.goto("https://example.com")
    assert bridged.url == "https://example.com"
    # The read-adapter surface works for the bridged backend (pre_submit_capture path).
    assert await hybrid.extract("t", session_id) == "<html>mirror</html>"
    assert await hybrid.read_values("t", session_id, ["#name"]) == {"#name": "Ada"}
