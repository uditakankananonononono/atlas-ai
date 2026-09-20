"""Row-named focused tests for growth planning artifacts (feature rows 417-450)."""

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m05_outreach_manager import routes as m05_routes
from app.modules.m05_outreach_manager.growth import (
    AccountHealth,
    AutomationTrigger,
    Creator,
    DynamicRule,
    EvidenceItem,
    GrowthPlanError,
    HealthSignal,
    IssueSolution,
    Lead,
    MediaContact,
    PriceBounds,
    PricePoint,
    PricedProduct,
    ScoringCriterion,
    StageMetric,
    Tier,
    analyze_price_elasticity,
    design_revenue_model,
    design_sales_funnel,
    design_subscription,
    design_support_system,
    develop_sales_script,
    plan_affiliate_marketing,
    plan_bundling,
    plan_community_management,
    plan_community_support,
    plan_conversion_optimization,
    plan_crisis_communication,
    plan_cross_selling,
    plan_customer_success,
    plan_dynamic_pricing,
    plan_email_marketing,
    plan_freemium,
    plan_influencer_marketing,
    plan_knowledge_base,
    plan_landing_page,
    plan_marketing_automation,
    plan_media_relations,
    plan_negotiation,
    plan_objection_handling,
    plan_onboarding,
    plan_pricing_strategy,
    plan_public_relations,
    plan_referral_program,
    plan_social_media_strategy,
    plan_tiered_pricing,
    plan_upselling,
    plan_usage_based_pricing,
    score_leads,
    structure_deal,
)
from app.modules.m05_outreach_manager.service import InMemoryContactRepository, Service
from app.modules.m05_outreach_manager.schemas import ContactCreate

EV = [EvidenceItem(key="ev1", source="founder interview 2026-09", fact="Atlas has 200 beta users")]


def test_row_417_public_relations():
    artifact = plan_public_relations(
        goal="Protect launch reputation", brand_facts=["200 beta users", "SOC2 in progress"], evidence=EV
    )
    assert artifact.feature_row == 417
    assert "200 beta users" in artifact.sections[0].body
    assert any("approval" in e for e in artifact.gated_effects)


def test_row_418_media_relations_never_fabricates_contacts():
    artifact = plan_media_relations(
        goal="Launch coverage",
        journalists=[MediaContact(name="Ana", outlet="TechPress", beat="dev tools", relevance_fact="covered our beta")],
        evidence=EV,
    )
    assert "Ana" in artifact.sections[0].body
    empty = plan_media_relations(goal="Launch coverage", journalists=[], evidence=EV)
    assert "None will be invented" in empty.sections[0].body
    assert any("no media contacts supplied" in c for c in empty.scope_checks)


def test_row_419_crisis_communication_uses_only_confirmed_facts():
    artifact = plan_crisis_communication(
        scenario="a data export bug",
        severity="high",
        confirmed_facts=["The bug affected 12 accounts.", "Exports are paused."],
        stakeholders=["affected customers", "all users", "press"],
        update_window="within 60 minutes",
        unconfirmed=["root cause"],
        evidence=EV,
    )
    statement = artifact.sections[1].body
    assert "12 accounts" in statement and "root cause" not in statement
    assert "60 minutes" in artifact.sections[0].body


def test_row_420_social_media_strategy():
    artifact = plan_social_media_strategy(
        goal="Grow awareness", platforms=["LinkedIn", "X"], brand_facts=["200 beta users"], evidence=EV
    )
    assert "linkedin: 3 posts/week" in artifact.sections[1].body
    assert any("self-bots" in c for c in artifact.scope_checks)


def test_row_421_community_management():
    artifact = plan_community_management(
        community_name="Atlas Builders", purpose="peer support", member_facts=["40 active members"], evidence=EV
    )
    assert "Atlas Builders" in artifact.sections[0].body
    assert "Level 3" in artifact.sections[1].body


