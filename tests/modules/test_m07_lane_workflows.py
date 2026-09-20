from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m07_brand_collaboration.lane_models import *
from app.modules.m07_brand_collaboration.lane_service import EvidenceService, ValidationError
from app.modules.m07_brand_collaboration.lane_workflows import *


def test_brief_review_blocks_missing_structure_and_warns_unsubstantiated_claims():
    brief = CollaborationBrief("c", "", "", ("Clinically proven",), (), (), (), ())
    review = BriefService().review(brief, [])
    assert not review.ready
    assert "objective is required" in review.blockers
    assert "key message lacks supporting evidence: Clinically proven" in review.warnings
    assert "no sponsorship disclosures are specified" in review.warnings


def test_brief_with_cited_claim_is_ready():
    evidence = EvidenceService().create(brand_name="B", kind=EvidenceKind.PRESS, source_url="https://x.test", claim="Plastic-free packaging", excerpt="All packaging is plastic-free")
    brief = CollaborationBrief("c", "Launch", "Artists", ("Plastic-free packaging",), ("#ad",), (), (Deliverable("video", 1, 100),), ("brand review",))
    review = BriefService().review(brief, [evidence])
    assert review.ready
    assert review.warnings == ()


def test_reminders_cover_due_and_overdue_work_and_payment():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    work = Campaign("a", "B", "Work", CampaignStatus.ACTIVE, "USD", 100, due_at=now + timedelta(days=2))
    payment = Campaign("b", "B", "Payment", CampaignStatus.APPROVED, "USD", 100, payment_due_at=now - timedelta(days=1))
    assert ReminderService().build(work, now=now)[0].kind == "deliverable_due"
    assert ReminderService().build(payment, now=now)[0].kind == "payment_overdue"


def test_portfolio_summary_tracks_money_and_weighted_rates():
    campaigns = [
        Campaign("a", "A", "One", CampaignStatus.ACTIVE, "USD", 1000),
        Campaign("b", "B", "Two", CampaignStatus.PAID, "USD", 2000),
        Campaign("c", "C", "Lead", CampaignStatus.PROSPECT, "USD", 9000),
    ]
    metrics = {"a": CampaignMetrics(impressions=100, clicks=10, conversions=2), "b": CampaignMetrics(impressions=300, clicks=30, conversions=3)}
    summary = PortfolioService().summarize(campaigns, metrics)
    assert summary.contracted_minor == 3000
    assert summary.paid_minor == 2000
    assert summary.outstanding_minor == 1000
    assert summary.weighted_ctr == .1
    assert summary.weighted_conversion_rate == .125


def test_portfolio_rejects_currency_mixing():
    campaigns = [Campaign("a", "A", "One", CampaignStatus.ACTIVE, "USD", 100), Campaign("b", "B", "Two", CampaignStatus.ACTIVE, "INR", 100)]
    with pytest.raises(ValidationError):
        PortfolioService().summarize(campaigns, {})
