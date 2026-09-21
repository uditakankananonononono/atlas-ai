from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m20_general_cognitive_worker.specialized_domain import (
    EXPECTED_ROWS,
    SpecializedDomainError,
    analyze_specialized_domain,
)
from app.modules.m20_general_cognitive_worker.specialized_domain_routes import router

SCOPE = {"tenant_id": "school-a", "actor_id": "reviewer-7"}
SOURCE = {"title": "Teaching evidence", "url": "https://example.edu/evidence"}


def run(row_id, data, options=None, **scope):
    return analyze_specialized_domain(
        row_id=row_id, data=data, options=options, **(scope or SCOPE)
    )


def test_registry_has_exact_m20_family_c_rows_without_silent_gaps():
    assert EXPECTED_ROWS == frozenset((*range(1310, 1360), *range(1410, 1560)))
    assert len(EXPECTED_ROWS) == 200


def test_finance_delegates_to_real_algorithm_and_preserves_model_limits():
    out = run(1340, {"spot": 100, "strike": 100, "time": 1, "rate": .05, "volatility": .2})
    assert out.domain == "finance" and out.capability == "black_scholes"
    assert out.result["price"] == pytest.approx(10.4506, rel=1e-3)
    assert out.tenant_id == "school-a" and out.evaluation.human_review_required
    assert out.side_effects == () and out.uncertainty.input_evidence_only


def test_foundation_education_preserves_evidence_and_review_contract():
    out = run(1410, {
        "topic": "Fractions", "learners": {"grade": 5},
        "objectives": [{"id": "o1", "statement": "Compare fractions"}],
        "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}],
        "duration_minutes": 45, "source": SOURCE,
    })
    assert out.domain == "education" and out.result["unassessed_objective_ids"] == []
    assert out.evaluation.status == "draft_for_review" and "objective_assessment_alignment" in out.evaluation.checks


def test_advanced_education_runs_risk_model_without_turning_it_into_fact():
    out = run(1461, {
        "features": {"absence": 2}, "coefficients": {"intercept": -1, "absence": 1},
        "sources": [{"source_id": "model-card-1", "observed_at": datetime.now(timezone.utc).isoformat()}],
    })
    assert out.result["dropout_risk_probability"] == pytest.approx(.7311)
    assert out.evaluation.human_review_required
    assert "No autonomous grading" in out.limits[0]


def test_engineering_runs_equation_but_never_claims_physical_verification():
    out = run(1515, {"sigma_x": 100, "sigma_y": 0, "tau_xy": 0, "yield_strength": 250})
    assert out.domain == "engineering" and out.result["factor_of_safety"] == 2.5
    assert not out.evaluation.externally_verified
    assert "model-form and boundary-condition choices" in out.uncertainty.drivers


def test_scope_and_input_failures_are_loud_and_do_not_cross_tenants():
    with pytest.raises(SpecializedDomainError): run(1360, {})
    with pytest.raises(SpecializedDomainError): run(1340, {}, tenant_id="", actor_id="a")
    with pytest.raises(ValueError): run(1514, {})
    left = run(1514, {"heat_w": 5, "ambient_c": 20, "thermal_resistances_k_per_w": [.2]})
    right = run(1514, {"heat_w": 5, "ambient_c": 20, "thermal_resistances_k_per_w": [.2]}, tenant_id="school-b", actor_id="b")
    assert left.result == right.result and left.tenant_id != right.tenant_id


def test_http_boundary_requires_tenant_and_actor_and_returns_typed_envelope():
    app = FastAPI(); app.include_router(router, prefix="/api/modules/20")
    client = TestClient(app)
    body = {"row_id": 1514, "data": {"heat_w": 10, "ambient_c": 20, "thermal_resistances_k_per_w": [.2, .3]}}
    assert client.post("/api/modules/20/specialized-domain/analyze", json=body).status_code == 422
    response = client.post(
        "/api/modules/20/specialized-domain/analyze", json=body,
        headers={"x-atlas-tenant": "tenant-1", "x-atlas-actor": "engineer-1"},
    )
    assert response.status_code == 200
    value = response.json()
    assert value["tenant_id"] == "tenant-1" and value["result"]["predicted_hot_temperature_c"] == 25
    assert value["side_effects"] == []