def test_row_422_influencer_marketing_requires_supplied_creators():
    artifact = plan_influencer_marketing(
        goal="Dev-tool awareness",
        creators=[Creator(name="Priya", platform="youtube", handle="priyabuilds", relevance_fact="reviewed Atlas beta")],
        evidence=EV,
    )
    assert "priyabuilds" in artifact.sections[0].body
    assert any("disclosure" in c for c in artifact.scope_checks)
    empty = plan_influencer_marketing(goal="x", creators=[], evidence=EV)
    assert "None will be invented" in empty.sections[0].body


def test_row_423_affiliate_marketing_computes_example():
    artifact = plan_affiliate_marketing(
        program_name="Atlas Partners", commission_pct=20, cookie_days=30, avg_order_value=120, evidence=EV
    )
    assert "pays 24.0" in artifact.sections[0].body
    with pytest.raises(GrowthPlanError):
        plan_affiliate_marketing(program_name="x", commission_pct=0, cookie_days=30, evidence=EV)


def test_row_424_referral_program():
    artifact = plan_referral_program(
        program_name="Bring a friend", referrer_reward="1 free month", referee_reward="1 free month", evidence=EV
    )
    assert "1 free month" in artifact.sections[0].body
    assert "Fraud guards" in artifact.sections[1].title


def test_row_425_email_marketing_binds_to_runtime_scope():
    service = Service(InMemoryContactRepository(), approval_sink=None, scholar=None)
    contact = service.create_contact(
        ContactCreate(
            project_id="p",
            name="Founder",
            email="f@x.io",
            metadata={"enrichment": {"email_verified": True}},
        )
    )
    artifact = plan_email_marketing(goal="Nurture trials", contacts=[contact], evidence=EV)
    assert artifact.feature_row == 425
    assert "send_outreach_email" in artifact.sections[2].body

    unverified = service.create_contact(ContactCreate(project_id="p", name="Lead", email="l@y.io"))
    with pytest.raises(GrowthPlanError, match="provider-verified"):
        plan_email_marketing(goal="Nurture trials", contacts=[unverified], evidence=EV)


def test_row_426_marketing_automation_never_autonomous():
    artifact = plan_marketing_automation(
        goal="Trial nurture",
        triggers=[AutomationTrigger(event="trial_started", action="send welcome email", delay_hours=1)],
        evidence=EV,
    )
    assert any("no autonomous sends" in c for c in artifact.scope_checks)
    assert "inert until a person approves" in artifact.sections[1].body


def test_row_427_lead_scoring_is_transparent():
    result = score_leads(
        leads=[
            Lead(name="A", attributes={"role": "professor", "replied": "yes"}),
            Lead(name="B", attributes={"role": "student"}),
        ],
        criteria=[
            ScoringCriterion(attribute="role", match="professor", points=50, rationale="decision maker"),
            ScoringCriterion(attribute="replied", points=50, rationale="already engaged"),
        ],
        evidence=EV,
    )
    assert result.scores[0].lead == "A" and result.scores[0].score == 100.0
    assert result.scores[1].score == 0.0
    assert "decision maker" in result.scores[0].reasons[0]


def test_row_428_sales_funnel_computes_conversion_from_supplied_metrics():
    artifact = design_sales_funnel(
        goal="Map journey",
        stages=[StageMetric(stage="visit", visitors=1000), StageMetric(stage="signup", visitors=120)],
        evidence=EV,
    )
    assert "12.0%" in artifact.sections[1].body
    bare = design_sales_funnel(goal="Map journey", evidence=EV)
    assert "no conversion claims" in bare.sections[0].body


def test_row_429_cro_prioritizes_weakest_step():
    artifact = plan_conversion_optimization(
        goal="Improve funnel",
        funnel=[
            StageMetric(stage="visit", visitors=1000),
            StageMetric(stage="signup", visitors=400),
            StageMetric(stage="paid", visitors=20),
        ],
        evidence=EV,
    )
    assert "signup -> paid" in artifact.sections[1].body
    assert "5.0%" in artifact.sections[1].body


def test_row_430_landing_page_audit_is_deterministic():
    artifact = plan_landing_page(
        page_url="https://atlas.example",
        current_headline="The autonomous assistant that plans and executes your entire workday for you every single morning",
        cta_text="Start free",
        value_facts=["Plans your day in 30 seconds"],
        load_time_ms=4200,
        evidence=EV,
    )
    findings = artifact.sections[0].body
    assert "over the 12-word" in findings
    assert "over the 2500ms" in findings
    assert "Plans your day in 30 seconds" in artifact.sections[1].body


