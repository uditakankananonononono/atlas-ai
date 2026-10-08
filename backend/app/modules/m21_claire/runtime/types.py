from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator


class ToolRisk(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ReplanRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    steps: list[str] = Field(min_length=1, max_length=8)


class AgentDecision(BaseModel):
    """Strict model response: exactly one of tool_call, replan or final."""
    thought: str = ""
    tool_call: ToolCall | None = None
    final: str | None = None
    replan: ReplanRequest | None = None

    @model_validator(mode="after")
    def one_action(self) -> "AgentDecision":
        if sum(v is not None for v in (self.tool_call, self.final, self.replan)) != 1:
            raise ValueError("provide exactly one of tool_call, replan or final")
        return self


class ToolReceipt(BaseModel):
    step: int
    tool: str
    arguments: dict[str, Any]
    ok: bool
    content: Any = None
    error: str | None = None
    replayed: bool = False  # True when the stored result of an already-committed identical call was returned


class Refusal(BaseModel):
    step: int
    tool: str
    risk: str | None
    reason: str  # unknown_tool | policy_denied | risk_changed | blocked | approval_required
    gates: list[str] = Field(default_factory=list)
    digest: str | None = None
    arguments: dict[str, Any] | None = None


class RunReport(BaseModel):
    """Engine output. Evidence only: it never marks a goal complete by itself."""
    final: str | None = None
    stop_reason: str  # final | step_limit | replan_limit | cancelled | model_unavailable | model_invalid_output | lease_lost
    steps_used: int
    receipts: list[ToolReceipt] = Field(default_factory=list)
    refusals: list[Refusal] = Field(default_factory=list)
