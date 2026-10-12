"""Regression tests for ATLAS-m13.A01/A03/A05, m15.A03, m16.A01/A02 (written from the audit repro probes)."""
import asyncio, os, pathlib, tempfile
import pytest
from app.core.models import ApprovalStatus
from app.modules.m13_browser_agent.service import Service as BrowserService
from app.modules.m13_browser_agent.vlm_loop import NavigationLoop
from app.modules.m13_browser_agent.domain import ActionType
from tests.modules.test_m13_browser_agent import Approvals, Sessions, Store


class OneClick:
    def __init__(self, selector, **extra):
        self.n, self.selector, self.extra = 0, selector, extra

    async def next_action(self, instruction, shot, history):
        self.n += 1
        return {"type": "click", "selector": self.selector, **self.extra} if self.n == 1 else {"type": "done"}


@pytest.mark.asyncio
async def test_m13_a01_unmarked_submit_click_needs_approval(tmp_path):
    sessions, approvals, store = Sessions(), Approvals(), Store()
    svc = BrowserService(sessions, approvals, store, str(tmp_path), {"example.com"})
    result = await NavigationLoop(svc, OneClick("#pay-now")).run("t", "r", "buy")
    assert result["status"] == "awaiting_approval"
    assert sessions.p.clicked == []


def _with_probe(sessions, info=None, exc=None):
    loc = sessions.p.locator

    class L:
        def __init__(self, inner): self.inner = inner
        def __getattr__(self, n): return getattr(self.inner, n)
        async def evaluate(self, js):
            if exc: raise exc
            return info
    sessions.p.locator = lambda sel: L(loc(sel))


@pytest.mark.asyncio
async def test_m13_a01_confirmed_inert_link_click_proceeds(tmp_path):
    sessions, approvals, store = Sessions(), Approvals(), Store()
    _with_probe(sessions, {"tag": "a", "type": "", "inForm": False, "href": "/tab2", "handler": False, "text": "next tab"})
    svc = BrowserService(sessions, approvals, store, str(tmp_path), {"example.com"})
    result = await NavigationLoop(svc, OneClick("#next-tab")).run("t", "r", "go")
    assert result["status"] == "complete" and sessions.p.clicked == ["#next-tab"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["no_probe", "probe_raises", "in_form", "custom_handler", "button_tag", "garbage"])
async def test_m13_a01_ambiguous_dom_fails_closed(tmp_path, mode):
    sessions, approvals, store = Sessions(), Approvals(), Store()
    base = {"tag": "a", "type": "", "inForm": False, "href": "/x", "handler": False, "text": "next"}
    if mode == "probe_raises": _with_probe(sessions, exc=RuntimeError("boom"))
    elif mode == "in_form": _with_probe(sessions, {**base, "inForm": True})
    elif mode == "custom_handler": _with_probe(sessions, {**base, "handler": True})
    elif mode == "button_tag": _with_probe(sessions, {**base, "tag": "div", "href": ""})
    elif mode == "garbage": _with_probe(sessions, "nope")
    svc = BrowserService(sessions, approvals, store, str(tmp_path), {"example.com"})
    result = await NavigationLoop(svc, OneClick("#next-tab")).run("t", "r", "go")
    assert result["status"] == "awaiting_approval" and sessions.p.clicked == []


@pytest.mark.asyncio
async def test_m13_a05_scroll_is_audited(tmp_path):
    sessions, approvals, store = Sessions(), Approvals(), Store()
    svc = BrowserService(sessions, approvals, store, str(tmp_path), {"example.com"})

    class Scroll:
        n = 0
        async def next_action(self, i, s, h):
            Scroll.n += 1
            return {"type": "scroll", "pixels": 300} if Scroll.n == 1 else {"type": "done"}
    await NavigationLoop(svc, Scroll()).run("t", "r", "look")
    assert ActionType.SCROLL in [e.action for e in store.events]


@pytest.mark.asyncio
async def test_m13_a03_dom_swap_after_approval_is_refused(tmp_path):
    approvals, sessions, store = Approvals(), Sessions(), Store()
    svc = BrowserService(sessions, approvals, store, str(tmp_path), {"example.com"})
    await svc.request_submit("t", "u", "r", "#go", {"name": "Ada"})
    approvals.rows["a"]["status"] = ApprovalStatus.APPROVED
    original = sessions.p.screenshot

    async def different(**kwargs):
        return b"a completely different page"
    sessions.p.screenshot = different
    with pytest.raises(PermissionError):
        await svc.submit("t", "r", "#go", {"name": "Ada"}, "a")
    assert sessions.p.clicked == []
    sessions.p.screenshot = original
    await svc.submit("t", "r", "#go", {"name": "Ada"}, "a")
    assert sessions.p.clicked == ["#go"]


def test_m15_a03_legacy_render_latex_escapes(tmp_path):
    from app.modules.m15_document_generator.service import Service
    template = tmp_path / "x.tex.j2"
    template.write_text("<<{{ title }}>>")
    out = Service.render_latex(template, {"title": r"\input{/etc/passwd}"}).decode()
    assert "\\input{" not in out and "textbackslash" in out


def _m16_service(tmp_path):
    os.environ.setdefault("ATLAS_DATABASE_URL", f"sqlite:///{tmp_path}/m16.db")
    from app.modules.m16_executive_dashboard.service import Service
    from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository
    return Service(SqlDashboardRepository("t-repair", "u"))


def test_m16_a01_mutation_preview_files_one_approval_only():
    from app.modules.m16_executive_dashboard.service import Service
    from tests.modules.test_m16_executive_dashboard import Repo
    repo = Repo()
    marked = set()
    original_mark = repo.mark_command

    def mark(cid, at):
        if cid in marked:
            raise RuntimeError("already claimed")
        marked.add(cid); original_mark(cid, at)
    repo.mark_command = mark
    # Repo.get_command reads executed_at from stored row; mirror the SQL behaviour
    svc = Service(repo)
    preview = svc.preview("send this email to carol")
    assert svc.execute(preview.id)["status"] == "approval_required"
    with pytest.raises(RuntimeError):
        svc.execute(preview.id)
    assert len(repo.approvals) == 1


@pytest.mark.parametrize("text", ["please remove all users", "cancel the order and pay invoice", "show kpis and delete the db", "transfer funds to bob", "reset the password"])
def test_m16_a02_mutating_phrasing_is_not_read_only(text):
    from app.modules.m16_executive_dashboard.service import Service
    assert Service._parse(text)["read_only"] is False


@pytest.mark.parametrize("text", ["show kpis", "what is blocked?", "show created tasks", "status of the timeline"])
def test_m16_a02_read_phrasing_stays_read_only(text):
    from app.modules.m16_executive_dashboard.service import Service
    assert Service._parse(text)["read_only"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("href", ["javascript:document.forms[0].requestSubmit()", " JaVa\tScript:void(0)", "data:text/html,x", "vbscript:x", "blob:abc"])
async def test_m13_a01_executable_href_is_never_inert(tmp_path, href):
    sessions, approvals, store = Sessions(), Approvals(), Store()
    _with_probe(sessions, {"tag": "a", "type": "", "inForm": False, "href": href, "handler": False, "text": "continue"})
    svc = BrowserService(sessions, approvals, store, str(tmp_path), {"example.com"})
    result = await NavigationLoop(svc, OneClick("#c")).run("t", "r", "go")
    assert result["status"] == "awaiting_approval" and sessions.p.clicked == []