def test_row_431_sales_script_cites_facts():
    artifact = develop_sales_script(
        persona="busy founder", product_facts=["Plans your day in 30 seconds"], call_to_action="book a 15-minute demo", evidence=EV
    )
    assert "Because Plans your day in 30 seconds" in artifact.sections[2].body
    assert artifact.sections[2].evidence_keys == ["pf1"]


def test_row_432_objection_handling_grounds_responses():
    artifact = plan_objection_handling(
        objections=["too expensive"], product_facts=["Costs less than one hour of a VA per month"], evidence=EV
    )
    assert "too expensive" in artifact.sections[0].title
    assert "Costs less than one hour" in artifact.sections[0].body
    assert artifact.sections[-1].title == "Never say"


def test_row_433_negotiation_computes_concession_ladder():
    artifact = plan_negotiation(
        target_outcome="annual contract",
        walk_away="below 8000 we walk",
        constraints=["no exclusivity"],
        counterpart_facts=["they need a decision by Friday"],
        opening_offer=12000,
        walk_away_price=8000,
        evidence=EV,
    )
    assert "12000" in artifact.sections[2].body and "8000" in artifact.sections[2].body
    assert "10666.67" in artifact.sections[2].body


def test_row_434_deal_structuring_tracks_open_terms():
    artifact = structure_deal(
        parties=["Atlas", "Northwind"],
        terms={"price": 10000, "term": "12 months", "exclusivity": "TBD"},
        evidence=EV,
    )
    assert "price: 10000" in artifact.sections[1].body
    assert "exclusivity" in artifact.sections[2].body
    assert any("not legal advice" in c for c in artifact.scope_checks)


def test_row_435_pricing_strategy_derives_only_from_inputs():
    artifact = plan_pricing_strategy(
        product="Atlas Pro", unit_cost=4, target_margin_pct=60, competitor_prices=[10, 14], evidence=EV
    )
    assert "10.0" in artifact.sections[0].body  # 4 / (1 - 0.6)
    assert "10-14" in artifact.sections[0].body
    bare = plan_pricing_strategy(product="Atlas Pro", unit_cost=4, target_margin_pct=60, evidence=EV)
    assert "no market positioning is claimed" in bare.sections[0].body


def test_row_436_price_elasticity_midpoint_math():
    result = analyze_price_elasticity(
        points=[PricePoint(price=10, quantity=100), PricePoint(price=12, quantity=70)], evidence=EV
    )
    # midpoint: dq = -30/85, dp = 2/11 -> E = 1.941
    assert result.average_elasticity == pytest.approx(1.941, abs=0.001)
    assert result.classification == "elastic"
    assert any("weak signal" in c for c in result.caveats)


def test_row_437_revenue_model():
    artifact = design_revenue_model(
        value_proposition="An assistant that does the work",
        streams=[{"name": "Pro", "type": "subscription", "description": "monthly plan"}],
        evidence=EV,
    )
    assert "Pro (subscription)" in artifact.sections[1].body


def test_row_438_subscription_design_computes_equivalents():
    artifact = design_subscription(
        tiers=[Tier(name="Annual", price=120, period="yearly"), Tier(name="Monthly", price=12)],
        evidence=EV,
    )
    assert "monthly equivalent 10.0" in artifact.sections[0].body


def test_row_439_freemium_rejects_overlap():
    artifact = plan_freemium(
        free_features=["daily plan"], paid_features=["email sends"], free_unit_cost=0.4, evidence=EV
    )
    assert "email sends" in artifact.sections[2].body
    with pytest.raises(GrowthPlanError, match="both free and paid"):
            plan_freemium(free_features=["x"], paid_features=["x"], free_unit_cost=0.1, evidence=EV)


