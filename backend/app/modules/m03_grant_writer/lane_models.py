from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


class ValidationError(ValueError):
    pass


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"


@dataclass(frozen=True)
class Opportunity:
    id: str
    title: str
    sponsor: str
    deadline: datetime
    eligibility: tuple[str, ...]
    priorities: tuple[str, ...]
    source_url: str
    source_text: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.id or not self.title or not self.source_url or not self.source_text:
            raise ValidationError("opportunity requires id, title, source_url, and source_text")
        if self.deadline.tzinfo is None or self.observed_at.tzinfo is None:
            raise ValidationError("opportunity timestamps must be timezone-aware")


@dataclass(frozen=True)
class CorpusDocument:
    id: str
    title: str
    text: str
    source_url: str
    observed_at: datetime
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.id, self.title, self.text, self.source_url)):
            raise ValidationError("corpus document requires id, title, text, and source_url")
        if self.observed_at.tzinfo is None:
            raise ValidationError("observed_at must be timezone-aware")


@dataclass(frozen=True)
class GroundingHit:
    document_id: str
    title: str
    source_url: str
    excerpt: str
    score: float
    observed_at: datetime


@dataclass(frozen=True)
class ProposalSection:
    name: str
    text: str
    citation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CritiqueItem:
    code: str
    severity: Severity
    section: str
    message: str
    suggestion: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class BudgetRate:
    code: str
    label: str
    unit: str
    amount: Decimal
    currency: str
    effective_from: date
    source_url: str
    observed_at: datetime
    effective_to: date | None = None

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValidationError("rate amount cannot be negative")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError("effective_to precedes effective_from")
        if self.observed_at.tzinfo is None:
            raise ValidationError("observed_at must be timezone-aware")


@dataclass(frozen=True)
class BudgetRequestLine:
    rate_code: str
    quantity: Decimal
    description: str

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValidationError("budget quantity must be positive")


@dataclass(frozen=True)
class BudgetLine:
    rate_code: str
    description: str
    quantity: Decimal
    unit: str
    unit_amount: Decimal
    total: Decimal
    currency: str
    rate_effective_from: date
    source_url: str


@dataclass(frozen=True)
class Budget:
    lines: tuple[BudgetLine, ...]
    currency: str
    direct_total: Decimal
    indirect_total: Decimal
    grand_total: Decimal
    indirect_rate: Decimal
    as_of: date


@dataclass(frozen=True)
class ReportPart:
    order: int
    kind: str
    title: str
    content: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class GrantReport:
    opportunity_id: str
    generated_at: datetime
    parts: tuple[ReportPart, ...]
    budget: Budget
    critique: tuple[CritiqueItem, ...]
    grounding: tuple[GroundingHit, ...]


@dataclass(frozen=True)
class ReviewHandoff:
    handoff_id: str
    artifact_sha256: str
    artifact_json: str
    recipient: str
    action: str
    created_at: datetime
    approval_required: bool = True


@dataclass(frozen=True)
class ReviewApproval:
    handoff_id: str
    artifact_sha256: str
    reviewer: str
    approved_at: datetime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
