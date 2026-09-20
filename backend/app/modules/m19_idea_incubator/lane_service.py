"""Idea incubation domain service with evidence, feasibility and stage gates."""
from __future__ import annotations

from math import fsum
from uuid import UUID

from .lane_models import (
    Decision, DecisionCreate, Evidence, EvidenceCreate, EvidencePolarity,
    EvidenceSummary, Experiment, ExperimentCreate, ExperimentStatus,
    ExperimentUpdate, FeasibilityOutcome, FeasibilityTest,
    FeasibilityTestCreate, Idea, IdeaCreate, IdeaDossier, IdeaStage, utcnow,
)
from .lane_repository import ConflictError, InMemoryIdeaRepository, NotFoundError


class ValidationError(ValueError):
    pass


DIMENSIONS = ("desirability", "technical", "viability", "strategic_fit", "compliance")
DEFAULT_WEIGHTS = {
    "desirability": 0.25, "technical": 0.20, "viability": 0.20,
    "strategic_fit": 0.15, "compliance": 0.20,
}
ALLOWED_TRANSITIONS = {
    IdeaStage.CAPTURED: {IdeaStage.DISCOVERY, IdeaStage.PARKED, IdeaStage.REJECTED},
    IdeaStage.DISCOVERY: {IdeaStage.VALIDATION, IdeaStage.PARKED, IdeaStage.REJECTED},
    IdeaStage.VALIDATION: {IdeaStage.EXPERIMENTING, IdeaStage.APPROVED, IdeaStage.PARKED, IdeaStage.REJECTED},
    IdeaStage.EXPERIMENTING: {IdeaStage.VALIDATION, IdeaStage.APPROVED, IdeaStage.PARKED, IdeaStage.REJECTED},
    IdeaStage.PARKED: {IdeaStage.DISCOVERY, IdeaStage.REJECTED},
    IdeaStage.APPROVED: set(),
    IdeaStage.REJECTED: set(),
}
TERMINAL_EXPERIMENTS = {
    ExperimentStatus.SUCCEEDED, ExperimentStatus.FAILED,
    ExperimentStatus.INCONCLUSIVE, ExperimentStatus.CANCELLED,
}