def test_row_440_usage_based_pricing_computes_bills():
    artifact = plan_usage_based_pricing(meter="tasks", unit_price=0.05, free_allowance=100, evidence=EV)
    assert "100 tasks -> bill 0.0" in artifact.sections[1].body
    assert "spend alerts" in artifact.sections[2].body


def test_row_441_tiered_pricing_spacing_analysis():
    artifact = plan_tiered_pricing(
        tiers=[Tier(name="Basic", price=10), Tier(name="Pro", price=11), Tier(name="Team", price=60)],
        evidence=EV,
    )
    assert "+10.0%" in artifact.sections[1].body
    assert "cannot tell them apart" in artifact.sections[1].body


def test_row_442_dynamic_pricing_enforces_bounds():
    artifact = plan_dynamic_pricing(
        base_price=10,
        rules=[DynamicRule(condition="demand is high", adjustment_pct=15)],
        bounds=PriceBounds(floor=5, ceiling=12),
        evidence=EV,
    )
    assert "11.5" in artifact.sections[0].body
    with pytest.raises(GrowthPlanError, match="outside the bounds"):
        plan_dynamic_pricing(
            base_price=10,
            rules=[DynamicRule(condition="surge", adjustment_pct=50)],
            bounds=PriceBounds(floor=5, ceiling=12),
            evidence=EV,
        )


def test_row_443_bundling_rejects_dishonest_bundles():
    artifact = plan_bundling(
        products=[PricedProduct(name="A", price=10), PricedProduct(name="B", price=20)],
        bundle_price=24,
        bundle_name="AB",
        evidence=EV,
    )
    assert "20.0%" in artifact.sections[0].body
    with pytest.raises(GrowthPlanError, match="no value"):
        plan_bundling(
            products=[PricedProduct(name="A", price=10), PricedProduct(name="B", price=20)],
            bundle_price=30,
            bundle_name="AB",
            evidence=EV,
        )


def test_row_444_upselling_computes_uplift():
    artifact = plan_upselling(
        current=PricedProduct(name="Basic", price=10),
        upgrades=[PricedProduct(name="Pro", price=25)],
        evidence=EV,
    )
    assert "+150.0%" in artifact.sections[0].body


def test_row_445_cross_selling_requires_pairing_facts():
    artifact = plan_cross_selling(
        anchor=PricedProduct(name="Atlas Pro", price=12),
        complements=[PricedProduct(name="Team add-on", price=6)],
        pairing_facts=["60% of Pro users manage a team"],
        evidence=EV,
    )
    assert "Team add-on" in artifact.sections[0].body
    assert "60% of Pro users" in artifact.sections[1].body


def test_row_446_customer_success_health_bands():
    artifact = plan_customer_success(
        accounts=[
            AccountHealth(
                account="Northwind",
                signals=[
                    HealthSignal(name="weekly active", value=9, target=10),
                    HealthSignal(name="nps", value=8, target=10),
                ],
            ),
            AccountHealth(
                account="Acme",
                signals=[HealthSignal(name="weekly active", value=2, target=10)],
            ),
        ],
        evidence=EV,
    )
    body = artifact.sections[0].body
    assert "Northwind: 85.0 (healthy)" in body
    assert "Acme: 20.0 (critical)" in body


def test_row_447_onboarding_first_value_path():
    artifact = plan_onboarding(
        product="Atlas",
        steps=["connect email", "approve first plan", "see it execute"],
        target_time_to_value_minutes=15,
        evidence=EV,
    )
    assert "connect email" in artifact.sections[0].body
    assert "15 minutes" in artifact.sections[0].body


def test_row_448_support_system_no_unsupervised_autoreplies():
    artifact = design_support_system(
        channels=["email", "in-app chat"], coverage_hours="24/5", first_response_sla_minutes=30, evidence=EV
    )
    assert "email" in artifact.sections[0].body
    assert any("no unsupervised auto-replies" in c for c in artifact.scope_checks)


def test_row_449_knowledge_base_rejects_missing_solutions():
    artifact = plan_knowledge_base(
        product="Atlas",
        articles=[IssueSolution(issue="export fails", solution="reconnect the account and retry")],
        evidence=EV,
    )
    assert "reconnect the account" in artifact.sections[0].body
    with pytest.raises(GrowthPlanError):
        plan_knowledge_base(
            product="Atlas", articles=[IssueSolution(issue="export fails", solution="")], evidence=EV
        )


