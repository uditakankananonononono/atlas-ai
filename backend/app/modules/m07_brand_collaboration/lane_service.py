from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable, Sequence

from .lane_models import (
    ALLOWED_TRANSITIONS,
    BrandCandidate,
    Campaign,
    CampaignEvent,
    CampaignMetrics,
    CampaignStatus,
    CreatorProfile,
    Deliverable,
    DiscoveryResult,
    Evidence,
    EvidenceKind,
    NegotiationDraft,
    new_id,
)


class ValidationError(ValueError):
    pass


def _terms(values: Iterable[str]) -> set[str]:
    return {v.strip().casefold() for v in values if v and v.strip()}


class BrandDiscoveryService:
    """Ranks supplied, source-attributed brand candidates without inventing brands."""

    def rank(self, creator: CreatorProfile, candidates: Sequence[BrandCandidate]) -> list[DiscoveryResult]:
        creator_categories = _terms(creator.categories)
        creator_values = _terms(creator.values)
        creator_locations = _terms(creator.audience_locations)
        blocked = _terms(creator.blocked_categories)
        results: list[DiscoveryResult] = []
        for brand in candidates:
            categories = _terms(brand.categories)
            if blocked & categories:
                continue
            score = 0.0
            reasons: list[str] = []
            warnings: list[str] = []
            overlap = creator_categories & categories
            if overlap:
                category_score = min(45.0, 15.0 * len(overlap))
                score += category_score
                reasons.append(f"category match: {', '.join(sorted(overlap))}")
            value_overlap = creator_values & _terms(brand.values)
            if value_overlap:
                score += min(20.0, 10.0 * len(value_overlap))
                reasons.append(f"value match: {', '.join(sorted(value_overlap))}")
            brand_locations = _terms(brand.audience_locations)
            if creator_locations and brand_locations:
                location_overlap = creator_locations & brand_locations
                if location_overlap:
                    score += 15.0
                    reasons.append(f"audience geography: {', '.join(sorted(location_overlap))}")
                else:
                    warnings.append("audience geography does not overlap")
            if brand.contact_email:
                score += 10.0
                reasons.append("public contact available")
            else:
                warnings.append("no contact evidence")
            if brand.source_url:
                score += 10.0
            else:
                warnings.append("candidate lacks source URL")
            if brand.minimum_followers is not None:
                if creator.followers >= brand.minimum_followers:
                    score += 10.0
                    reasons.append("creator meets stated follower threshold")
                else:
                    warnings.append("creator is below stated follower threshold")
                    score -= 20.0
            results.append(DiscoveryResult(brand, round(max(0.0, min(score, 100.0)), 2), tuple(reasons), tuple(warnings)))
        return sorted(results, key=lambda item: (-item.score, item.brand.name.casefold()))


class EvidenceService:
    def create(
        self,
        *,
        brand_name: str,
        kind: EvidenceKind,
        source_url: str,
        claim: str,
        excerpt: str,
        observed_at: datetime | None = None,
        confidence: float = 1.0,
        metadata: dict | None = None,
    ) -> Evidence:
        if not source_url.startswith(("https://", "http://")):
            raise ValidationError("evidence requires an http(s) source URL")
        if not claim.strip() or not excerpt.strip():
            raise ValidationError("claim and excerpt are required")
        if not 0 <= confidence <= 1:
            raise ValidationError("confidence must be between 0 and 1")
        return Evidence(
            id=new_id("evidence"), brand_name=brand_name.strip(), kind=kind,
            source_url=source_url, claim=claim.strip(), excerpt=excerpt.strip(),
            observed_at=observed_at or datetime.now(timezone.utc), confidence=confidence,
            metadata=metadata or {},
        )

    def claims(self, evidence: Sequence[Evidence], *, minimum_confidence: float = .7) -> dict[str, list[Evidence]]:
        grouped: dict[str, list[Evidence]] = {}
        for item in evidence:
            if item.confidence >= minimum_confidence:
                grouped.setdefault(item.claim, []).append(item)
        return grouped


