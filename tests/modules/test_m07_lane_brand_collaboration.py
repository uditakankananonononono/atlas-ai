import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m07_brand_collaboration.lane_models import *
from app.modules.m07_brand_collaboration.lane_repository import BrandCollaborationRepository
from app.modules.m07_brand_collaboration.lane_service import *


def test_discovery_ranks_fit_and_filters_blocked_categories():
    creator = CreatorProfile(("art", "science"), ("sustainability",), ("india",), 10_000, blocked_categories=("gambling",))
    candidates = [
        BrandCandidate("Good", "https://good.test", ("art",), values=("sustainability",), contact_email="hi@good.test", audience_locations=("india",), minimum_followers=5000, source_url="https://good.test/creators"),
        BrandCandidate("Blocked", "https://blocked.test", ("gambling",), source_url="https://blocked.test"),
        BrandCandidate("Weak", "https://weak.test", ("fashion",)),
    ]
    results = BrandDiscoveryService().rank(creator, candidates)
    assert [r.brand.name for r in results] == ["Good", "Weak"]
    assert results[0].score == 70
    assert "candidate lacks source URL" in results[1].warnings


def test_discovery_flags_follower_threshold():
    creator = CreatorProfile(("tech",), followers=99)
    [result] = BrandDiscoveryService().rank(creator, [BrandCandidate("B", "https://b.test", ("tech",), minimum_followers=100, source_url="https://b.test")])
    assert result.score == 5
    assert "creator is below stated follower threshold" in result.warnings


def test_evidence_requires_source_and_groups_only_confident_claims():
    service = EvidenceService()
    with pytest.raises(ValidationError):
        service.create(brand_name="B", kind=EvidenceKind.PRESS, source_url="citation", claim="x", excerpt="y")
    high = service.create(brand_name="B", kind=EvidenceKind.PRESS, source_url="https://source.test", claim="Runs creator campaigns", excerpt="Creator program", confidence=.9)
    low = service.create(brand_name="B", kind=EvidenceKind.SOCIAL, source_url="https://social.test", claim="Runs creator campaigns", excerpt="Maybe", confidence=.4)
    assert service.claims([high, low]) == {"Runs creator campaigns": [high]}


def test_quote_includes_usage_and_exclusivity_and_rejects_mixed_currency():
    service = NegotiationService()
    d = Deliverable("video", 2, 10_000, "USD", usage_months=2, exclusivity_months=1)
    assert service.quote([d]) == 22_000
    with pytest.raises(ValidationError):
        service.quote([d, Deliverable("post", 1, 100, "INR")])


def test_negotiation_draft_is_approval_gated_and_surfaces_low_offer():
    draft = NegotiationService().draft_counteroffer(brand_name="Acme", contact_name="Ana", deliverables=[Deliverable("video", 1, 10_000)], offered_minor=5000, creator_name="Udita")
    assert draft.approval_required is True
    assert draft.ask_minor == 10_000
    assert draft.floor_minor == 8_500
    assert "below the calculated floor" in draft.assumptions[-1]
    assert "Hi Ana," in draft.body


def test_campaign_transition_state_machine_and_overdue_flags():
    now = datetime.now(timezone.utc)
    campaign = Campaign("c1", "Acme", "Launch", CampaignStatus.CONTRACTED, "USD", 1000, due_at=now - timedelta(days=1))
    service = CampaignService()
    assert service.overdue_flags(campaign, now=now) == ("deliverable_overdue",)
    updated, event = service.transition(campaign, CampaignStatus.ACTIVE, at=now)
    assert updated.status is CampaignStatus.ACTIVE
    assert event.payload["from"] == "contracted"
    with pytest.raises(ValidationError):
        service.transition(updated, CampaignStatus.PAID)


def test_metrics_aggregate_and_derive_rates():
    now = datetime.now(timezone.utc)
    events = [CampaignEvent("e1", "c", "metrics", now, {"impressions": 1000, "clicks": 50, "engagements": 100, "conversions": 5}), CampaignEvent("e2", "c", "metrics", now, {"impressions": 1000, "clicks": 50})]
    metrics = CampaignService().aggregate_metrics(events)
    assert metrics.click_through_rate == .05
    assert metrics.engagement_rate == .05
    assert metrics.conversion_rate == .05


def test_repository_round_trip_campaign_evidence_and_events():
    repo = BrandCollaborationRepository(sqlite3.connect(":memory:"))
    repo.migrate()
    evidence = EvidenceService().create(brand_name="Acme", kind=EvidenceKind.WEBSITE, source_url="https://acme.test", claim="Creator program", excerpt="Apply")
    repo.save_evidence(evidence)
    assert repo.list_evidence("Acme") == [evidence]
    campaign = Campaign("c1", "Acme", "Launch", CampaignStatus.PROSPECT, "USD", 1000, deliverables=(Deliverable("video", 1, 1000),))
    repo.save_campaign(campaign)
    assert repo.get_campaign("c1") == campaign
    event = CampaignEvent("e1", "c1", "metrics", datetime.now(timezone.utc), {"views": 10})
    repo.save_event(event)
    assert repo.list_events("c1") == [event]
