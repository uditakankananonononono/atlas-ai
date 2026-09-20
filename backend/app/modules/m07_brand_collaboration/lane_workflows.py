from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping, Sequence

from .lane_models import Campaign, CampaignMetrics, CampaignStatus, Deliverable, Evidence
from .lane_service import ValidationError


@dataclass(frozen=True)
class CollaborationBrief:
    campaign_id: str
    objective: str
    audience: str
    key_messages: tuple[str, ...]
    required_disclosures: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    deliverables: tuple[Deliverable, ...]
    approval_steps: tuple[str, ...]


@dataclass(frozen=True)
class BriefReview:
    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class Reminder:
    campaign_id: str
    kind: str
    due_at: datetime
    message: str


@dataclass(frozen=True)
class PortfolioSummary:
    campaign_count: int
    active_count: int
    contracted_minor: int
    paid_minor: int
    outstanding_minor: int
    currency: str
    total_impressions: int
    total_clicks: int
    total_conversions: int
    weighted_ctr: float
    weighted_conversion_rate: float


class BriefService:
    def review(self, brief: CollaborationBrief, evidence: Sequence[Evidence]) -> BriefReview:
        blockers: list[str] = []
        warnings: list[str] = []
        if not brief.objective.strip(): blockers.append("objective is required")
        if not brief.audience.strip(): blockers.append("audience is required")
        if not brief.key_messages: blockers.append("at least one key message is required")
        if not brief.deliverables: blockers.append("at least one deliverable is required")
        if not brief.approval_steps: blockers.append("approval workflow is required")
        claims = {e.claim.casefold() for e in evidence if e.confidence >= .7}
        for message in brief.key_messages:
            if message.casefold() not in claims:
                warnings.append(f"key message lacks supporting evidence: {message}")
        if not brief.required_disclosures:
            warnings.append("no sponsorship disclosures are specified")
        return BriefReview(not blockers, tuple(blockers), tuple(warnings))


class ReminderService:
    def build(self, campaign: Campaign, *, now: datetime | None = None) -> list[Reminder]:
        now = now or datetime.now(timezone.utc)
        reminders: list[Reminder] = []
        if campaign.due_at and campaign.status in {CampaignStatus.CONTRACTED, CampaignStatus.ACTIVE, CampaignStatus.REVISION}:
            if now <= campaign.due_at <= now + timedelta(days=7):
                reminders.append(Reminder(campaign.id, "deliverable_due", campaign.due_at, f"{campaign.title} deliverable is due {campaign.due_at.isoformat()}"))
            elif campaign.due_at < now:
                reminders.append(Reminder(campaign.id, "deliverable_overdue", campaign.due_at, f"{campaign.title} deliverable is overdue"))
        if campaign.payment_due_at and campaign.status == CampaignStatus.APPROVED:
            kind = "payment_overdue" if campaign.payment_due_at < now else "payment_due"
            if campaign.payment_due_at <= now + timedelta(days=7):
                reminders.append(Reminder(campaign.id, kind, campaign.payment_due_at, f"{campaign.title} payment is {'overdue' if kind == 'payment_overdue' else 'due soon'}"))
        return sorted(reminders, key=lambda r: (r.due_at, r.kind))


class PortfolioService:
    def summarize(self, campaigns: Sequence[Campaign], metrics: Mapping[str, CampaignMetrics]) -> PortfolioSummary:
        currencies = {c.currency.upper() for c in campaigns}
        if len(currencies) > 1:
            raise ValidationError("portfolio summary requires a single currency")
        currency = next(iter(currencies), "USD")
        contracted = sum(c.agreed_fee_minor for c in campaigns if c.status not in {CampaignStatus.PROSPECT, CampaignStatus.PITCHED, CampaignStatus.NEGOTIATING, CampaignStatus.CANCELLED})
        paid = sum(c.agreed_fee_minor for c in campaigns if c.status == CampaignStatus.PAID)
        aggregate = CampaignMetrics(
            impressions=sum(metrics.get(c.id, CampaignMetrics()).impressions for c in campaigns),
            views=sum(metrics.get(c.id, CampaignMetrics()).views for c in campaigns),
            clicks=sum(metrics.get(c.id, CampaignMetrics()).clicks for c in campaigns),
            engagements=sum(metrics.get(c.id, CampaignMetrics()).engagements for c in campaigns),
            conversions=sum(metrics.get(c.id, CampaignMetrics()).conversions for c in campaigns),
            revenue_minor=sum(metrics.get(c.id, CampaignMetrics()).revenue_minor for c in campaigns),
        )
        return PortfolioSummary(
            len(campaigns), sum(c.status in {CampaignStatus.CONTRACTED, CampaignStatus.ACTIVE, CampaignStatus.SUBMITTED, CampaignStatus.REVISION, CampaignStatus.APPROVED} for c in campaigns),
            contracted, paid, contracted - paid, currency, aggregate.impressions, aggregate.clicks, aggregate.conversions,
            aggregate.click_through_rate, aggregate.conversion_rate,
        )