class NegotiationService:
    USAGE_RATE_PER_MONTH = 0.025
    EXCLUSIVITY_RATE_PER_MONTH = 0.05

    def quote(self, deliverables: Sequence[Deliverable]) -> int:
        if not deliverables:
            raise ValidationError("at least one deliverable is required")
        currencies = {d.currency.upper() for d in deliverables}
        if len(currencies) != 1:
            raise ValidationError("all deliverables must use one currency")
        total = 0.0
        for d in deliverables:
            if d.quantity < 1 or d.unit_rate_minor < 0 or d.usage_months < 0 or d.exclusivity_months < 0:
                raise ValidationError("invalid deliverable quantity, rate, or duration")
            base = d.base_minor
            total += base
            total += base * self.USAGE_RATE_PER_MONTH * d.usage_months
            total += base * self.EXCLUSIVITY_RATE_PER_MONTH * d.exclusivity_months
        return round(total)

    def draft_counteroffer(
        self,
        *,
        brand_name: str,
        contact_name: str | None,
        deliverables: Sequence[Deliverable],
        offered_minor: int,
        creator_name: str,
        floor_ratio: float = .85,
    ) -> NegotiationDraft:
        if offered_minor < 0 or not 0 < floor_ratio <= 1:
            raise ValidationError("offered amount and floor ratio are invalid")
        ask = self.quote(deliverables)
        floor = round(ask * floor_ratio)
        currency = deliverables[0].currency.upper()
        greeting = f"Hi {contact_name.strip()}," if contact_name and contact_name.strip() else "Hello,"
        scope = ", ".join(f"{d.quantity} x {d.kind}" for d in deliverables)
        body = (
            f"{greeting}\n\nThanks for sharing the proposal for {scope}. Based on the scope, usage, "
            f"and exclusivity terms, my rate is {currency} {ask / 100:,.2f}. "
            "That includes the deliverables listed above and the agreed review round. "
            "If the budget is fixed, I can revise the scope or usage period rather than reduce the work without changing terms.\n\n"
            f"Best,\n{creator_name}"
        )
        assumptions = ["one review round included", "payment schedule and cancellation terms still require agreement"]
        if offered_minor < floor:
            assumptions.append(f"brand offer of {currency} {offered_minor / 100:,.2f} is below the calculated floor")
        return NegotiationDraft(new_id("draft"), brand_name, f"Re: {brand_name} collaboration scope and rate", body, ask, floor, currency, tuple(assumptions), True)


class CampaignService:
    def transition(self, campaign: Campaign, target: CampaignStatus, *, at: datetime | None = None, note: str = "") -> tuple[Campaign, CampaignEvent]:
        if target not in ALLOWED_TRANSITIONS[campaign.status]:
            raise ValidationError(f"cannot transition campaign from {campaign.status.value} to {target.value}")
        occurred_at = at or datetime.now(timezone.utc)
        updated = replace(campaign, status=target, updated_at=occurred_at)
        event = CampaignEvent(new_id("event"), campaign.id, "status_changed", occurred_at, {"from": campaign.status.value, "to": target.value, "note": note})
        return updated, event

    def aggregate_metrics(self, events: Sequence[CampaignEvent]) -> CampaignMetrics:
        totals = {"impressions": 0, "views": 0, "clicks": 0, "engagements": 0, "conversions": 0, "revenue_minor": 0}
        for event in events:
            if event.kind != "metrics":
                continue
            for key in totals:
                value = event.payload.get(key, 0)
                if not isinstance(value, int) or value < 0:
                    raise ValidationError(f"metric {key} must be a non-negative integer")
                totals[key] += value
        return CampaignMetrics(**totals)

    def overdue_flags(self, campaign: Campaign, *, now: datetime | None = None) -> tuple[str, ...]:
        now = now or datetime.now(timezone.utc)
        flags: list[str] = []
        if campaign.due_at and campaign.due_at < now and campaign.status in {CampaignStatus.CONTRACTED, CampaignStatus.ACTIVE, CampaignStatus.REVISION}:
            flags.append("deliverable_overdue")
        if campaign.payment_due_at and campaign.payment_due_at < now and campaign.status == CampaignStatus.APPROVED:
            flags.append("payment_overdue")
        return tuple(flags)
