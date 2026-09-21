from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from app.modules.m14_project_builder.routes import router as project_router
from app.modules.m14_project_builder.semantic_engines_575_584 import run as engine_run
from app.modules.m17_advice_essay.communication_coaching import CommunicationCoach
from app.modules.m17_advice_essay.collaboration_coaching import CollaborationCoach
from app.modules.m17_advice_essay.trust_wellbeing_coaching import TrustWellbeingCoach
from app.modules.m17_advice_essay.schemas import (
    CommunicationCoachingRequest, CommunicationSkill,
    CollaborationCoachingRequest, CollaborationSkill,
    TrustWellbeingCoachingRequest, TrustWellbeingSkill,
)
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import ROWS, execute
from app.modules.m20_general_cognitive_worker.cognitive_learning_860_909 import execute as cognitive_execute, STAGES


def test_engine_executes_and_reports_method_specific_evaluation():
    result = engine_run(582, {"text": "compress me " * 20})
    assert result["result"]["round_trip_verified"] is True
    assert result["evaluation"]["executed"] is True
    assert result["uncertainty"]["limitations"]
    with pytest.raises(ValueError):
        engine_run(577, {"bodies": [], "dt_seconds": 0, "steps": 1})


def test_engine_route_is_mounted():
    paths = {route.path for route in project_router.routes if hasattr(route, "path")}
    assert "/project-builder/semantic-engines-575-584/{row_id}" in paths


@pytest.mark.parametrize("skill", list(CommunicationSkill))
def test_every_communication_method_is_calibrated(skill):
    response = CommunicationCoach().coach(CommunicationCoachingRequest(
        owner_id=uuid4(), skill=skill, context="A real discussion", goal="Reach clarity",
        audience="colleague", known_facts=["A deadline was stated"], draft="An evidence based draft because facts matter",
    ))
    assert response.evaluation["row_id"] == 710 + list(CommunicationSkill).index(skill)
    assert response.uncertainty["unknowns"]
    assert response.external_action_proposed is False


@pytest.mark.parametrize("skill", list(CollaborationSkill))
def test_every_collaboration_method_is_calibrated(skill):
    response = CollaborationCoach().coach(CollaborationCoachingRequest(
        owner_id=uuid4(), skill=skill, context="Workshop", objective="Make a decision",
        participants=["A", "B"], known_facts=["Both accepted the agenda"], proposal_or_argument="Option A because evidence supports it",
    ))
    assert response.evaluation["row_id"] == 741 + list(CollaborationSkill).index(skill)
    assert "unheard perspectives" in response.uncertainty["unknowns"]


@pytest.mark.parametrize("skill", list(TrustWellbeingSkill))
def test_every_trust_wellbeing_method_preserves_clinical_boundary(skill):
    response = TrustWellbeingCoach().coach(TrustWellbeingCoachingRequest(
        owner_id=uuid4(), skill=skill, context="Personal reflection", goal="Try a small step",
    ))
    assert response.evaluation["row_id"] == 771 + list(TrustWellbeingSkill).index(skill)
    assert response.uncertainty["level"] == "high"
    assert "not emergency" in response.escalation_boundary


@pytest.mark.parametrize("row", range(810, 860))
def test_learning_rows_have_evaluation_and_uncertainty(row):
    name = ROWS[row]
    payload = {"source": {"title": "Evidence", "url": "https://example.test/source"}}
    family_payload = {
        810: {"objective": "learn", "items": [{"id": "a", "quality": 4}]},
    }
    payload.update(family_payload.get(row, {}))
    if row <= 832:
        payload.setdefault("objective", "learn")
        if row == 811: payload["skills"] = ["a", "b"]
        if row == 816: payload["examples"] = [{"feature": "x"}]
        if row == 820: payload["chunks"] = [{"label": "x", "elements": [1]}]
        if row == 825: payload["goal"] = {"specific": "x"}
        if row == 826: payload["records"] = [{"value": 1}]
        if row in (827, 828): payload.update(criteria=["c"], ratings={"c": 1})
        if row in (829, 830, 831): payload["items"] = [{"objective_id": "o"}]
    elif row <= 837:
        payload.update(source_case={"features": ["x"]}, target_case={"features": ["x"]})
    elif row <= 855:
        if row == 838: payload["rules"] = [{"if": [], "then": "x"}]
        if row == 841: payload["values"] = [1, 2]
        if row == 843: payload["events"] = [{"time": 1}]
        if row == 846: payload.update(prior=.5, likelihood_given_h=.8, likelihood_given_not_h=.2)
        if row == 847: payload["memberships"] = {"x": .5}
    else:
        payload["problem"] = "solve this"
    response = execute(name, payload)
    assert response["row_id"] == row
    assert response["evaluation"]["independent_verification_required"] is True
    assert response["uncertainty"]["calibration"]


def test_critical_thinking_row_861_is_method_specific_and_incomplete_when_evidence_missing():
    payload = {"sources": [{"source_id": "s1", "observed_at": "2026-09-21"}], "inputs": {"claim": "x", "evidence": ["e"]}}
    result = cognitive_execute(861, payload)
    assert result["evidence_gaps"] == ["assumptions", "alternatives", "judgment"]
    assert result["evaluation"]["stage_coverage"] == pytest.approx(0.4)
    assert result["uncertainty"]["level"] == "high"
