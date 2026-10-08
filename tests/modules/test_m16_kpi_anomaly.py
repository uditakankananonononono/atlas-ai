"""M16 KPI anomaly check: robust z-score on a KPI's own recorded history (heuristic, labelled as such)."""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from app.modules.m16_executive_dashboard.anomaly import detect, MIN_POINTS
from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository
from app.modules.m16_executive_dashboard.service import Service

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
pts = lambda vals: [(T0 + timedelta(hours=i), float(v)) for i, v in enumerate(vals)]

def test_known_numbers():
    # history 10,11,9,10,12,10,11,9 -> median 10, MAD 1 ; value 20 -> z = 0.6745*10/1 = 6.745
    v = detect("k", 24, 20, pts([10, 11, 9, 10, 12, 10, 11, 9]))
    assert (v.baseline_median, v.baseline_mad, v.robust_z, v.status, v.direction) == (10.0, 1.0, 6.745, "anomalous", "above")
    assert detect("k", 24, 10.5, pts([10, 11, 9, 10, 12, 10, 11, 9])).status == "normal"
    assert detect("k", 24, 0, pts([10, 11, 9, 10, 12, 10, 11, 9])).direction == "below"

def test_too_little_history_is_not_guessed():
    v = detect("k", 24, 999, pts([1, 2, 3]))
    assert v.status == "insufficient_history" and v.robust_z is None and v.points_used == 3 and MIN_POINTS == 8

def test_constant_history_reports_flat_baseline_change_without_inventing_a_score():
    flat = pts([5] * 10)
    v = detect("k", 24, 9, flat)
    assert v.status == "flat_baseline_changed" and v.robust_z is None and v.baseline_mad == 0
    assert detect("k", 24, 5, flat).status == "normal"

def test_outliers_in_history_do_not_hide_a_real_anomaly():
    # a mean/stdev z-score would be dragged by the 1000; median/MAD is not
    v = detect("k", 24, 30, pts([10, 11, 9, 10, 12, 10, 1000, 9]))
    assert v.status == "anomalous"

def test_result_always_carries_its_limits():
    assert any("heuristic" in l for l in detect("k", 24, 1, []).limits)

def _svc():
    return Service(SqlDashboardRepository(f"t-{uuid.uuid4().hex}", "actor"))

def test_service_reads_real_recorded_history_and_excludes_the_current_points_own_record():
    s = _svc(); now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
    kid = s.kpis(now)[0]
    # record 9 historical points around 10 for this KPI, plus one at now-1min (the current value's own record)
    for i, val in enumerate([10, 11, 9, 10, 12, 10, 11, 9, 10]):
        s.repository.record_kpi_points([(kid.id, kid.window_hours, val)], now - timedelta(hours=20 - i))
    s.repository.record_kpi_points([(kid.id, kid.window_hours, 777)], now - timedelta(minutes=1))
    v = s.kpi_anomaly(kid.id, now)
    assert v.points_used == 9 and v.baseline_median == 10.0
    assert v.newest_point.replace(tzinfo=timezone.utc) == now - timedelta(hours=12)
    assert v.oldest_point.replace(tzinfo=timezone.utc) == now - timedelta(hours=20)
    assert v.baseline_mad == 1.0
    # Establish that recent data really exists in SQL; exclusion is the
    # service's five-minute boundary, not a failed fixture insertion.
    all_points = s.repository.kpi_history(kid.id, kid.window_hours, now, 60)
    assert len(all_points) == 10 and all_points[0][1] == 777.0
    assert all_points[0][0].replace(tzinfo=timezone.utc) == now - timedelta(minutes=1)
    with pytest.raises(LookupError): s.kpi_anomaly("nope", now)

def test_http_route():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m16_executive_dashboard import routes
    s = _svc(); app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: s
    c = TestClient(app); kid = s.kpis()[0]
    r = c.get(f"/executive-dashboard/kpis/{kid.id}/anomaly")
    assert r.status_code == 200 and r.json()["status"] == "insufficient_history" and r.json()["limits"]
    assert c.get("/executive-dashboard/kpis/nope/anomaly").status_code == 404
    assert c.get(f"/executive-dashboard/kpis/{kid.id}/anomaly?limit=2").status_code == 422

# ---- non-finite data: controlled refusal, never normal/anomalous, never NaN/Infinity in the response ----
import json, math
GOOD = [10, 11, 9, 10, 12, 10, 11, 9]

@pytest.mark.parametrize("cur", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_current_is_refused(cur):
    v = detect("k", 24, cur, pts(GOOD))
    assert v.status == "invalid_data" and v.value is None and v.robust_z is None and v.direction is None and v.reason
    json.loads(v.model_dump_json(), parse_constant=lambda c: (_ for _ in ()).throw(AssertionError(c)))

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_history_point_is_refused(bad):
    v = detect("k", 24, 10, pts(GOOD + [bad]))
    assert v.status == "invalid_data" and "1 of 9" in v.reason and v.robust_z is None
    json.loads(v.model_dump_json(), parse_constant=lambda c: (_ for _ in ()).throw(AssertionError(c)))

def test_finite_but_overflowing_values_are_refused_not_inf():
    v = detect("k", 24, 1e308, pts([-1e308, 1e308, -1e308, 1e308, -1e308, 1e308, -1e308, 1e308]))
    assert v.status == "invalid_data" and v.robust_z is None
    v2 = detect("k", 24, -1e308, pts(GOOD))
    assert v2.status == "anomalous" and v2.direction == "below"
    assert v2.baseline_median == 10.0 and v2.baseline_mad == 1.0
    assert v2.robust_z == -6.745e307 and math.isfinite(v2.robust_z)
    assert v2.reason is None
    json.loads(v2.model_dump_json(), parse_constant=lambda c: (_ for _ in ()).throw(AssertionError(c)))

def _strict(resp):
    return json.loads(resp.text, parse_constant=lambda c: (_ for _ in ()).throw(AssertionError(f"non-finite {c} in JSON")))

def test_poisoned_sql_history_through_real_repository_and_http():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m16_executive_dashboard import routes
    s = _svc(); now = datetime.now(timezone.utc); kid = s.kpis(now)[0]
    for i, val in enumerate([10, 11, 9, 10, 12, 10, 11, 9, 10]):
        s.repository.record_kpi_points([(kid.id, kid.window_hours, val)], now - timedelta(hours=40 - i))
    s.repository.record_kpi_points([(kid.id, kid.window_hours, float("inf"))], now - timedelta(hours=3))  # poisoned row in SQL
    app = FastAPI(); app.include_router(routes.router); app.dependency_overrides[routes.get_service] = lambda: s
    r = TestClient(app).get(f"/executive-dashboard/kpis/{kid.id}/anomaly")
    body = _strict(r)
    assert r.status_code == 200 and body["status"] == "invalid_data" and body["robust_z"] is None and "not finite" in body["reason"]

def test_poisoned_current_value_through_http():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m16_executive_dashboard import routes
    s = _svc(); kid = s.kpis()[0]
    real = s.kpis
    def poisoned(now=None):
        out = real(now); out[0] = out[0].model_copy(update={"value": float("nan")}); return out
    s.kpis = poisoned
    app = FastAPI(); app.include_router(routes.router); app.dependency_overrides[routes.get_service] = lambda: s
    r = TestClient(app).get(f"/executive-dashboard/kpis/{kid.id}/anomaly")
    body = _strict(r)
    assert r.status_code == 200 and body["status"] == "invalid_data" and body["value"] is None
