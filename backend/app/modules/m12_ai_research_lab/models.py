from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

class TaskType(str, Enum):
    RESEARCH="research"; DRAFT="draft"; CRITIQUE="critique"; REVISE="revise"; VISION="vision"; CODE="code"

@dataclass(frozen=True)
class ModelCapability:
    model_id: str
    task_types: frozenset[TaskType]
    max_output_tokens: int
    cents_per_1k_tokens: float
    p95_latency_ms: int
    quality: float
    supports_logprobs: bool = False
    enabled: bool = True

@dataclass(frozen=True)
class RouteRequest:
    task_type: TaskType
    output_tokens: int
    budget_cents: float
    latency_tolerance_ms: int
    tenant_id: str
    required_model_ids: frozenset[str] = frozenset()

@dataclass
class ModelResult:
    text: str
    model_id: str
    confidence: float | None = None
    logprobs: list[float] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

class ModelProvider(Protocol):
    async def generate(self, *, model_id: str, prompt: str, context: dict[str, Any]) -> ModelResult: ...