def test_row_450_community_support_has_escalation():
    artifact = plan_community_support(
        community_name="Atlas Builders", guidelines=["be kind", "no self-promotion"], moderators=["Udita"], evidence=EV
    )
    assert "24 hours" in artifact.sections[1].body
    assert "Udita" in artifact.sections[0].body


# --- cross-cutting invariants -----------------------------------------------------


def test_artifacts_require_some_evidence():
    with pytest.raises(GrowthPlanError, match="at least one evidence item"):
        design_sales_funnel(goal="x", evidence=[])


def test_unknown_evidence_keys_are_rejected():
    from app.modules.m05_outreach_manager.growth import ArtifactSection, _artifact

    with pytest.raises(GrowthPlanError, match="unknown evidence keys"):
        _artifact(
            kind="k",
            row=0,
            title="t",
            summary="s",
            sections=[ArtifactSection(title="s", body="b", evidence_keys=["nope"])],
            evidence=EV,
        )


# --- mounted HTTP surface ----------------------------------------------------------


def _client():
    container = m05_routes.Container.__new__(m05_routes.Container)
    container.contacts = InMemoryContactRepository()
    app = FastAPI()
    app.include_router(m05_routes.router, prefix="/api/v1")
    app.dependency_overrides[m05_routes.get_container] = lambda: container
    return TestClient(app), container


def test_growth_endpoints_are_mounted_and_evidence_checked():
    client, _ = _client()
    ok = client.post(
        "/api/v1/outreach-manager/growth/public-relations",
        json={
            "goal": "Reputation",
            "inputs": {"brand_facts": ["200 beta users"]},
            "evidence": [{"source": "founder", "fact": "200 beta users"}],
        },
    )
    assert ok.status_code == 200
    assert ok.json()["feature_row"] == 417

    no_evidence = client.post(
        "/api/v1/outreach-manager/growth/sales-funnel",
        json={"goal": "Reputation"},
    )
    assert no_evidence.status_code == 422


def test_growth_lead_scoring_and_elasticity_over_http():
    client, _ = _client()
    scoring = client.post(
        "/api/v1/outreach-manager/growth/lead-scoring",
        json={
            "inputs": {
                "leads": [{"name": "A", "attributes": {"role": "professor"}}],
                "criteria": [{"attribute": "role", "match": "professor", "points": 10, "rationale": "buyer"}],
            },
            "evidence": [{"fact": "crm export"}],
        },
    )
    assert scoring.status_code == 200
    assert scoring.json()["scores"][0]["score"] == 100.0

    elasticity = client.post(
        "/api/v1/outreach-manager/growth/price-elasticity",
        json={
            "inputs": {"points": [{"price": 10, "quantity": 100}, {"price": 12, "quantity": 70}]},
            "evidence": [{"fact": "billing export"}],
        },
    )
    assert elasticity.status_code == 200
    assert elasticity.json()["classification"] == "elastic"


def test_growth_email_marketing_uses_crm_contacts_over_http():
    client, container = _client()
    service = Service(container.contacts, approval_sink=None, scholar=None)
    verified = service.create_contact(
        ContactCreate(
            project_id="p",
            name="Founder",
            email="f@x.io",
            metadata={"enrichment": {"email_verified": True}},
        )
    )
    ok = client.post(
        "/api/v1/outreach-manager/growth/email-marketing",
        json={
            "goal": "Nurture",
            "contact_ids": [verified.id],
            "evidence": [{"fact": "beta list"}],
        },
    )
    assert ok.status_code == 200
    assert ok.json()["feature_row"] == 425

    unverified = service.create_contact(ContactCreate(project_id="p", name="Lead", email="l@y.io"))
    rejected = client.post(
        "/api/v1/outreach-manager/growth/email-marketing",
        json={"goal": "Nurture", "contact_ids": [unverified.id], "evidence": [{"fact": "beta list"}]},
    )
    assert rejected.status_code == 422
