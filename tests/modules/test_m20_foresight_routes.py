"""Mounted-route evidence for rows 35-59: one HTTP path per row."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m20_general_cognitive_worker.routes import bind_service, router
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService


@pytest.fixture()
def client():
    service = CognitiveWorkerService()
    service.semantic.remember("python packaging uses pyproject", kind="fact")
    app = FastAPI()
    app.include_router(router)
    bind_service(service)
    return TestClient(app), service


def test_row35_serendipity_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/serendipity/plan",
               json={"text": "improve the onboarding flow for new users with caching",
                     "available_slots": 5, "seed": 3})
    assert r.status_code == 200
    body = r.json()
    assert "slots" in body and "approval" in body["note"]


def test_row36_insight_routes(client):
    c, _ = client
    created = c.post("/api/modules/20/meta/insights",
                     json={"text": "lint pyproject configs automatically"})
    assert created.status_code == 201
    iid = created.json()["insight_id"]
    assert created.json()["links"]  # linked against semantic memory
    developed = c.post(f"/api/modules/20/meta/insights/{iid}/develop",
                       json={"note": "prototype it"})
    assert developed.status_code == 200
    assert developed.json()["status"] == "developed"
    missing = c.post("/api/modules/20/meta/insights/nope/develop", json={"note": "x"})
    assert missing.status_code == 404
    stale = c.get("/api/modules/20/meta/insights/stale")
    assert stale.status_code == 200


def test_row37_simulation_routes(client):
    c, _ = client
    created = c.post("/api/modules/20/meta/simulations",
                     json={"domain": "estimates", "predicted": 10.0, "confidence": 0.8})
    assert created.status_code == 201
    rid = created.json()["record_id"]
    resolved = c.post(f"/api/modules/20/meta/simulations/{rid}/resolve",
                      json={"actual": 20.0})
    assert resolved.status_code == 200
    assert resolved.json()["fidelity"] == pytest.approx(0.5)
    assert resolved.json()["confidence_adjustment"] == pytest.approx(0.5)


def test_row38_hypothesis_routes(client):
    c, _ = client
    a = c.post("/api/modules/20/meta/hypotheses",
               json={"statement": "cache bug", "prior": 0.6}).json()["hypothesis_id"]
    b = c.post("/api/modules/20/meta/hypotheses",
               json={"statement": "network", "prior": 0.4}).json()["hypothesis_id"]
    r = c.post("/api/modules/20/meta/hypotheses/evidence",
               json={"likelihood_ratios": {a: 3.0, b: 0.5}})
    assert r.status_code == 200
    ranking = r.json()["ranking"]
    assert ranking[0]["hypothesis_id"] == a
    assert ranking[0]["probability"] > ranking[1]["probability"]
    bad = c.post("/api/modules/20/meta/hypotheses/evidence",
                 json={"likelihood_ratios": {"missing": 1.0}})
    assert bad.status_code == 404


def test_row39_bayes_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/bayes/update",
               json={"prior": 0.5, "likelihood_ratio": 3.0})
    assert r.status_code == 200
    assert r.json()["posterior"] == pytest.approx(0.75)


def test_row40_causal_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/causal/assess",
               json={"cause": "ice cream", "effect": "drowning"})
    assert r.status_code == 200
    assert r.json()["verdict"] == "unverified"
    assert r.json()["causality_verified"] is False
    assert r.json()["required_tests"]


def test_row41_base_rate_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/base-rate/integrate",
               json={"base_rate": 0.1, "case_estimate": 0.9,
                     "evidence_reliability": 0.8, "sample_size": 50})
    assert r.status_code == 200
    body = r.json()
    assert 0.1 < body["adjusted"] < 0.9
    assert body["assumptions"]


def test_row42_reference_class_routes(client):
    c, _ = client
    for features, outcome in [("backend migration project", 30.0),
                              ("backend migration effort", 45.0),
                              ("backend data migration", 60.0)]:
        assert c.post("/api/modules/20/meta/reference-class/cases",
                      json={"features": features, "outcome": outcome}).status_code == 201
    r = c.post("/api/modules/20/meta/reference-class/forecast",
               json={"features": "backend migration"})
    assert r.status_code == 200
    fc = r.json()["forecast"]
    assert fc["n_cases"] >= 3 and fc["p25"] <= fc["median"] <= fc["p75"]


def test_row43_outside_view_route(client):
    c, service = client
    service.reference_class.add_case("rewrite project like this one", 12.0, label="past")
    r = c.post("/api/modules/20/meta/outside-view",
               json={"inside_estimate": 6.0, "subject": "rewrite project like this one",
                     "outside_weight": 0.5})
    assert r.status_code == 200
    body = r.json()
    assert body["outside_median"] == pytest.approx(12.0)
    assert body["blended"] == pytest.approx(9.0)
    assert body["perspective_notes"]


def test_row44_planning_fallacy_routes(client):
    c, _ = client
    for _ in range(10):
        assert c.post("/api/modules/20/meta/planning-fallacy/records",
                      json={"kind": "blog post", "estimated": 2.0,
                            "actual": 4.0}).status_code == 201
    r = c.post("/api/modules/20/meta/planning-fallacy/correct",
               json={"kind": "blog post", "estimate": 2.0})
    assert r.status_code == 200
    assert r.json()["corrected"] > 2.0
    assert r.json()["samples"] == 10


def test_row45_optimism_routes(client):
    c, _ = client
    for _ in range(4):
        assert c.post("/api/modules/20/meta/optimism/records",
                      json={"domain": "launches", "predicted_confidence": 0.9,
                            "succeeded": False}).status_code == 201
    r = c.post("/api/modules/20/meta/optimism/adjust",
               json={"domain": "launches", "confidence": 0.9})
    assert r.status_code == 200
    assert r.json()["adjusted"] < 0.9
    assert r.json()["direction"] == "optimistic"


def test_row46_scenarios_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/scenarios",
               json={"objective": "launch beta", "drivers": ["conversion", "stability"]})
    assert r.status_code == 200
    scenarios = r.json()["scenarios"]
    assert {s["name"] for s in scenarios} == {"best", "base", "worst", "wildcard"}
    assert sum(s["probability"] for s in scenarios) == pytest.approx(1.0)


def test_row47_premortem_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/premortem",
               json={"goal": "launch api with vendor partner before deadline",
                     "risks": ["vendor instability"]})
    assert r.status_code == 200
    assert r.json()["causes"]
    assert "failure_assumed_at" in r.json()


def test_row48_red_team_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/red-team",
               json={"plan": "Only one person can deploy; the launch will succeed.",
                     "assets": ["billing database"]})
    assert r.status_code == 200
    vectors = {v["vector"] for v in r.json()["vulnerabilities"]}
    assert "single point of failure" in vectors and "abuse case" in vectors


def test_row49_second_order_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/second-order",
               json={"action": "cut prices", "first_order": ["product gets cheaper"],
                     "depth": 2})
    assert r.status_code == 200
    effects = {e["effect"] for e in r.json()["effects"]}
    assert "demand increases" in effects
    assert r.json()["rules_used"]


def test_row50_systems_loops_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/systems/loops", json={"links": [
        {"source": "users", "target": "revenue", "sign": "+"},
        {"source": "revenue", "target": "marketing", "sign": "+", "delay": "months"},
        {"source": "marketing", "target": "users", "sign": "+"},
    ]})
    assert r.status_code == 200
    loops = r.json()["loops"]
    assert loops and loops[0]["kind"] == "reinforcing"
    assert "months" in loops[0]["delay_notes"]


def test_row51_leverage_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/systems/leverage", json={"links": [
        {"source": "users", "target": "revenue", "sign": "+"},
        {"source": "revenue", "target": "marketing", "sign": "+"},
        {"source": "marketing", "target": "users", "sign": "+"},
        {"source": "logo color", "target": "users", "sign": "+"},
    ]})
    assert r.status_code == 200
    points = r.json()["leverage_points"]
    assert points[0]["variable"] in {"users", "revenue", "marketing"}
    assert points[0]["score"] >= points[-1]["score"]


def test_row52_constraints_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/constraints/analyze", json={"stages": [
        {"name": "intake", "capacity": 100, "demand": 60},
        {"name": "review", "capacity": 20, "demand": 60},
    ]})
    assert r.status_code == 200
    assert r.json()["bottleneck"] == "review"
    assert r.json()["system_throughput"] == 20


def test_row53_antifragility_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/antifragility/assess", json={"components": [
        {"name": "single supplier", "stress_response": -0.8},
        {"name": "community", "stress_response": 0.5},
    ]})
    assert r.status_code == 200
    by_name = {x["name"]: x for x in r.json()["components"]}
    assert by_name["single supplier"]["classification"] == "fragile"
    assert by_name["community"]["classification"] == "antifragile"


def test_row54_optionality_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/optionality/assess",
               json={"decision": "5-year lease", "options_kept": ["sublet"],
                     "options_closed": ["remote-first", "coworking", "move"],
                     "reversible": False})
    assert r.status_code == 200
    assert r.json()["optionality_score"] == pytest.approx(0.25)
    assert r.json()["recommendations"]


def test_row55_reversibility_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/reversibility/assess",
               json={"decision": "delete prod data", "undo_cost": 10,
                     "undo_days": 365, "blast_radius": 10})
    assert r.status_code == 200
    assert r.json()["classification"] == "one_way_door"
    assert r.json()["requires_approval_review"]


def test_row56_asymmetry_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/asymmetry/evaluate", json={"options": [
        {"name": "side project", "downside": 100.0, "upside": 5000.0, "prob_upside": 0.1},
        {"name": "unhedged short", "upside": 500.0},
    ]})
    assert r.status_code == 200
    body = r.json()
    assert body["options"][0]["name"] == "side project"
    assert body["options"][0]["asymmetric"]
    assert "not investment" in body["caveat"]


def test_row57_ev_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/ev/compute", json={"options": [
        {"name": "a", "outcomes": [[0.5, 100.0], [0.5, 0.0]]},
        {"name": "b", "outcomes": [[0.9, 20.0], [0.1, -10.0]]},
    ]})
    assert r.status_code == 200
    body = r.json()
    assert body["options"][0]["name"] == "a"
    assert body["options"][0]["ev"] == pytest.approx(50.0)
    assert "not investment" in body["caveat"]


def test_row58_risk_of_ruin_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/risk-of-ruin",
               json={"capital": 1000.0, "bet_size": 10.0, "win_prob": 0.6})
    assert r.status_code == 200
    body = r.json()
    assert body["method"] == "closed_form"
    assert body["verdict"] == "acceptable"
    assert "not investment" in body["caveat"]


def test_row59_kelly_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/kelly/size",
               json={"win_prob": 0.6, "payoff_ratio": 1.0})
    assert r.status_code == 200
    body = r.json()
    assert body["full_kelly"] == pytest.approx(0.2)
    assert body["recommended"] == pytest.approx(0.1)
    assert "not investment" in body["caveat"]
    no_edge = c.post("/api/modules/20/meta/kelly/size",
                     json={"win_prob": 0.4, "payoff_ratio": 1.0})
    assert no_edge.json()["recommended"] == 0.0


def test_hypothesis_invalid_batch_http_has_no_partial_update(client):
    c, service = client
    h = service.hypotheses.add("candidate", prior=0.4)
    response = c.post("/api/modules/20/meta/hypotheses/evidence", json={"likelihood_ratios": {h.hypothesis_id: 3, "missing": 2}})
    assert response.status_code == 404
    assert service.hypotheses.hypotheses[h.hypothesis_id].probability == 0.4
    response = c.post("/api/modules/20/meta/hypotheses/evidence", json={"likelihood_ratios": {h.hypothesis_id: -1}})
    assert response.status_code == 422
    response = c.post("/api/modules/20/meta/hypotheses/evidence", json={"likelihood_ratios": {h.hypothesis_id: 2}})
    assert response.status_code == 200
    assert "heuristic" in response.json()["scope"]


def test_causal_randomized_flag_http_is_not_verified(client):
    c, _ = client
    response = c.post("/api/modules/20/meta/causal/assess", json={"cause": "a", "effect": "b", "evidence": {"randomized": True}})
    assert response.status_code == 200
    assert response.json()["verdict"] == "unverified"
    assert response.json()["causality_verified"] is False
    for flags in [{"randomized": "false"}, {"unknown": True}]:
        response = c.post("/api/modules/20/meta/causal/assess", json={"cause": "a", "effect": "b", "evidence": flags})
        assert response.status_code == 422


@pytest.mark.parametrize('field,value', [('predicted', True), ('predicted', '10'), ('confidence', True), ('confidence', '0.8')])
def test_simulation_http_does_not_coerce_numeric_inputs(client, field, value):
    c, service = client
    body = {'domain': 'fixture', 'predicted': 10, 'confidence': 0.8}
    body[field] = value
    response = c.post('/api/modules/20/meta/simulations', json=body)
    assert response.status_code == 422
    assert len(service.sim_fidelity.records) == 0


@pytest.mark.parametrize('actual', [True, '20'])
def test_simulation_http_actual_is_strict_numeric(client, actual):
    c, service = client
    record = service.sim_fidelity.record_prediction('fixture', 10)
    response = c.post(f'/api/modules/20/meta/simulations/{record.record_id}/resolve', json={'actual': actual})
    assert response.status_code == 422
    assert service.sim_fidelity.records[record.record_id].actual is None


@pytest.mark.parametrize('field,value', [('predicted_confidence', True), ('predicted_confidence', '0.8'), ('succeeded', 'false'), ('succeeded', 1)])
def test_optimism_http_rejects_coerced_record_inputs(client, field, value):
    c, service = client
    body = {'domain': 'fixture', 'predicted_confidence': 0.8, 'succeeded': False}
    body[field] = value
    response = c.post('/api/modules/20/meta/optimism/records', json=body)
    assert response.status_code == 422
    assert service.optimism.records == {}


@pytest.mark.parametrize('confidence', [True, '0.8'])
def test_optimism_http_rejects_coerced_adjust_inputs(client, confidence):
    c, _ = client
    response = c.post('/api/modules/20/meta/optimism/adjust', json={'domain': 'fixture', 'confidence': confidence})
    assert response.status_code == 422


@pytest.mark.parametrize('field,value', [('base_rate', True), ('case_estimate', '0.8'), ('evidence_reliability', True), ('sample_size', True), ('sample_size', '10')])
def test_base_rate_http_rejects_coerced_inputs(client, field, value):
    c, _ = client
    body = {'base_rate': 0.2, 'case_estimate': 0.8, 'evidence_reliability': 0.5, 'sample_size': 10}
    body[field] = value
    response = c.post('/api/modules/20/meta/base-rate/integrate', json=body)
    assert response.status_code == 422


@pytest.mark.parametrize('estimated,actual', [(True, 1), ('1', 2), (1, True), (1e-308, 1e308)])
def test_planning_http_invalid_or_overflow_ratio_rejects_without_record(client, estimated, actual):
    c, service = client
    response = c.post('/api/modules/20/meta/planning-fallacy/records', json={'kind': 'fixture', 'estimated': estimated, 'actual': actual})
    assert response.status_code == 422
    assert service.planning_fallacy.history == {}


def test_planning_http_corrected_overflow_is_422(client):
    c, service = client
    service.planning_fallacy.record(kind='fixture', estimated=1, actual=1e308)
    response = c.post('/api/modules/20/meta/planning-fallacy/correct', json={'kind': 'fixture', 'estimate': 1e308})
    assert response.status_code == 422


@pytest.mark.parametrize('field,value', [('inside_estimate', True), ('inside_estimate', '10'), ('outside_weight', True), ('outside_weight', '0.5')])
def test_outside_view_http_does_not_coerce_numbers(client, field, value):
    c, _ = client
    body = {'inside_estimate': 10, 'outside_weight': 0.5, 'subject': 'fixture'}
    body[field] = value
    assert c.post('/api/modules/20/meta/outside-view', json=body).status_code == 422


@pytest.mark.parametrize('outcome', [True, '10'])
def test_reference_http_does_not_coerce_outcome(client, outcome):
    c, service = client
    response = c.post('/api/modules/20/meta/reference-class/cases', json={'features': 'fixture', 'outcome': outcome})
    assert response.status_code == 422
    assert service.reference_class.cases == []


@pytest.mark.parametrize('probabilities', [{'best': True}, {'best': '0.2'}, {'best': -0.2}, {'unknown': 0.2}])
def test_scenario_http_rejects_invalid_or_coerced_weights(client, probabilities):
    c, _ = client
    response = c.post('/api/modules/20/meta/scenarios', json={'objective': 'fixture', 'drivers': ['fixture'], 'probabilities': probabilities})
    assert response.status_code == 422


def test_risk_register_http_control_gaps_and_complete_review_not_approval(client):
    c, _ = client
    risk = {'id': 'deadline', 'cause': 'Miss payroll cutoff', 'severity': 8, 'occurrence': 3, 'detection': 4,
            'owner': '', 'mitigation': 'Alert before cutoff', 'test': '', 'evidence': []}
    response = c.post('/api/modules/20/meta/premortem/register', json={'goal': 'Export payroll', 'risks': [risk]})
    assert response.status_code == 200
    assert response.json()['risks'][0]['missing_controls'] == ['owner', 'test', 'evidence']
    risk.update(owner='ops lead', test='Replay cutoff backlog', evidence=['supplied-test-reference'])
    complete = c.post('/api/modules/20/meta/premortem/register', json={'goal': 'Export payroll', 'risks': [risk]}).json()
    assert complete['ready_for_owner_review'] is True
    assert complete['evidence_verified'] is False and complete['external_actions_executed'] is False
    risk['severity'] = True
    assert c.post('/api/modules/20/meta/premortem/register', json={'goal': 'fixture', 'risks': [risk]}).status_code == 422
