"""M16 dashboard view: versioned compare-and-set saves against the real SQL repository."""
import uuid
import pytest
from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository, ViewVersionConflict
from app.modules.m16_executive_dashboard.schemas import DashboardViewIn, WidgetConfig, WidgetKind
from app.modules.m16_executive_dashboard.service import Service

def svc():
    return Service(SqlDashboardRepository(f"t-{uuid.uuid4().hex}", "actor"))
def body(*ids, base=None):
    return DashboardViewIn(widgets=[WidgetConfig(id=i, kind=WidgetKind.BLOCKERS, position=n) for n, i in enumerate(ids)], base_version=base)

def test_get_returns_version_zero_before_any_save_then_increments():
    s = svc()
    assert s.get_view().version == 0
    assert s.save_view(body("a")).version == 1
    assert s.save_view(body("a", "b")).version == 2
    assert s.get_view().version == 2

def test_same_base_second_write_is_rejected_and_nothing_is_overwritten():
    s = svc()
    v1 = s.save_view(body("a")).version
    assert s.save_view(body("first", base=v1)).version == 2
    with pytest.raises(ViewVersionConflict) as e:
        s.save_view(body("second", base=v1))
    assert e.value.current == 2
    assert [w.id for w in s.get_view().widgets][0] == "first"

def test_save_without_base_still_works_last_write_wins():
    s = svc(); s.save_view(body("a", base=0))
    assert s.save_view(body("z")).version == 2

def test_http_route_maps_conflict_to_409_with_current_version():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m16_executive_dashboard import routes
    s = svc(); app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: s
    c = TestClient(app); put = lambda **kw: c.put("/executive-dashboard/view", json=kw)
    w = lambda i: [{"id": i, "kind": "blockers", "position": 0, "visible": True, "kpi_id": None}]
    assert put(widgets=w("a"), base_version=0).json()["version"] == 1
    r = put(widgets=w("b"), base_version=0)
    assert r.status_code == 409 and r.json()["detail"]["current_version"] == 1
    assert c.get("/executive-dashboard/view").json()["widgets"][0]["id"] == "a"
