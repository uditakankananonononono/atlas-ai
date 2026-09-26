"""End-to-end: the capture-bound single-use submit flow runs over the paired-PC
bridge with the approval binding intact, and the daemon receives a verifiable
submit token for the approved click - and only that click."""
import base64
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m13_browser_agent.capture_bound_submit import (
    execute_capture_bound_submit, request_capture_bound_submit)
from app.modules.m13_browser_agent.security import values_digest
from app.modules.m13_browser_agent.service import Service
from app.modules.m13_browser_agent.session_bridge import protocol
from app.modules.m13_browser_agent.session_bridge.dispatch import BridgedSessions
from app.modules.m13_browser_agent.session_bridge.protocol import CommandKind
from app.modules.m13_browser_agent.session_bridge.registry import BridgeRegistry

CAP = "c" * 64
URL = "https://example.com/form"
V = {"#name": "Ada", "#email": "a@b.co"}


class FakeConnection:
    pacing_seconds = 2.0

    def __init__(self):
        self.commands = []
        self.url = URL
        self.values = dict(V)

    async def execute(self, kind, args, timeout=60.0):
        self.commands.append({"kind": kind, "args": args})
        if kind is CommandKind.READ_VALUES:
            return {"values": {s: self.values.get(s, "") for s in args["selectors"]}, "url": self.url}
        if kind is CommandKind.SCREENSHOT:
            return {"png_base64": base64.b64encode(b"\x89PNG-fake").decode(), "url": self.url}
        if kind is CommandKind.EXTRACT:
            return {"html": "<html>form</html>", "url": self.url}
        return {"url": self.url}


class FakeHub:
    def __init__(self, connection):
        self.connection = connection

    def online(self, device_id):
        return True

    def get(self, device_id):
        return self.connection


class Store:
    def __init__(self, session_id):
        self.events, self.consumed = [], set()
        self.captures = {CAP: SimpleNamespace(
            session_id=session_id,
            artifact={"destination": URL, "fields": dict(V), "dom_sha256": "d" * 64,
                      "screenshot_sha256": "e" * 64, "captured_at": "now"})}

    async def append_audit(self, e):
        self.events.append(e)

    async def get_capture(self, t, h):
        return self.captures.get(h) if t == "t" else None

    async def was_consumed(self, a):
        return a in self.consumed

    async def consume(self, a, t):
        if a in self.consumed:
            raise PermissionError("approval was already consumed")
        self.consumed.add(a)


class Approvals:
    def __init__(self):
        self.rows, self.n = {}, 0

    def submit(self, **kw):
        self.n += 1
        i = f"a{self.n}"
        self.rows[i] = {"id": i, "payload": kw["payload"], "status": ApprovalStatus.PENDING}
        return self.rows[i]

    def get(self, i):
        return self.rows.get(i)


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'m13.db'}")
    Base.metadata.create_all(engine)
    registry = BridgeRegistry(sessionmaker(bind=engine, expire_on_commit=False))
    challenge = registry.create_challenge("t")
    device = registry.confirm_pairing(
        challenge["server_nonce"], challenge["code"], name="laptop",
        public_key="-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n",
        capabilities=["navigate", "extract", "screenshot", "read_values", "fill",
                      "click_nav", "click_submit"])
    connection = FakeConnection()
    sessions = BridgedSessions(registry, FakeHub(connection))
    session_id = protocol.make_pc_session(device["device_id"], "main")
    service = Service(sessions, Approvals(), Store(session_id), str(tmp_path), {"example.com"})
    return service, sessions, device, connection, session_id, sessionmaker(bind=engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_capture_bound_submit_over_bridge(env, tmp_path):
    service, sessions, device, connection, SESSION_ID, sf = env

    page = await sessions.page("t", SESSION_ID)
    await page.goto(URL)  # the paired browser is already on the form
    staged = await request_capture_bound_submit(service, "t", "u", SESSION_ID, "#go", V, CAP)
    assert staged["status"] == "awaiting_approval"
    service.approvals.rows[staged["approval_id"]]["status"] = ApprovalStatus.APPROVED

    result = await execute_capture_bound_submit(service, sf, "t", SESSION_ID, "#go", V,
                                                staged["approval_id"], CAP)
    assert result["status"] == "submitted"

    submit_commands = [c for c in connection.commands if c["kind"] is CommandKind.CLICK_SUBMIT]
    assert len(submit_commands) == 1
    token = submit_commands[0]["args"]["token"]
    assert protocol.verify_submit_token(
        device["command_secret"], approval_id=staged["approval_id"], capture_sha256=CAP,
        selector="#go", values_digest=values_digest(V), token=token)

    # Replay is impossible: the approval was consumed.
    with pytest.raises(PermissionError, match="consumed|not approved"):
        await execute_capture_bound_submit(service, sf, "t", SESSION_ID, "#go", V,
                                           staged["approval_id"], CAP)
    assert len([c for c in connection.commands if c["kind"] is CommandKind.CLICK_SUBMIT]) == 1
