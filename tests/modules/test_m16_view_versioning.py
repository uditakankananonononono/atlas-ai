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

def _file_repo_pair(tmp_path, tenant):
    """Two repositories on two separate connections to one SQLite FILE (a real cross-connection race)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.modules.m16_executive_dashboard import repository as R
    eng = create_engine(f"sqlite:///{tmp_path/'v.db'}", connect_args={"check_same_thread": False, "timeout": 10})
    R.Base.metadata.create_all(eng)
    mk = lambda: R.SqlDashboardRepository.__new__(R.SqlDashboardRepository)
    out = []
    for _ in range(2):
        r = mk(); r.tenant_id = tenant; r.actor_id = "a"; r.sessions = sessionmaker(eng, expire_on_commit=False); out.append(r)
    return out

LAYOUT = {"widgets": [{"id": "a", "kind": "blockers", "position": 0, "visible": True, "kpi_id": None}]}

def _race(r1, r2, expect):
    """Both writers run save_view with the same base; a barrier inside the first statement of each holds both
    until both have read the same state, which is how a read-then-write CAS loses an update."""
    import threading
    from datetime import datetime, timezone
    from sqlalchemy import event
    barrier = threading.Barrier(2, timeout=5); res = {}
    for r in (r1, r2):
        eng = r.sessions.kw["bind"]
        def hook(conn, cur, stmt, params, ctx, many, _b=barrier):
            if stmt.lstrip().upper().startswith(("SELECT", "UPDATE", "INSERT")) and not getattr(_b, "_done", {}).get(threading.get_ident()):
                _b._done = {**getattr(_b, "_done", {}), threading.get_ident(): True}
                try: _b.wait()
                except threading.BrokenBarrierError: pass
        event.listen(eng, "before_cursor_execute", hook)
    def go(name, r):
        from app.modules.m16_executive_dashboard.repository import ViewVersionConflict
        try: res[name] = ("ok", r.save_view({**LAYOUT, "tag": name}, datetime.now(timezone.utc), expect_version=expect))
        except ViewVersionConflict as e: res[name] = ("conflict", e.current)
    ts = [threading.Thread(target=go, args=(n, r)) for n, r in (("w1", r1), ("w2", r2))]
    [t.start() for t in ts]; [t.join(15) for t in ts]
    return res

def test_two_connections_same_base_exactly_one_wins(tmp_path):
    r1, r2 = _file_repo_pair(tmp_path, "race-existing")
    assert r1.save_view(LAYOUT, __import__("datetime").datetime.now(__import__("datetime").timezone.utc)) == 1
    res = _race(r1, r2, expect=1)
    kinds = sorted(v[0] for v in res.values())
    assert kinds == ["conflict", "ok"], res
    assert [v for v in res.values() if v[0] == "ok"][0][1] == 2
    layout, _ = r1.get_view(); assert layout["version"] == 2

def test_two_connections_first_insert_exactly_one_wins(tmp_path):
    r1, r2 = _file_repo_pair(tmp_path, "race-new")
    res = _race(r1, r2, expect=0)
    assert sorted(v[0] for v in res.values()) == ["conflict", "ok"], res
    assert r1.get_view()[0]["version"] == 1

def test_missing_row_with_nonzero_base_is_conflict_not_insert(tmp_path):
    from datetime import datetime, timezone
    from app.modules.m16_executive_dashboard.repository import ViewVersionConflict
    r1, _ = _file_repo_pair(tmp_path, "empty")
    with pytest.raises(ViewVersionConflict) as e: r1.save_view(LAYOUT, datetime.now(timezone.utc), expect_version=3)
    assert e.value.current == 0 and r1.get_view() == (None, None)
