from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m13_browser_agent.capture_bound_submit import (SubmitAttemptRow, execute_capture_bound_submit,
                                                                request_capture_bound_submit)
from app.modules.m13_browser_agent.service import Service

CAP = "c" * 64
URL = "https://example.com/form"


class Locator:
    def __init__(self, page, sel): self.page, self.sel = page, sel
    async def click(self):
        if self.page.fail_click: raise RuntimeError("detached")
        self.page.clicked.append(self.sel)
    async def input_value(self): return self.page.values[self.sel]


class Page:
    def __init__(self): self.url, self.clicked, self.values, self.fail_click = URL, [], {"#name": "Ada", "#email": "a@b.co"}, False
    def locator(self, sel): return Locator(self, sel)


class Sessions:
    def __init__(self): self.p = Page()
    async def page(self, *a): return self.p


class Store:
    def __init__(self):
        self.events, self.consumed = [], set()
        self.captures = {CAP: SimpleNamespace(session_id="s1", artifact={"destination": URL, "fields": {"#name": "Ada", "#email": "a@b.co"},
                                                                        "dom_sha256": "d" * 64, "screenshot_sha256": "e" * 64, "captured_at": "now"})}
    async def append_audit(self, e): self.events.append(e)
    async def get_capture(self, t, h): return self.captures.get(h) if t == "t" else None
    async def was_consumed(self, a): return a in self.consumed
    async def consume(self, a, t):
        if a in self.consumed: raise PermissionError("approval was already consumed")
        self.consumed.add(a)


class Approvals:
    def __init__(self): self.rows, self.n = {}, 0
    def submit(self, **kw):
        self.n += 1; i = f"a{self.n}"
        self.rows[i] = {"id": i, "payload": kw["payload"], "status": ApprovalStatus.PENDING}; return self.rows[i]
    def get(self, i): return self.rows.get(i)


@pytest.fixture
def env(tmp_path):
    e = create_engine(f"sqlite:///{tmp_path/'m13.db'}"); Base.metadata.create_all(e)
    svc = Service(Sessions(), Approvals(), Store(), str(tmp_path), {"example.com"})
    return svc, sessionmaker(bind=e, expire_on_commit=False)


V = {"#name": "Ada", "#email": "a@b.co"}


@pytest.mark.asyncio
async def test_request_requires_matching_persisted_capture(env):
    svc, _ = env
    with pytest.raises(PermissionError, match="not persisted"):
        await request_capture_bound_submit(svc, "t", "u", "s1", "#go", V, "f" * 64)
    with pytest.raises(PermissionError, match="different browser session"):
        await request_capture_bound_submit(svc, "t", "u", "s2", "#go", V, CAP)
    with pytest.raises(PermissionError, match="differ from the capture"):
        await request_capture_bound_submit(svc, "t", "u", "s1", "#go", {"#name": "Bob"}, CAP)
    svc.sessions.p.url = "https://example.com/other"
    with pytest.raises(PermissionError, match="captured destination"):
        await request_capture_bound_submit(svc, "t", "u", "s1", "#go", V, CAP)


@pytest.mark.asyncio
async def test_execute_is_single_use_and_rechecks_live_page(env):
    svc, sf = env
    req = await request_capture_bound_submit(svc, "t", "u", "s1", "#go", V, CAP)
    a = req["approval_id"]
    with pytest.raises(PermissionError, match="not approved"):
        await execute_capture_bound_submit(svc, sf, "t", "s1", "#go", V, a, CAP)
    svc.approvals.rows[a]["status"] = ApprovalStatus.APPROVED
    svc.sessions.p.values["#email"] = "x@evil.test"
    with pytest.raises(PermissionError, match="changed since"):
        await execute_capture_bound_submit(svc, sf, "t", "s1", "#go", V, a, CAP)
    svc.sessions.p.values["#email"] = "a@b.co"
    with pytest.raises(PermissionError, match="different capture"):
        await execute_capture_bound_submit(svc, sf, "t", "s1", "#go", V, a, "f" * 64)
    out = await execute_capture_bound_submit(svc, sf, "t", "s1", "#go", V, a, CAP)
    assert out["status"] == "submitted" and svc.sessions.p.clicked == ["#go"]
    with pytest.raises(PermissionError, match="already consumed"):
        await execute_capture_bound_submit(svc, sf, "t", "s1", "#go", V, a, CAP)
    req2 = await request_capture_bound_submit(svc, "t", "u", "s1", "#go", V, CAP)
    svc.approvals.rows[req2["approval_id"]]["status"] = ApprovalStatus.APPROVED
    with pytest.raises(PermissionError, match="already exists for this approval or capture"):
        await execute_capture_bound_submit(svc, sf, "t", "s1", "#go", V, req2["approval_id"], CAP)
    assert svc.sessions.p.clicked == ["#go"]


@pytest.mark.asyncio
async def test_failed_click_is_recorded_and_never_replays(env):
    svc, sf = env
    req = await request_capture_bound_submit(svc, "t", "u", "s1", "#go", V, CAP)
    svc.approvals.rows[req["approval_id"]]["status"] = ApprovalStatus.APPROVED
    svc.sessions.p.fail_click = True
    with pytest.raises(RuntimeError, match="capture and approve again"):
        await execute_capture_bound_submit(svc, sf, "t", "s1", "#go", V, req["approval_id"], CAP)
    with sf() as db:
        row = db.scalar(select(SubmitAttemptRow))
        assert row.state == "click_failed" and "detached" in row.error
    svc.sessions.p.fail_click = False
    with pytest.raises(PermissionError):
        await execute_capture_bound_submit(svc, sf, "t", "s1", "#go", V, req["approval_id"], CAP)
    assert svc.sessions.p.clicked == []
