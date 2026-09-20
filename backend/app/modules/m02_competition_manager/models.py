"""Domain models for Competition Manager.

The module deliberately keeps provider-specific browser and storage concerns outside the
core. Every extracted fact carries source evidence, and every irreversible browser step
is represented by an approval-gated staged action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class ApplicationStatus(str, Enum):
    DISCOVERED = "discovered"
    PREPARING = "preparing"
    READY = "ready"
    STAGED = "staged"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ActionState(str, Enum):
    DRAFT = "draft"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {
    ApplicationStatus.ACCEPTED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
}


@dataclass(frozen=True)
class SourceEvidence:
    source_id: str
    quote: str
    start: int
    end: int
    url: Optional[str] = None
    retrieved_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.quote.strip():
            raise ValueError("source_id and quote are required")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("invalid evidence offsets")


@dataclass(frozen=True)
class ExtractedFact:
    kind: str
    value: Any
    evidence: SourceEvidence
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass
class ChecklistItem:
    title: str
    id: str = field(default_factory=lambda: new_id("item"))
    required: bool = True
    completed: bool = False
    dependency_ids: set[str] = field(default_factory=set)
    due_at: Optional[datetime] = None
    evidence_ids: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class StagedBrowserAction:
    application_id: str
    action: str
    target_url: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: new_id("action"))
    state: ActionState = ActionState.APPROVAL_REQUIRED
    payload_digest: str = ""
    approval_id: Optional[str] = None
    approved_digest: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass
class ApplicationWorkspace:
    competition_id: str
    title: str
    source_ids: list[str]
    id: str = field(default_factory=lambda: new_id("application"))
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    facts: list[ExtractedFact] = field(default_factory=list)
    checklist: list[ChecklistItem] = field(default_factory=list)
    materials: dict[str, str] = field(default_factory=dict)
    staged_actions: list[str] = field(default_factory=list)
    version: int = 1
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def required_complete(self) -> bool:
        return all(item.completed for item in self.checklist if item.required)


@dataclass(frozen=True)
class StatusObservation:
    application_id: str
    status: ApplicationStatus
    source: str
    observed_at: datetime
    evidence: str
    external_reference: Optional[str] = None
