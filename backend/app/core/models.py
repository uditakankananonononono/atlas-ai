from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"

class GoalRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=2000)

class PlannedStep(BaseModel):
    module_id: int
    module_name: str
    action: str
    requires_approval: bool
    operation: str
    payload: dict[str, Any]
    evidence: list[dict[str, Any]] = Field(default_factory=list)

class ApprovalRequest(BaseModel):
    id: str
    module_id: int
    action_type: str
    payload: dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING

class GoalPlan(BaseModel):
    goal: str
    steps: list[PlannedStep]
    approval_requests: list[ApprovalRequest]

class ApprovalDecision(BaseModel):
    decision: ApprovalStatus

class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=20_000)
    provider: str = "openai"
    model: str | None = None

class GenerateResponse(BaseModel):
    provider: str
    model: str
    text: str