class IdeaIncubatorService:
    def __init__(self, repository: InMemoryIdeaRepository | None = None) -> None:
        self.repository = repository or InMemoryIdeaRepository()

    def create_idea(self, data: IdeaCreate) -> Idea:
        return self.repository.add_idea(Idea(**data.model_dump()))

    def get_idea(self, idea_id: UUID) -> Idea:
        return self.repository.get_idea(idea_id)

    def list_ideas(self, stage: IdeaStage | None = None) -> list[Idea]:
        ideas = self.repository.list_ideas()
        return [x for x in ideas if stage is None or x.stage == stage]

    def add_evidence(self, idea_id: UUID, data: EvidenceCreate) -> Evidence:
        self.repository.get_idea(idea_id)
        return self.repository.add_evidence(Evidence(idea_id=idea_id, **data.model_dump()))

    def summarize_evidence(self, idea_id: UUID) -> EvidenceSummary:
        items = self.repository.list_evidence(idea_id)
        by_polarity = {
            polarity: [x for x in items if x.polarity == polarity]
            for polarity in EvidencePolarity
        }
        def weighted(group: list[Evidence]) -> float:
            # Independent evidence is capped at 1 using complementary probabilities.
            residual = 1.0
            for item in group:
                residual *= 1.0 - (item.strength * item.confidence)
            return 1.0 - residual
        support = weighted(by_polarity[EvidencePolarity.SUPPORTS])
        contradiction = weighted(by_polarity[EvidencePolarity.CONTRADICTS])
        confidence = 0.0 if not items else fsum(x.confidence for x in items) / len(items)
        return EvidenceSummary(
            supporting_count=len(by_polarity[EvidencePolarity.SUPPORTS]),
            contradicting_count=len(by_polarity[EvidencePolarity.CONTRADICTS]),
            neutral_count=len(by_polarity[EvidencePolarity.NEUTRAL]),
            support_score=round(support, 4), contradiction_score=round(contradiction, 4),
            net_score=round(support - contradiction, 4), confidence=round(confidence, 4),
        )

    def run_feasibility_test(self, idea_id: UUID, data: FeasibilityTestCreate) -> FeasibilityTest:
        self.repository.get_idea(idea_id)
        weights = data.weights or DEFAULT_WEIGHTS
        if set(weights) != set(DIMENSIONS):
            raise ValidationError(f"weights must contain exactly: {', '.join(DIMENSIONS)}")
        if any(value < 0 for value in weights.values()) or abs(sum(weights.values()) - 1.0) > 1e-6:
            raise ValidationError("weights must be non-negative and sum to 1")
        scores = {name: getattr(data, name) for name in DIMENSIONS}
        weighted_score = fsum(scores[name].score * weights[name] for name in DIMENSIONS)
        weighted_confidence = fsum(scores[name].confidence * weights[name] for name in DIMENSIONS)
        hard_failure = any(scores[name].score < 30 for name in DIMENSIONS)
        if data.blockers or hard_failure or weighted_score < 50:
            outcome = FeasibilityOutcome.FAIL
        elif weighted_score >= 70 and weighted_confidence >= 0.6:
            outcome = FeasibilityOutcome.PASS
        else:
            outcome = FeasibilityOutcome.CONDITIONAL
        normalized = data.model_dump()
        normalized["weights"] = weights
        item = FeasibilityTest(
            idea_id=idea_id, weighted_score=round(weighted_score, 2),
            weighted_confidence=round(weighted_confidence, 4), outcome=outcome, **normalized,
        )
        return self.repository.add_feasibility_test(item)

    def create_experiment(self, idea_id: UUID, data: ExperimentCreate) -> Experiment:
        idea = self.repository.get_idea(idea_id)
        if idea.stage in {IdeaStage.APPROVED, IdeaStage.REJECTED}:
            raise ValidationError("terminal ideas cannot receive new experiments")
        return self.repository.add_experiment(Experiment(idea_id=idea_id, **data.model_dump()))

    def update_experiment(self, idea_id: UUID, experiment_id: UUID, data: ExperimentUpdate) -> Experiment:
        experiments = self.repository.list_experiments(idea_id)
        try:
            item = next(x for x in experiments if x.id == experiment_id)
        except StopIteration as exc:
            raise NotFoundError(f"experiment {experiment_id} not found") from exc
        allowed = {
            ExperimentStatus.PLANNED: {ExperimentStatus.RUNNING, ExperimentStatus.CANCELLED},
            ExperimentStatus.RUNNING: TERMINAL_EXPERIMENTS - {ExperimentStatus.CANCELLED} | {ExperimentStatus.CANCELLED},
        }
        if item.status in TERMINAL_EXPERIMENTS:
            raise ConflictError("completed experiment results are immutable")
        if data.status not in allowed.get(item.status, set()):
            raise ValidationError(f"invalid experiment transition {item.status} -> {data.status}")
        if data.status in {ExperimentStatus.SUCCEEDED, ExperimentStatus.FAILED} and data.observed_value is None:
            raise ValidationError("observed_value is required for succeeded or failed experiments")
        item.status = data.status
        item.observed_value = data.observed_value
        item.learnings = data.learnings
        item.updated_at = utcnow()
        return self.repository.save_experiment(item)

    def record_decision(self, idea_id: UUID, data: DecisionCreate) -> Decision:
        idea = self.repository.get_idea(idea_id)
        if data.expected_version is not None and data.expected_version != idea.version:
            raise ConflictError(f"idea version changed: expected {data.expected_version}, current {idea.version}")
        if data.to_stage not in ALLOWED_TRANSITIONS[idea.stage]:
            raise ValidationError(f"invalid idea transition {idea.stage} -> {data.to_stage}")
        evidence = self.summarize_evidence(idea_id)
        tests = self.repository.list_feasibility_tests(idea_id)
        experiments = self.repository.list_experiments(idea_id)
        if data.to_stage == IdeaStage.VALIDATION and not self.repository.list_evidence(idea_id):
            raise ValidationError("validation requires at least one evidence item")
        if data.to_stage == IdeaStage.EXPERIMENTING and not experiments:
            raise ValidationError("experimenting requires at least one defined experiment")
        if data.to_stage == IdeaStage.APPROVED:
            if not tests or tests[-1].outcome != FeasibilityOutcome.PASS:
                raise ValidationError("approval requires a passing latest feasibility test")
            if evidence.net_score <= 0:
                raise ValidationError("approval requires net-positive evidence")
            if any(x.status not in TERMINAL_EXPERIMENTS for x in experiments):
                raise ValidationError("approval requires every experiment to be completed or cancelled")
        prior_version = idea.version
        from_stage = idea.stage
        idea.stage = data.to_stage
        idea.version += 1
        idea.updated_at = utcnow()
        self.repository.save_idea(idea, expected_version=prior_version)
        decision = Decision(
            idea_id=idea_id, from_stage=from_stage,
            to_stage=data.to_stage, rationale=data.rationale.strip(), actor_id=data.actor_id.strip(),
            metadata=data.metadata, idea_version=idea.version,
        )
        return self.repository.add_decision(decision)

    def dossier(self, idea_id: UUID) -> IdeaDossier:
        return IdeaDossier(
            idea=self.repository.get_idea(idea_id),
            evidence=self.repository.list_evidence(idea_id),
            evidence_summary=self.summarize_evidence(idea_id),
            feasibility_tests=self.repository.list_feasibility_tests(idea_id),
            experiments=self.repository.list_experiments(idea_id),
            decisions=self.repository.list_decisions(idea_id),
        )
