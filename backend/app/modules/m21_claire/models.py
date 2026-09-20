"""Domain models for Claire's consent, planning, and reviewed execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanState(str, Enum):
    DRAFT = "draft"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepState(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class Evidence:
    source: str
    reference: str
    captured_at: datetime
    excerpt: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.reference.strip():
            raise ValueError("evidence requires source and reference")
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Preference:
    key: str
    value: Any
    evidence: tuple[Evidence, ...]
    allowed_uses: frozenset[str]
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_usable(self, purpose: str, now: datetime) -> bool:
        return bool(self.evidence) and purpose in self.allowed_uses and not self.revoked_at and (
            self.expires_at is None or now < self.expires_at
        )


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    decision_id: str
    subject: str
    choice: Any
    purpose: str
    evidence: tuple[Evidence, ...]
    consent_scopes: frozenset[str]
    decided_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_usable(self, *, scope: str, purpose: str, now: datetime) -> bool:
        return (
            bool(self.evidence)
            and scope in self.consent_scopes
            and self.purpose == purpose
            and self.revoked_at is None
            and (self.expires_at is None or now < self.expires_at)
        )


@dataclass(frozen=True, slots=True)
class ActionRequest:
    module: str
    action: str
    parameters: Mapping[str, Any]
    purpose: str
    risk: RiskLevel = RiskLevel.LOW
    dependencies: tuple[str, ...] = ()
    action_id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def capability(self) -> str:
        return f"{self.module}.{self.action}"


@dataclass(frozen=True, slots=True)
class ReviewSnapshot:
    """Immutable payload the user reviewed; its digest binds later execution."""

    plan_id: str
    action_id: str
    capability: str
    purpose: str
    parameters: Mapping[str, Any]
    risk: RiskLevel
    digest: str


@dataclass(frozen=True, slots=True)
class Approval:
    approval_id: str
    review_digest: str
    approver: str
    approved_at: datetime
    expires_at: datetime | None = None

    def valid_at(self, now: datetime) -> bool:
        return self.expires_at is None or now < self.expires_at


@dataclass(slots=True)
class PlanStep:
    request: ActionRequest
    state: StepState = StepState.PENDING
    output: Any = None
    error: str | None = None


@dataclass(slots=True)
class ExecutionPlan:
    goal: str
    steps: list[PlanStep]
    plan_id: str = field(default_factory=lambda: str(uuid4()))
    state: PlanState = PlanState.DRAFT
    created_at: datetime = field(default_factory=utcnow)
    approvals: dict[str, Approval] = field(default_factory=dict)

    def step(self, action_id: str) -> PlanStep:
        for item in self.steps:
            if item.request.action_id == action_id:
                return item
        raise KeyError(action_id)

    def ordered_requests(self) -> Sequence[ActionRequest]:
        return tuple(step.request for step in self.steps)
