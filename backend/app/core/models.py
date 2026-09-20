from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field

class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"

class GoalRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=2000)
    allow_external_action: bool = False

class PlannedStep(BaseModel):
    module_id: int
    module_name: str
    action: str
    requires_approval: bool

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
