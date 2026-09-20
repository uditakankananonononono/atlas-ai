from uuid import uuid4

import pytest

from app.modules.m19_idea_incubator.lane_models import (
    DecisionCreate, DimensionScore, EvidenceCreate, EvidenceKind, EvidencePolarity,
    ExperimentCreate, ExperimentStatus, ExperimentUpdate, FeasibilityOutcome,
    FeasibilityTestCreate, IdeaCreate, IdeaStage,
)
from app.modules.m19_idea_incubator.lane_repository import ConflictError, InMemoryIdeaRepository, NotFoundError
from app.modules.m19_idea_incubator.lane_service import IdeaIncubatorService, ValidationError


def service_and_idea():
    service = IdeaIncubatorService(InMemoryIdeaRepository())
    idea = service.create_idea(IdeaCreate(
        title="Verified scholarship matching", problem="Students miss good deadlines",
        proposed_solution="Match profiles to verified programs", owner_id="u-1",
        tags=["education"],
    ))
    return service, idea


def evidence(polarity=EvidencePolarity.SUPPORTS, strength=.8, confidence=.9):
    return EvidenceCreate(kind=EvidenceKind.INTERVIEW, claim="Students need it",
        source="interview-001", polarity=polarity, strength=strength, confidence=confidence)


def feasibility(score=80, confidence=.8, blockers=None, weights=None):
    dimension = DimensionScore(score=score, confidence=confidence, notes="measured")
    return FeasibilityTestCreate(
        desirability=dimension, technical=dimension, viability=dimension,
        strategic_fit=dimension, compliance=dimension, blockers=blockers or [],
        weights=weights,
    )


def decision(stage, version=None):
    return DecisionCreate(to_stage=stage, rationale="Evidence supports moving", actor_id="owner", expected_version=version)


def test_create_list_and_repository_defensive_copy():
    service, idea = service_and_idea()
    fetched = service.get_idea(idea.id)
    fetched.title = "mutated"
    assert service.get_idea(idea.id).title == "Verified scholarship matching"
    assert service.list_ideas(IdeaStage.CAPTURED)[0].id == idea.id
    assert service.list_ideas(IdeaStage.APPROVED) == []


def test_missing_idea_raises_not_found():
    with pytest.raises(NotFoundError):
        IdeaIncubatorService().get_idea(uuid4())


def test_evidence_scoring_accounts_for_support_and_contradiction():
    service, idea = service_and_idea()
    service.add_evidence(idea.id, evidence(strength=.8, confidence=.5))
    service.add_evidence(idea.id, evidence(strength=.5, confidence=.8))
    service.add_evidence(idea.id, evidence(EvidencePolarity.CONTRADICTS, .5, .5))
    summary = service.summarize_evidence(idea.id)
    assert summary.supporting_count == 2
    assert summary.contradicting_count == 1
    assert summary.support_score == .64  # 1 - (1-.4)^2
    assert summary.contradiction_score == .25
    assert summary.net_score == .39


def test_feasibility_pass_conditional_fail_and_weight_validation():
    service, idea = service_and_idea()
    assert service.run_feasibility_test(idea.id, feasibility()).outcome == FeasibilityOutcome.PASS
    assert service.run_feasibility_test(idea.id, feasibility(60)).outcome == FeasibilityOutcome.CONDITIONAL
    assert service.run_feasibility_test(idea.id, feasibility(80, blockers=["license"])).outcome == FeasibilityOutcome.FAIL
    with pytest.raises(ValidationError, match="exactly"):
        service.run_feasibility_test(idea.id, feasibility(weights={"technical": 1.0}))
    with pytest.raises(ValidationError, match="sum to 1"):
        service.run_feasibility_test(idea.id, feasibility(weights={name: .3 for name in (
            "desirability", "technical", "viability", "strategic_fit", "compliance")}))


def test_a_single_hard_feasibility_failure_forces_fail():
    service, idea = service_and_idea()
    data = feasibility(90)
    data.compliance = DimensionScore(score=20, confidence=.9)
    assert service.run_feasibility_test(idea.id, data).outcome == FeasibilityOutcome.FAIL


def test_experiment_lifecycle_and_immutability():
    service, idea = service_and_idea()
    exp = service.create_experiment(idea.id, ExperimentCreate(
        name="Landing page", hypothesis="10 percent convert", method="Traffic test",
        metric="conversion", target=10, unit="percent",
    ))
    running = service.update_experiment(idea.id, exp.id, ExperimentUpdate(status=ExperimentStatus.RUNNING))
    assert running.status == ExperimentStatus.RUNNING
    with pytest.raises(ValidationError, match="observed_value"):
        service.update_experiment(idea.id, exp.id, ExperimentUpdate(status=ExperimentStatus.SUCCEEDED))
    done = service.update_experiment(idea.id, exp.id, ExperimentUpdate(
        status=ExperimentStatus.SUCCEEDED, observed_value=13, learnings="Demand exists"))
    assert done.observed_value == 13
    with pytest.raises(ConflictError, match="immutable"):
        service.update_experiment(idea.id, exp.id, ExperimentUpdate(status=ExperimentStatus.RUNNING))


