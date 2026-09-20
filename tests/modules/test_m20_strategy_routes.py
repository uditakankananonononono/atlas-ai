"""Mounted-route evidence for rows 60-84: one HTTP path per row."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m20_general_cognitive_worker.routes import bind_service, router
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService


@pytest.fixture()
def client():
    service = CognitiveWorkerService()
    app = FastAPI()
    app.include_router(router)
    bind_service(service)
    return TestClient(app), service


def test_row60_ergodicity_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/ergodicity",
               json={"outcomes": [[0.5, 1.5], [0.5, 0.6]]})
    assert r.status_code == 200
    body = r.json()
    assert not body["ergodic"] and "ruins you" in body["verdict"]
    bad = c.post("/api/modules/20/meta/ergodicity", json={"outcomes": [[1.5, 1.5]]})
    assert bad.status_code == 422


def test_row61_nonlinear_routes(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/nonlinear/classify",
               json={"xs": [1, 2, 4, 8, 16], "ys": [2, 16, 128, 1024, 8192]})
    assert r.status_code == 200
    body = r.json()
    assert body["best_fit"] == "power_law"
    ex = c.post("/api/modules/20/meta/nonlinear/extrapolate",
                json={"model": "power_law", "slope": body["slope"],
                      "intercept": body["intercept"], "x": 32})
    assert ex.status_code == 200
    assert ex.json()["extrapolated"] == pytest.approx(65536, rel=1e-2)


def test_row62_tipping_point_route(client):
    c, _ = client
    series = [1.0 + 0.01 * i for i in range(10)] + [1.0, 1.9, 0.2, 2.2, 0.1, 2.5, 0.05, 3.0, 0.02, 3.5]
    r = c.post("/api/modules/20/meta/tipping-point",
               json={"series": series, "threshold": 3.6})
    assert r.status_code == 200
    assert r.json()["warning"]
    short = c.post("/api/modules/20/meta/tipping-point", json={"series": [1.0, 2.0]})
    assert short.status_code == 422


def test_row63_network_effects_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/network-effects",
               json={"n_users": 100, "two_sided": True})
    assert r.status_code == 200
    body = r.json()
    assert body["value_estimates"]["metcalfe"] == 4950.0
    assert "two-sided" in body["network_kind"]


def test_row64_flywheels_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/flywheels", json={"links": [
        {"source": "users", "target": "content", "sign": "+"},
        {"source": "content", "target": "users", "sign": "+", "delay": "weeks"},
    ]})
    assert r.status_code == 200
    wheels = r.json()["flywheels"]
    assert wheels and wheels[0]["touches_growth"]


def test_row65_moats_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/moats", json={"ratings": {
        "network_effects": {"strength": 4.0, "durability_years": 5}}})
    assert r.status_code == 200
    assert r.json()["strongest"] == "network_effects"
    assert "caveat" in r.json()


def test_row66_disruption_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/disruption", json={
        "entrant_improvement_rate": 0.5, "incumbent_improvement_rate": 0.1,
        "entrant_targets_underserved": False, "entrant_cheaper": True,
        "incumbent_overserving": True})
    assert r.status_code == 200
    assert r.json()["disruption_type"] == "low-end"
    assert r.json()["disruption_likely"]


def test_row67_jtbd_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/jtbd", json={
        "product": "rideshare",
        "statements": ["When I leave work late, I want to get home fast, so I can feel safe"]})
    assert r.status_code == 200
    job = r.json()["jobs"][0]
    assert job["parsed"] and "emotional" in job["dimensions"]


def test_row68_value_chain_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/value-chain", json={"stages": [
        {"name": "farm", "cost": 1.0, "price": 2.0},
        {"name": "cafe", "cost": 2.0, "price": 10.0}]})
    assert r.status_code == 200
    assert r.json()["capture_concentration"] == "cafe"


def test_row69_pareto_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/pareto",
               json={"items": {"a": 50, "b": 30, "c": 10, "d": 10}})
    assert r.status_code == 200
    assert r.json()["vital_few"] == ["a", "b"]
    assert r.json()["share_covered"] == pytest.approx(0.8)


def test_row70_toc_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/toc/observe", json={"stages": [
        {"name": "build", "capacity": 50, "demand": 40},
        {"name": "test", "capacity": 20, "demand": 40}]})
    assert r.status_code == 200
    assert r.json()["bottleneck"] == "test"
    second = c.post("/api/modules/20/meta/toc/observe", json={"stages": [
        {"name": "build", "capacity": 50, "demand": 60},
        {"name": "test", "capacity": 100, "demand": 40}]})
    assert second.json()["migrated_from"] == "test"


def test_row71_queue_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/queue",
               json={"arrival_rate": 4.0, "service_rate": 5.0})
    assert r.status_code == 200
    assert r.json()["avg_in_system"] == pytest.approx(4.0)
    multi = c.post("/api/modules/20/meta/queue",
                   json={"arrival_rate": 8.0, "service_rate": 5.0, "servers": 2})
    assert multi.json()["stable"]
    unstable = c.post("/api/modules/20/meta/queue",
                      json={"arrival_rate": 6.0, "service_rate": 5.0})
    assert not unstable.json()["stable"]


def test_row72_littles_law_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/littles-law",
               json={"wip": 12.0, "throughput": 3.0})
    assert r.status_code == 200
    assert r.json()["cycle_time"] == pytest.approx(4.0)
    assert r.json()["levers"]
    bad = c.post("/api/modules/20/meta/littles-law", json={"wip": 12.0})
    assert bad.status_code == 422


def test_row73_critical_path_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/critical-path", json={"tasks": [
        {"id": "design", "duration": 5, "depends_on": []},
        {"id": "build", "duration": 10, "depends_on": ["design"]},
        {"id": "ship", "duration": 2, "depends_on": ["build"]}]})
    assert r.status_code == 200
    assert r.json()["duration"] == 17.0
    assert r.json()["critical_path"] == ["design", "build", "ship"]


def test_row74_monte_carlo_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/monte-carlo", json={
        "tasks": [{"min": 1.0, "mode": 2.0, "max": 5.0}], "trials": 500, "seed": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["p5"] < body["median"] < body["p95"]


def test_row75_sensitivity_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/sensitivity", json={
        "expression": "price * volume - fixed",
        "params": {"price": 10.0, "volume": 100.0, "fixed": 200.0}})
    assert r.status_code == 200
    assert r.json()["most_influential"] in {"price", "volume"}
    unsafe = c.post("/api/modules/20/meta/sensitivity", json={
        "expression": "__import__('os')", "params": {"x": 1.0}})
    assert unsafe.status_code == 422


def test_row76_tornado_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/tornado", json={
        "expression": "price * volume - fixed",
        "params": {"price": 10.0, "volume": 100.0, "fixed": 200.0}})
    assert r.status_code == 200
    bars = r.json()["bars"]
    assert bars[0]["impact"] >= bars[-1]["impact"]
    assert "|" in bars[0]["bar"]


def test_row77_decision_tree_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/decision-tree", json={"spec": {
        "kind": "decision", "children": [
            {"node": {"kind": "leaf", "value": 10.0, "label": "safe"}},
            {"node": {"kind": "chance", "label": "risky", "children": [
                {"prob": 0.5, "node": {"kind": "leaf", "value": 30.0}},
                {"prob": 0.5, "node": {"kind": "leaf", "value": 0.0}}]}}]}})
    assert r.status_code == 200
    assert r.json()["value"] == pytest.approx(15.0)
    assert r.json()["best_first_choice"] == "risky"


def test_row78_real_options_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/real-options", json={
        "underlying": 100.0, "up": 1.5, "down": 0.6,
        "exercise_cost": 120.0, "kind": "expand", "steps": 10})
    assert r.status_code == 200
    assert r.json()["option_value"] > 0.0
    assert "caveat" in r.json()
    arb = c.post("/api/modules/20/meta/real-options", json={
        "underlying": 100.0, "up": 1.0, "down": 0.5, "exercise_cost": 10.0,
        "risk_free": 0.5})
    assert arb.status_code == 422


def test_row79_game_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/game", json={
        "row_payoffs": [[3, 0], [5, 1]], "col_payoffs": [[3, 5], [0, 1]]})
    assert r.status_code == 200
    body = r.json()
    assert 0 in body["dominated_rows"]
    assert [0, 0] in body["pareto_optimal_cells"]


def test_row80_nash_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/nash", json={
        "row_payoffs": [[1, -1], [-1, 1]], "col_payoffs": [[-1, 1], [1, -1]]})
    assert r.status_code == 200
    body = r.json()
    assert body["pure_equilibria"] == []
    assert body["mixed_equilibrium"]["row_plays_first_with"] == pytest.approx(0.5)


def test_row81_mechanism_routes(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/mechanism/vcg", json={"agents": {
        "a": {"x": 10.0}, "b": {"x": 8.0}}})
    assert r.status_code == 200
    assert r.json()["payments"]["a"] == pytest.approx(8.0)
    ic = c.post("/api/modules/20/meta/mechanism/check-incentives", json={
        "agent": "a", "true_values": {"x": 10.0}, "others": {"b": {"x": 8.0}},
        "deviations": [{"x": 100.0}, {"x": 1.0}]})
    assert ic.status_code == 200
    assert ic.json()["incentive_compatible"]


def test_row82_auction_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/auction", json={
        "auction_type": "first_price", "value": 100.0, "n_bidders": 5,
        "common_value": True})
    assert r.status_code == 200
    body = r.json()
    assert body["recommended_bid"] == pytest.approx(80.0)
    assert any("winner's curse" in w for w in body["warnings"])


def test_row83_signaling_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/signaling", json={
        "benefit": 100.0, "cost_high_type": 40.0, "cost_low_type": 150.0})
    assert r.status_code == 200
    assert r.json()["separating"]


def test_row84_principal_agent_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/principal-agent", json={
        "efforts": [{"level": "low", "cost": 0.0, "expected_output": 100.0},
                    {"level": "high", "cost": 30.0, "expected_output": 200.0}],
        "target_effort": "high"})
    assert r.status_code == 200
    assert r.json()["recommended_share"] is not None
    assert "not business" in r.json()["caveat"]
