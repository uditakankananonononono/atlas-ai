"""Pydantic request/response models for the Human Approval Center API."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.models import ApprovalStatus

DEFAULT_USER_ID = "default"


class ApprovalSubmit(BaseModel):
    """Body for proposing a gated action. Nothing executes; this only queues the ask."""

    module_id: int
    action_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    user_id: str = Field(default=DEFAULT_USER_ID, min_length=1, max_length=120)
    ttl_seconds: int | None = Field(default=None, gt=0)


class ApprovalView(BaseModel):
    """Full state of one approval request as stored."""

    id: str
    module_id: int
    action_type: str
    payload: dict[str, Any]
    user_id: str
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime | None
    decided_at: datetime | None
    approved_by: str | None


class ApprovalDecisionIn(BaseModel):
    """A human decision. Only approved/denied can be submitted by a person."""

    decision: Literal["approved", "denied"]
    decided_by: str = Field(min_length=1, max_length=120)


class ApprovalEventView(BaseModel):
    """One immutable audit event on an approval request."""

    event: str
    actor: str | None
    at: datetime


class ExpireResult(BaseModel):
    """Result of sweeping overdue pending requests into the expired state."""

    expired_ids: list[str]

class PolicyUpsert(BaseModel):
    """Policy controlling whether a matching action is allowed, denied, or reviewed."""
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    action_pattern: str = Field(default="*", min_length=1, max_length=200)
    module_id: int | None = None
    effect: Literal["allow", "deny", "review"]
    priority: int = 0
    enabled: bool = True
    conditions: dict[str, Any] = Field(default_factory=dict)
    review_ttl_seconds: int = Field(default=3600, gt=0)


class PolicyView(PolicyUpsert):
    tenant_id: str
    created_at: datetime
    updated_at: datetime


class GateCheck(BaseModel):
    """Evaluate policy and, when required, durably create a review request."""
    module_id: int
    action_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    user_id: str = Field(default=DEFAULT_USER_ID, min_length=1, max_length=120)
    idempotency_key: str | None = Field(default=None, max_length=200)


class GateResult(BaseModel):
    decision: Literal["allow", "deny", "review"]
    allowed: bool
    reason: str
    policy_id: str | None = None
    approval: ApprovalView | None = None


class EffectConsume(BaseModel):
    """Consume an approved request immediately before its exact external effect."""
    module_id: int
    action_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    user_id: str = Field(default=DEFAULT_USER_ID, min_length=1, max_length=120)
    effect_id: str = Field(min_length=1, max_length=200)


class EffectPermit(BaseModel):
    approval_id: str
    effect_id: str
    allowed: bool
    consumed_at: datetime
