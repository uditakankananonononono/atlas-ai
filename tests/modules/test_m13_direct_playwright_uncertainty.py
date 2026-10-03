"""Direct (non-bridge) Playwright click whose response is slow: the form may already be received.

Real Chromium + local server that counts hits and answers late. Local fixture only.
"""
import asyncio
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m13_browser_agent.capture_bound_submit import (
    SubmitAttemptRow, execute_capture_bound_submit, request_capture_bound_submit)
from app.modules.m13_browser_agent.service import Service

CAP = "c" * 64
URL = "https://example.com/form"
HITS = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/received"):
            HITS.append(self.path)
            time.sleep(3)
            body = b"<html>received</html>"
        else:
            body = (b'<html><body><form method="get" action="/received"><input id="name" name="name" value="Ada">'
                    b'<input id="email" name="email" value="a@b.co"><button id="go">go</button></form></body></html>')
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class RealPage:
    """Real Playwright page; reports the approved public URL so the capture checks pass."""
    url = URL

    def __init__(self, page):
        self._page = page

    def locator(self, selector):
        return self._page.locator(selector)

    def __getattr__(self, name):  # content(), evaluate(), ... on the real page
        return getattr(self._page, name)


class Sessions:
    def __init__(self, page): self.p = page
    async def page(self, *a): return self.p


class Store:
    def __init__(self):
        self.events, self.consumed = [], set()
        self.captures = {CAP: SimpleNamespace(session_id="s1", artifact={
            "destination": URL, "fields": {"#name": "Ada", "#email": "a@b.co"},
            "dom_sha256": "d" * 64, "screenshot_sha256": "e" * 64, "captured_at": "now"})}
    async def append_audit(self, e): self.events.append(e)
    async def get_capture(self, t, h): return self.captures.get(h) if t == "t" else None
    async def was_consumed(self, a): return a in self.consumed
    async def consume(self, a, t): self.consumed.add(a)


class Approvals:
    def __init__(self): self.rows, self.n = {}, 0
    def submit(self, **kw):
        self.n += 1; i = f"a{self.n}"
        self.rows[i] = {"id": i, "payload": kw["payload"], "status": ApprovalStatus.PENDING}; return self.rows[i]
    def get(self, i): return self.rows.get(i)


@pytest.fixture(autouse=True)
def _allow_unguarded_server_submit_fixture(monkeypatch):
    # TEST FIXTURE: the shipped default REFUSES approved submits on server-side sessions (no click-time
    # guard). This file only proves uncertainty bookkeeping for a slow response on a real page; the
    # refusal itself is covered by test_m13_server_side_refusal.py. Not a real-path claim.
    monkeypatch.setattr(Service, "allow_unguarded_server_submit", True, raising=False)


@pytest.mark.asyncio
async def test_direct_playwright_click_timeout_after_server_received_is_uncertain(tmp_path):
    HITS.clear()
    site = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=site.serve_forever, daemon=True).start()
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        page.set_default_timeout(700)
        await page.goto(f"http://127.0.0.1:{site.server_address[1]}/form")
        engine = create_engine(f"sqlite:///{tmp_path/'m13.db'}"); Base.metadata.create_all(engine)
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        svc = Service(Sessions(RealPage(page)), Approvals(), Store(), str(tmp_path), {"example.com"})
        V = {"#name": "Ada", "#email": "a@b.co"}
        import hashlib  # the capture's DOM hash is now really compared with the live page
        svc.store.captures[CAP].artifact["dom_sha256"] = hashlib.sha256((await page.content()).encode()).hexdigest()
        req = await request_capture_bound_submit(svc, "t", "u", "s1", "#go", V, CAP)
        a = req["approval_id"]
        svc.approvals.rows[a]["status"] = ApprovalStatus.APPROVED
        with pytest.raises(Exception) as caught:
            await execute_capture_bound_submit(svc, sf, "t", "s1", "#go", V, a, CAP)
        await asyncio.sleep(0.2)
        assert len(HITS) == 1, (HITS, repr(caught.value))  # the server did receive the submit
        assert "approve again" not in str(caught.value)
        assert "outcome unknown" in str(caught.value) and "do not retry" in str(caught.value)
        with sf() as db:
            row = db.scalar(select(SubmitAttemptRow).where(SubmitAttemptRow.approval_id == a))
        assert row.state == "click_uncertain"
        await browser.close()
    site.shutdown()


@pytest.mark.asyncio
async def test_cancellation_after_dispatch_leaves_durable_uncertainty(tmp_path):
    """A cancelled request after the click began must not leave a consumed approval with no outcome."""
    import tests.modules.test_m13_capture_bound_submit as base
    engine = create_engine(f"sqlite:///{tmp_path/'m13.db'}"); Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False)
    svc = Service(base.Sessions(), base.Approvals(), base.Store(), str(tmp_path), {"example.com"})
    started = asyncio.Event()

    async def hanging_click(self):
        started.set()
        await asyncio.sleep(30)
    base.Locator.click, original = hanging_click, base.Locator.click
    try:
        req = await request_capture_bound_submit(svc, "t", "u", "s1", "#go", base.V, base.CAP)
        a = req["approval_id"]
        svc.approvals.rows[a]["status"] = ApprovalStatus.APPROVED
        task = asyncio.create_task(execute_capture_bound_submit(svc, sf, "t", "s1", "#go", base.V, a, base.CAP))
        await asyncio.wait_for(started.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        base.Locator.click = original
    assert a in svc.store.consumed
    with sf() as db:
        row = db.scalar(select(SubmitAttemptRow).where(SubmitAttemptRow.approval_id == a))
    assert row.state == "click_uncertain" and row.finished_at is not None


@pytest.mark.asyncio
async def test_capture_bound_attempt_row_exists_before_consume_and_is_not_a_success_or_failure(tmp_path):
    import tests.modules.test_m13_capture_bound_submit as base
    engine = create_engine(f"sqlite:///{tmp_path/'m13.db'}"); Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False)
    svc = Service(base.Sessions(), base.Approvals(), base.Store(), str(tmp_path), {"example.com"})
    req = await request_capture_bound_submit(svc, "t", "u", "s1", "#go", base.V, base.CAP)
    a = req["approval_id"]
    svc.approvals.rows[a]["status"] = ApprovalStatus.APPROVED

    async def die(approval_id, tenant):
        raise asyncio.CancelledError()
    svc.store.consume = die
    with pytest.raises(asyncio.CancelledError):
        await execute_capture_bound_submit(svc, sf, "t", "s1", "#go", base.V, a, base.CAP)
    with sf() as db:
        row = db.scalar(select(SubmitAttemptRow).where(SubmitAttemptRow.approval_id == a))
    assert row.state == "clicking" and row.finished_at is None  # attempt started, outcome unconfirmed
    assert svc.sessions.p.clicked == []
