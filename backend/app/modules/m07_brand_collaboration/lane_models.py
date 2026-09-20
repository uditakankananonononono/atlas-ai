from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class EvidenceKind(str, Enum):
    WEBSITE = "website"
    SOCIAL = "social"
    PRESS = "press"
    CAMPAIGN = "campaign"
    CONTACT = "contact"
    POLICY = "policy"


class CampaignStatus(str, Enum):
    PROSPECT = "prospect"
    PITCHED = "pitched"
    NEGOTIATING = "negotiating"
    CONTRACTED = "contracted"
    ACTIVE = "active"
    SUBMITTED = "submitted"
    REVISION = "revision"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"


ALLOWED_TRANSITIONS: dict[CampaignStatus, set[CampaignStatus]] = {
    CampaignStatus.PROSPECT: {CampaignStatus.PITCHED, CampaignStatus.CANCELLED},
    CampaignStatus.PITCHED: {CampaignStatus.NEGOTIATING, CampaignStatus.CONTRACTED, CampaignStatus.CANCELLED},
    CampaignStatus.NEGOTIATING: {CampaignStatus.CONTRACTED, CampaignStatus.CANCELLED},
    CampaignStatus.CONTRACTED: {CampaignStatus.ACTIVE, CampaignStatus.CANCELLED},
    CampaignStatus.ACTIVE: {CampaignStatus.SUBMITTED, CampaignStatus.CANCELLED},
    CampaignStatus.SUBMITTED: {CampaignStatus.REVISION, CampaignStatus.APPROVED},
    CampaignStatus.REVISION: {CampaignStatus.SUBMITTED, CampaignStatus.APPROVED},
    CampaignStatus.APPROVED: {CampaignStatus.PAID},
    CampaignStatus.PAID: set(),
    CampaignStatus.CANCELLED: set(),
}


@dataclass(frozen=True)
class BrandCandidate:
    name: str
    website: str
    categories: tuple[str, ...] = ()
    description: str = ""
    values: tuple[str, ...] = ()
    contact_email: str | None = None
    audience_locations: tuple[str, ...] = ()
    minimum_followers: int | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class CreatorProfile:
    categories: tuple[str, ...]
    values: tuple[str, ...] = ()
    audience_locations: tuple[str, ...] = ()
    followers: int = 0
    average_views: int = 0
    engagement_rate: float = 0.0
    blocked_categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryResult:
    brand: BrandCandidate
    score: float
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class Evidence:
    id: str
    brand_name: str
    kind: EvidenceKind
    source_url: str
    claim: str
    excerpt: str
    observed_at: datetime
    confidence: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Deliverable:
    kind: str
    quantity: int = 1
    unit_rate_minor: int = 0
    currency: str = "USD"
    usage_months: int = 0
    exclusivity_months: int = 0

    @property
    def base_minor(self) -> int:
        return self.quantity * self.unit_rate_minor


@dataclass(frozen=True)
class NegotiationDraft:
    id: str
    brand_name: str
    subject: str
    body: str
    ask_minor: int
    floor_minor: int
    currency: str
    assumptions: tuple[str, ...]
    approval_required: bool = True


@dataclass(frozen=True)
class Campaign:
    id: str
    brand_name: str
    title: str
    status: CampaignStatus
    currency: str
    agreed_fee_minor: int
    start_at: datetime | None = None
    due_at: datetime | None = None
    payment_due_at: datetime | None = None
    deliverables: tuple[Deliverable, ...] = ()
    owner: str | None = None
    notes: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class CampaignEvent:
    id: str
    campaign_id: str
    kind: str
    occurred_at: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CampaignMetrics:
    impressions: int = 0
    views: int = 0
    clicks: int = 0
    engagements: int = 0
    conversions: int = 0
    revenue_minor: int = 0

    @property
    def click_through_rate(self) -> float:
        denominator = self.impressions or self.views
        return self.clicks / denominator if denominator else 0.0

    @property
    def engagement_rate(self) -> float:
        denominator = self.impressions or self.views
        return self.engagements / denominator if denominator else 0.0

    @property
    def conversion_rate(self) -> float:
        return self.conversions / self.clicks if self.clicks else 0.0
