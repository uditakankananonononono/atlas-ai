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
