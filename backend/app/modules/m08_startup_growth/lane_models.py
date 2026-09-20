"""Domain models for Atlas module 08: startup growth."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EvidenceKind(StrEnum):
    INTERVIEW = "interview"
    SUPPORT = "support"
    SURVEY = "survey"
    SALES = "sales"
    REVIEW = "review"
    USABILITY = "usability"


@dataclass(frozen=True, slots=True)
class Variant:
    key: str
    weight: float
    description: str = ""


@dataclass(slots=True)
class Experiment:
    id: str
    name: str
    hypothesis: str
    primary_metric: str
    variants: tuple[Variant, ...]
    minimum_sample_size: int
    guardrail_metrics: tuple[str, ...] = ()
    status: ExperimentStatus = ExperimentStatus.DRAFT
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class MetricObservation:
    event_id: str
    experiment_id: str
    subject_id: str
    variant_key: str
    metric: str
    value: float
    occurred_at: datetime = field(default_factory=utcnow)
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FunnelStep:
    key: str
    name: str


@dataclass(slots=True)
class Funnel:
    id: str
    name: str
    steps: tuple[FunnelStep, ...]
    created_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class FunnelEvent:
    event_id: str
    funnel_id: str
    subject_id: str
    step_key: str
    occurred_at: datetime = field(default_factory=utcnow)
    segment: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class CustomerEvidence:
    id: str
    kind: EvidenceKind
    text: str
    source: str
    customer_id: str | None = None
    tags: tuple[str, ...] = ()
    sentiment: float | None = None
    occurred_at: datetime = field(default_factory=utcnow)
    created_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class MeasurementDefinition:
    key: str
    name: str
    description: str
    owner: str
    formula: str
    target: float | None = None
    direction: str = "increase"
