"""M16 card over M04 scheduled re-run proposals: read-only, tenant-scoped, degrades cleanly."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m16_executive_dashboard import routes as m16_routes
from app.modules.m16_executive_dashboard.rerun_card import build_card, card_for
from app.modules.m16_executive_dashboard.schemas import DashboardViewIn, WidgetConfig, WidgetKind
from app.modules.m16_executive_dashboard.service import Service

from tests.modules.test_m04_approved_sandbox import (  # reuse the real M04 fixtures
    Clock, center, needs_bwrap, shared_executor, submit,
)
from tests.modules.test_m16_dashboard_analytics import CAT, NOW, FakeRepo

STATS = {
    "tenant_id": "tenant-a", "as_of": "2026-10-05T09:00:00+00:00",
    "schedules": {"total": 3, "active": 2, "due_now": ["s1"]},
    "proposals": {"total": 5, "by_state": {"pending": 2, "approved_not_executed": 1, "executed": 2},
                  "overdue": 2, "verdicts": {"reproduced": 1, "diverged": 1}},
    "overdue": [
        {"schedule_id": "s1", "original_approval_id": "o1", "rerun_approval_id": "r1", "due_at": "x",
         "filed_at": "2026-10-01T09:00:00+00:00", "state": "pending", "age_hours": 96.0, "overdue": True},
        {"schedule_id": "s1", "original_approval_id": "o2", "rerun_approval_id": "r2", "due_at": "x",
         "filed_at": "2026-09-30T09:00:00+00:00", "state": "approved_not_executed", "age_hours": 120.0, "overdue": True},
    ],
    "recent": [{"schedule_id": "s2", "original_approval_id": f"o{i}", "rerun_approval_id": f"r{i}", "due_at": "x",
                "filed_at": "2026-10-04T09:00:00+00:00", "state": "executed", "age_hours": 24.0,
                "overdue": False, "verdict": "reproduced"} for i in range(8)],
}


def test_card_shapes_stats_for_the_dashboard():
    card = build_card(STATS)
    assert card.available and card.schedules_total == 3 and card.schedules_active == 2 and card.schedules_due_now == 1
    assert card.awaiting_approval == 2 and card.approved_not_executed == 1 and card.overdue_total == 2
    assert card.by_state == {"pending": 2, "approved_not_executed": 1, "executed": 2, "denied": 0, "expired": 0}
    assert card.verdicts == {"reproduced": 1, "diverged": 1}
    assert [r.rerun_approval_id for r in card.overdue] == ["r2", "r1"]  # oldest first
    assert len(card.recent) == 5 and card.recent[0].verdict == "reproduced"
    assert card.overdue[0].approval_path == "/approval-center/requests/r2"


def test_card_degrades_instead_of_breaking_the_dashboard():
    assert card_for(None).available is False
    def boom():
        raise RuntimeError("db locked")
    down = card_for(boom)
    assert down.available is False and "RuntimeError" in down.reason and down.overdue == []


def test_route_is_get_only_and_survives_m04_failure():
    app = FastAPI(); app.include_router(m16_routes.router)
    def boom():
        raise OSError("disk")
    app.dependency_overrides[m16_routes.get_rerun_stats_source] = lambda: boom
    client = TestClient(app); h = {"X-Atlas-Tenant": "tenant-a"}
    r = client.get("/executive-dashboard/rerun-schedules", headers=h)
    assert r.status_code == 200 and r.json()["available"] is False
    assert client.post("/executive-dashboard/rerun-schedules", headers=h).status_code == 405


def test_view_shows_the_card_by_default_and_on_older_saved_layouts():
    assert WidgetKind.RERUN_SCHEDULES in [w.kind for w in Service(FakeRepo(), catalog=CAT).get_view(NOW).widgets]
    repo = FakeRepo(); stored = {}
    repo.save_view = lambda layout, at: stored.update(layout=layout, at=at)
    repo.get_view = lambda: (stored.get("layout"), stored.get("at"))
    s = Service(repo, catalog=CAT)
    # a layout saved before the card existed keeps its order; the card is appended last
    stored.update(layout={"widgets": [{"id": "b", "kind": "blockers", "position": 0, "visible": True, "kpi_id": None},
                                      {"id": "k", "kind": "kpi_card", "position": 1, "visible": False, "kpi_id": None}]}, at=NOW)
    view = s.get_view(NOW)
    assert [(w.id, w.position, w.visible) for w in view.widgets] == [("b", 0, True), ("k", 1, False), ("rerun_schedules", 2, True)]
    # hiding it persists and is not re-added
    widgets = [w.model_copy(update={"visible": w.kind != WidgetKind.RERUN_SCHEDULES}) for w in view.widgets]
    s.save_view(DashboardViewIn(widgets=widgets))
    again = s.get_view(NOW)
    assert [w.kind for w in again.widgets].count(WidgetKind.RERUN_SCHEDULES) == 1
    assert next(w for w in again.widgets if w.kind == WidgetKind.RERUN_SCHEDULES).visible is False


@needs_bwrap
def test_route_reads_real_m04_stats_per_tenant_and_files_nothing(center, tmp_path, monkeypatch):
    from app.modules.m04_research_scientist import routes as m04_routes
    from app.modules.m04_research_scientist.rerun_schedule import RerunScheduleService
    ex_a = shared_executor(center, tmp_path, "tenant-a")
    ex_b = shared_executor(center, tmp_path, "tenant-b")
    monkeypatch.setattr(m04_routes, "_sandbox_executors", {"tenant-a": ex_a, "tenant-b": ex_b})
    a_orig = submit(center, "print('a')", tenant="tenant-a"); ex_a.execute(a_orig)
    past = datetime.now(timezone.utc) - timedelta(days=5)
    svc_a = RerunScheduleService(ex_a, clock=lambda: past)
    svc_a.create(scope="analysis", target=a_orig, interval_hours=24, overdue_after_hours=24, first_due_at=past)
    filed = svc_a.tick()["filed"]  # proposal filed 5 days ago, never approved -> overdue now
    assert len(filed) == 1
    app = FastAPI(); app.include_router(m16_routes.router)
    client = TestClient(app)
    before = len(center.list(user_id="tenant-a"))
    a = client.get("/executive-dashboard/rerun-schedules", headers={"X-Atlas-Tenant": "tenant-a"}).json()
    assert a["available"] and a["schedules_total"] == 1 and a["schedules_due_now"] == 1
    assert a["awaiting_approval"] == 1 and a["overdue_total"] == 1
    rid = filed[0]["rerun_approval_id"]
    assert a["overdue"][0]["rerun_approval_id"] == rid
    # the row's link resolves to the real pending approval in the M00 approval center, for this tenant only
    from app.modules.m00_approval_center import routes as m00_routes
    m00 = FastAPI(); m00.include_router(m00_routes.router)
    m00.dependency_overrides[m00_routes.get_service] = lambda: center
    m00_client = TestClient(m00)
    linked = m00_client.get(a["overdue"][0]["approval_path"], headers={"X-Atlas-Tenant": "tenant-a"})
    assert linked.status_code == 200 and linked.json()["action_type"] == "rerun_sandboxed_analysis"
    assert linked.json()["status"] == "pending"
    assert m00_client.get(a["overdue"][0]["approval_path"], headers={"X-Atlas-Tenant": "tenant-b"}).status_code == 404
    # reading the card is not a tick: nothing new filed even though the schedule is due
    assert RerunScheduleService(ex_a).stats()["proposals"]["total"] == 1
    assert len(center.list(user_id="tenant-a")) == before
    # tenant B sees none of tenant A's schedules or proposals
    b = client.get("/executive-dashboard/rerun-schedules", headers={"X-Atlas-Tenant": "tenant-b"}).json()
    assert b["available"] and b["schedules_total"] == 0 and b["proposals_total"] == 0 and b["overdue"] == []
