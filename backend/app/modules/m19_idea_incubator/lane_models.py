"""Schemas and domain types for the Idea Incubator module."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IdeaStage(str, Enum):
    CAPTURED = "captured"
    DISCOVERY = "discovery"
    VALIDATION = "validation"
    EXPERIMENTING = "experimenting"
    APPROVED = "approved"
    PARKED = "parked"
    REJECTED = "rejected"


class EvidenceKind(str, Enum):
    INTERVIEW = "interview"
    MARKET_DATA = "market_data"
    COMPETITOR = "competitor"
    TECHNICAL = "technical"
    REGULATORY = "regulatory"
    EXPERIMENT = "experiment"
    OTHER = "other"


class EvidencePolarity(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class ExperimentStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    CANCELLED = "cancelled"


class FeasibilityOutcome(str, Enum):
    PASS = "pass"
    CONDITIONAL = "conditional"
    FAIL = "fail"


class IdeaCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    problem: str = Field(min_length=1, max_length=5000)
    proposed_solution: str = Field(min_length=1, max_length=5000)
    owner_id: str = Field(min_length=1, max_length=200)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "problem", "proposed_solution", "owner_id")
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class Idea(IdeaCreate):
    id: UUID = Field(default_factory=uuid4)
    stage: IdeaStage = IdeaStage.CAPTURED
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    version: int = 1


class EvidenceCreate(BaseModel):
    kind: EvidenceKind
    claim: str = Field(min_length=1, max_length=5000)
    source: str = Field(min_length=1, max_length=2000)
    polarity: EvidencePolarity
    strength: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    observed_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("claim", "source")
    def strip_evidence_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class Evidence(EvidenceCreate):
    id: UUID = Field(default_factory=uuid4)
    idea_id: UUID
    created_at: datetime = Field(default_factory=utcnow)


class DimensionScore(BaseModel):
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    notes: str = Field(default="", max_length=3000)


class FeasibilityTestCreate(BaseModel):
    desirability: DimensionScore
    technical: DimensionScore
    viability: DimensionScore
    strategic_fit: DimensionScore
    compliance: DimensionScore
    weights: dict[str, float] | None = None
    blockers: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class FeasibilityTest(FeasibilityTestCreate):
    id: UUID = Field(default_factory=uuid4)
    idea_id: UUID
    weighted_score: float
    weighted_confidence: float
    outcome: FeasibilityOutcome
    tested_at: datetime = Field(default_factory=utcnow)


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    hypothesis: str = Field(min_length=1, max_length=3000)
    method: str = Field(min_length=1, max_length=5000)
    metric: str = Field(min_length=1, max_length=500)
    target: float
    unit: str = Field(default="", max_length=80)
    deadline: datetime | None = None


class ExperimentUpdate(BaseModel):
    status: ExperimentStatus
    observed_value: float | None = None
    learnings: str = Field(default="", max_length=5000)


class Experiment(ExperimentCreate):
    id: UUID = Field(default_factory=uuid4)
    idea_id: UUID
    status: ExperimentStatus = ExperimentStatus.PLANNED
    observed_value: float | None = None
    learnings: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DecisionCreate(BaseModel):
    to_stage: IdeaStage
    rationale: str = Field(min_length=1, max_length=5000)
    actor_id: str = Field(min_length=1, max_length=200)
    expected_version: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    idea_id: UUID
    from_stage: IdeaStage
    to_stage: IdeaStage
    rationale: str
    actor_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    decided_at: datetime = Field(default_factory=utcnow)
    idea_version: int


class EvidenceSummary(BaseModel):
    supporting_count: int
    contradicting_count: int
    neutral_count: int
    support_score: float
    contradiction_score: float
    net_score: float
    confidence: float


class IdeaDossier(BaseModel):
    idea: Idea
    evidence: list[Evidence]
    evidence_summary: EvidenceSummary
    feasibility_tests: list[FeasibilityTest]
    experiments: list[Experiment]
    decisions: list[Decision]