def test_invalid_experiment_transition_and_unknown_experiment():
    service, idea = service_and_idea()
    exp = service.create_experiment(idea.id, ExperimentCreate(
        name="Test", hypothesis="H", method="M", metric="x", target=1))
    with pytest.raises(ValidationError, match="invalid experiment transition"):
        service.update_experiment(idea.id, exp.id, ExperimentUpdate(
            status=ExperimentStatus.SUCCEEDED, observed_value=2))
    with pytest.raises(NotFoundError):
        service.update_experiment(idea.id, uuid4(), ExperimentUpdate(status=ExperimentStatus.RUNNING))


def test_stage_gates_and_decision_audit_history():
    service, idea = service_and_idea()
    first = service.record_decision(idea.id, decision(IdeaStage.DISCOVERY, idea.version))
    assert first.from_stage == IdeaStage.CAPTURED
    assert first.idea_version == 2
    with pytest.raises(ValidationError, match="evidence"):
        service.record_decision(idea.id, decision(IdeaStage.VALIDATION))
    service.add_evidence(idea.id, evidence())
    second = service.record_decision(idea.id, decision(IdeaStage.VALIDATION, 2))
    assert second.from_stage == IdeaStage.DISCOVERY
    assert service.get_idea(idea.id).version == 3
    with pytest.raises(ValidationError, match="defined experiment"):
        service.record_decision(idea.id, decision(IdeaStage.EXPERIMENTING))


def test_optimistic_version_conflict_and_invalid_transition():
    service, idea = service_and_idea()
    with pytest.raises(ConflictError, match="version changed"):
        service.record_decision(idea.id, decision(IdeaStage.DISCOVERY, 99))
    with pytest.raises(ValidationError, match="invalid idea transition"):
        service.record_decision(idea.id, decision(IdeaStage.APPROVED))


def test_approval_requires_positive_evidence_passing_latest_test_and_finished_experiments():
    service, idea = service_and_idea()
    service.record_decision(idea.id, decision(IdeaStage.DISCOVERY))
    service.add_evidence(idea.id, evidence())
    service.record_decision(idea.id, decision(IdeaStage.VALIDATION))
    exp = service.create_experiment(idea.id, ExperimentCreate(
        name="Demand", hypothesis="Users pay", method="Preorders", metric="orders", target=5))
    service.run_feasibility_test(idea.id, feasibility())
    with pytest.raises(ValidationError, match="completed"):
        service.record_decision(idea.id, decision(IdeaStage.APPROVED))
    service.update_experiment(idea.id, exp.id, ExperimentUpdate(status=ExperimentStatus.RUNNING))
    service.update_experiment(idea.id, exp.id, ExperimentUpdate(
        status=ExperimentStatus.SUCCEEDED, observed_value=7, learnings="Target beaten"))
    approved = service.record_decision(idea.id, decision(IdeaStage.APPROVED))
    assert approved.to_stage == IdeaStage.APPROVED
    assert service.dossier(idea.id).idea.stage == IdeaStage.APPROVED
    with pytest.raises(ValidationError, match="terminal ideas"):
        service.create_experiment(idea.id, ExperimentCreate(
            name="Late", hypothesis="h", method="m", metric="x", target=1))


def test_latest_feasibility_result_is_authoritative():
    service, idea = service_and_idea()
    service.record_decision(idea.id, decision(IdeaStage.DISCOVERY))
    service.add_evidence(idea.id, evidence())
    service.record_decision(idea.id, decision(IdeaStage.VALIDATION))
    service.run_feasibility_test(idea.id, feasibility())
    service.run_feasibility_test(idea.id, feasibility(40))
    with pytest.raises(ValidationError, match="passing latest"):
        service.record_decision(idea.id, decision(IdeaStage.APPROVED))


def test_dossier_contains_complete_audit_material():
    service, idea = service_and_idea()
    ev = service.add_evidence(idea.id, evidence())
    test = service.run_feasibility_test(idea.id, feasibility())
    dossier = service.dossier(idea.id)
    assert dossier.idea.id == idea.id
    assert dossier.evidence[0].id == ev.id
    assert dossier.feasibility_tests[0].id == test.id
    assert dossier.evidence_summary.net_score > 0
