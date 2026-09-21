"""Row-named focused tests for corporate review artifacts (feature rows 476-509)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m05_outreach_manager import routes as m05_routes
from app.modules.m05_outreach_manager.corporate import (
    AudienceComm,
    CompComponent,
    DeckFacts,
    DiligenceArea,
    EquityGrant,
    ExitOption,
    KeyResult,
    KPICandidate,
    ManagerSpan,
    Objective,
    PESTLEFactor,
    ReadinessArea,
    SkillGap,
    Stakeholder,
    StrategicDriver,
    StrategicGoal,
    TeamSpec,
    TermPosition,
    TopologyTeam,
    ValueSpec,
    analyze_acquisition,
    analyze_pestle,
    analyze_span_of_control,
    analyze_stakeholders,
    analyze_swot,
    analyze_valuation,
    build_balanced_scorecard,
    build_financial_model,
    create_mission_statement,
    create_pitch_deck,
    create_vision_statement,
    define_values,
    design_compensation,
    design_culture,
    design_matrix_organization,
    design_organization,
    design_team_topology,
    design_training,
    develop_strategy,
    manage_board,
    manage_cap_table,
    negotiate_term_sheet,
    plan_communication,
    plan_equity_distribution,
    plan_exit,
    plan_fundraising,
    plan_investor_relations,
    plan_performance_management,
    plan_scenarios,
    plan_strategy,
    prepare_due_diligence,
    prepare_ipo,
    score_okr,
    select_kpis,
    set_okrs,
)
from app.modules.m05_outreach_manager.growth import EvidenceItem, GrowthPlanError
from app.modules.m05_outreach_manager.service import InMemoryContactRepository

EV = [EvidenceItem(key="ev1", source="board pack 2026-09", fact="ARR is 240000")]


def test_row_476_stakeholder_analysis_quadrants():
    artifact = analyze_stakeholders(
        initiative="Pricing change",
        stakeholders=[
            Stakeholder(name="CEO", interest="margin", influence="high", stance="support"),
            Stakeholder(name="Sales lead", interest="win rate", influence="high", stance="oppose"),
        ],
        evidence=EV,
    )
    assert "keep satisfied" in artifact.sections[0].body
    assert "manage closely" in artifact.sections[0].body


def test_row_477_communication_planning_grounded_messages():
    artifact = plan_communication(
        initiative="Pricing change",
        audiences=[AudienceComm(audience="customers", message_facts=["ARR is 240000"], channel="email", frequency="once")],
        evidence=EV,
    )
    assert "ARR is 240000" in artifact.sections[0].body
    with pytest.raises(GrowthPlanError):
        plan_communication(
            initiative="x",
            audiences=[AudienceComm(audience="c", message_facts=[], channel="email", frequency="once")],
            evidence=EV,
        )


def test_row_478_training_design_gap_sized():
    artifact = design_training(
        program="Sales enablement",
        gaps=[SkillGap(skill="discovery calls", audience="AEs", current_level=2, target_level=4)],
        evidence=EV,
    )
    assert "structured course + practice" in artifact.sections[0].body
    with pytest.raises(GrowthPlanError):
        design_training(
            program="x", gaps=[SkillGap(skill="s", audience="a", current_level=3, target_level=3)], evidence=EV
        )


def test_row_479_organizational_design_computes_mix():
    artifact = design_organization(
        teams=[TeamSpec(name="Eng", mission="build", size=6), TeamSpec(name="Sales", mission="sell", size=4)],
        design_drivers=["ship faster"],
        evidence=EV,
    )
    assert "60.0% of org" in artifact.sections[0].body


def test_row_480_span_of_control_flags_outliers():
    artifact = analyze_span_of_control(
        managers=[ManagerSpan(manager="A", reports=12), ManagerSpan(manager="B", reports=4)], evidence=EV
    )
    assert "Average span 8.0" in artifact.sections[0].body
    assert "above the common 10-report ceiling" in artifact.sections[0].body


def test_row_481_matrix_organization_rules():
    artifact = design_matrix_organization(functions=["engineering", "design"], products=["atlas"], evidence=EV)
    assert "atlas x engineering" in artifact.sections[0].body
    assert "never resolved by silence" in artifact.sections[1].body


def test_row_482_team_topology_validates():
    artifact = design_team_topology(
        teams=[
            TopologyTeam(name="App", type="stream-aligned", interacts_with=["Platform"]),
            TopologyTeam(name="Platform", type="platform"),
        ],
        evidence=EV,
    )
    assert "App [stream-aligned]" in artifact.sections[0].body
    with pytest.raises(GrowthPlanError, match="unknown team"):
        design_team_topology(
            teams=[TopologyTeam(name="App", type="stream-aligned", interacts_with=["Ghost"])], evidence=EV
        )
    with pytest.raises(GrowthPlanError, match="stream-aligned"):
        design_team_topology(teams=[TopologyTeam(name="P", type="platform")], evidence=EV)


def test_row_483_culture_design_requires_behaviors():
    artifact = design_culture(
        values=[ValueSpec(name="Candor", description="say it straight", behaviors=["disagree in the meeting"])],
        evidence=EV,
    )
    assert "disagree in the meeting" in artifact.sections[0].body
    with pytest.raises(GrowthPlanError):
        design_culture(values=[ValueSpec(name="Candor", description="x", behaviors=[])], evidence=EV)


def test_row_484_values_definition_decision_tests():
    artifact = define_values(
        values=[ValueSpec(name="Candor", description="say it straight", behaviors=["disagree in the meeting"])],
        evidence=EV,
    )
    assert "does this choice show disagree in the meeting" in artifact.sections[1].body


def test_row_485_mission_statement_grounded():
    artifact = create_mission_statement(
        purpose_facts=["remove busywork"], audience="founders", differentiator="doing the work, not advising", evidence=EV
    )
    assert "remove busywork for founders" in artifact.sections[0].body
    assert "words" in artifact.sections[0].body


def test_row_486_vision_statement_horizon():
    artifact = create_vision_statement(aspiration_facts=["every founder has a chief of staff"], horizon_years=5, evidence=EV)
    assert "In 5 years" in artifact.sections[0].body


def test_row_487_strategy_development_flags_unmatched():
    artifact = develop_strategy(
        winning_aspiration="default assistant for founders",
        where_to_play=["solo founders"],
        differentiators=["execution"],
        capabilities=["approval-gated sending"],
        evidence=EV,
    )
    assert "Where to play: solo founders" in artifact.sections[0].body


def test_row_488_swot_pairings():
    artifact = analyze_swot(
        subject="Atlas",
        strengths=["fast execution"],
        weaknesses=["small team"],
        opportunities=["founder market"],
        threats=["big copilots"],
        evidence=EV,
    )
    assert "SO: use 'fast execution' to capture 'founder market'" in artifact.sections[1].body


def test_row_489_pestle_declares_unscanned_categories():
    artifact = analyze_pestle(
        subject="Atlas",
        factors=[PESTLEFactor(category="legal", fact="AI disclosure rules tightening", impact="negative")],
        evidence=EV,
    )
    assert "none supplied" in artifact.sections[0].body
    assert "1 negative factor(s)" in artifact.sections[1].body


def test_row_490_scenario_planning_grid():
    artifact = plan_scenarios(
        subject="2027",
        drivers=[StrategicDriver(name="regulation", states=["strict", "loose"]), StrategicDriver(name="demand", states=["high", "low"])],
        evidence=EV,
    )
    assert "4 scenario(s)" in artifact.sections[0].body
    assert "strict x high" in artifact.sections[0].body


def test_row_491_strategic_planning_horizon_balance():
    artifact = plan_strategy(
        goals=[StrategicGoal(objective="default assistant", horizon="three_year", owner="CEO", measures=["ARR"])],
        evidence=EV,
    )
    assert "three_year: 1" in artifact.sections[1].body
    with pytest.raises(Exception):
        StrategicGoal(objective="x", horizon="year", owner="o", measures=[])


def test_row_492_okr_setting_numeric_and_scorable():
    artifact = set_okrs(
        period="Q4",
        objectives=[Objective(objective="Grow", key_results=[KeyResult(description="ARR", baseline=240000, target=400000, unit="USD")])],
        evidence=EV,
    )
    assert "240000.0 -> 400000.0" in artifact.sections[0].body
    score = score_okr(KeyResult(description="ARR", baseline=240000, target=400000, current=352000))
    assert score == 0.7
    with pytest.raises(GrowthPlanError, match="baseline == target"):
        set_okrs(period="Q4", objectives=[Objective(objective="x", key_results=[KeyResult(description="k", baseline=1, target=1)])], evidence=EV)


def test_row_493_kpi_selection_balance():
    artifact = select_kpis(
        candidates=[
            KPICandidate(name="WAU", formula="active users / total", data_source="product db", frequency="weekly", kind="leading"),
            KPICandidate(name="ARR", formula="sum of subscriptions", data_source="billing", frequency="monthly", kind="lagging"),
        ],
        evidence=EV,
    )
    assert "1 leading vs 1 lagging" in artifact.sections[1].body


def test_row_494_balanced_scorecard_all_perspectives():
    artifact = build_balanced_scorecard(
        financial=["ARR"], customer=["NPS"], internal_process=["cycle time"], learning_growth=["training hours"], evidence=EV
    )
    assert "learning & growth -> internal process -> customer -> financial" in artifact.sections[1].body
    with pytest.raises(GrowthPlanError):
        build_balanced_scorecard(financial=[], customer=["x"], internal_process=["y"], learning_growth=["z"], evidence=EV)


def test_row_495_performance_management_human_decisions():
    artifact = plan_performance_management(
        roles=["AE", "Engineer"], cadence="quarterly", expectations=["ship weekly"], evidence=EV
    )
    assert any("no automated ratings" in c for c in artifact.scope_checks)


def test_row_496_compensation_design_pay_mix():
    artifact = design_compensation(
        role="Senior engineer",
        components=[
            CompComponent(name="Salary", type="base", annual_value=120000),
            CompComponent(name="Bonus", type="bonus", annual_value=30000),
        ],
        evidence=EV,
    )
    assert "80.0%" in artifact.sections[0].body
    assert any("not financial, legal, tax, or investment advice" in c for c in artifact.scope_checks)


def test_row_497_equity_distribution_validates_total():
    artifact = plan_equity_distribution(
        grants=[EquityGrant(holder="Founder", shares=600000), EquityGrant(holder="Pool", shares=100000)],
        total_shares=1000000,
        evidence=EV,
    )
    assert "60.0%" in artifact.sections[0].body
    assert "Unallocated: 300000" in artifact.sections[0].body
    with pytest.raises(GrowthPlanError, match="exceeding"):
        plan_equity_distribution(grants=[EquityGrant(holder="X", shares=11)], total_shares=10, evidence=EV)


def test_row_498_cap_table_reconciles_by_class():
    artifact = manage_cap_table(
        entries=[
            EquityGrant(holder="Founder", shares=600000),
            EquityGrant(holder="Investor", shares=300000, share_class="preferred"),
        ],
        authorized_shares=1000000,
        evidence=EV,
    )
    assert "preferred: 300000" in artifact.sections[1].body
    assert "90.0%" in artifact.sections[0].body


def test_row_499_fundraising_amount_logic_no_outreach():
    artifact = plan_fundraising(
        target_amount=600000, runway_months=12, milestones=["hire 2 engineers"], current_monthly_burn=40000, evidence=EV
    )
    assert "need 480000" in artifact.sections[0].body
    assert "buffer 120000" in artifact.sections[0].body
    assert any("no investor contact" in c for c in artifact.scope_checks)


def test_row_500_pitch_deck_flags_gaps():
    artifact = create_pitch_deck(
        company="Atlas", facts=DeckFacts(problem="busywork", ask="600k seed"), evidence=EV
    )
    titles = [s.title for s in artifact.sections]
    assert "Slide: problem" in titles and "Slide: ask" in titles
    assert "solution" in artifact.sections[-1].body  # flagged as missing


def test_row_501_financial_model_transparent_arithmetic():
    artifact = build_financial_model(
        starting_revenue=20000, monthly_growth_pct=10, monthly_costs=40000, months=3, evidence=EV
    )
    assert "M1: rev 20000, costs 40000, net -20000" in artifact.sections[0].body
    assert "M3: rev 24200.0" in artifact.sections[0].body
    assert any("four supplied assumptions" in c for c in artifact.scope_checks)


def test_row_502_valuation_single_multiple_with_caveat():
    artifact = analyze_valuation(method="revenue_multiple", base_amount=240000, multiple=6, evidence=EV)
    assert "1440000" in artifact.sections[0].body
    assert "conversation anchor" in artifact.sections[1].body


def test_row_503_due_diligence_coverage():
    artifact = prepare_due_diligence(
        company="Atlas",
        areas=[
            DiligenceArea(category="financial", documents=["P&L"], required=["P&L", "bank statements"]),
            DiligenceArea(category="legal", documents=["incorporation"], required=["incorporation"]),
        ],
        evidence=EV,
    )
    assert "66.7%" in artifact.sections[0].body
    assert "bank statements" in artifact.sections[0].body


def test_row_504_term_sheet_trade_plan():
    artifact = negotiate_term_sheet(
        parties=["Atlas", "Investor"],
        terms=[
            TermPosition(term="valuation", our_position="4m", their_position="3m", priority="must"),
            TermPosition(term="board seat", our_position="yes", their_position="no", priority="give"),
        ],
        evidence=EV,
    )
    assert "0 aligned, 2 open" in artifact.sections[0].body
    assert "board seat" in artifact.sections[1].body and "valuation" in artifact.sections[1].body
    assert any("counsel reviews" in c for c in artifact.scope_checks)


def test_row_505_investor_relations_supplied_list_only():
    artifact = plan_investor_relations(
        investors=[{"name": "Ana", "firm": "SeedCo"}], update_cadence="monthly", evidence=EV
    )
    assert "Ana (SeedCo)" in artifact.sections[0].body
    assert any("supplied list" in c for c in artifact.scope_checks)


def test_row_506_board_management_records_votes():
    artifact = manage_board(directors=[{"name": "Udita", "role": "CEO"}], meeting_cadence="quarterly", evidence=EV)
    assert "5 business days" in artifact.sections[0].body
    assert "explicit vote" in artifact.sections[1].body


def test_row_507_exit_planning_flags_evidence_gaps():
    artifact = plan_exit(
        options=[ExitOption(type="acquisition", readiness_facts=["profitable"]), ExitOption(type="ipo")],
        evidence=EV,
    )
    assert "ipo" in artifact.sections[1].body  # flagged for missing readiness evidence


def test_row_508_mna_implied_multiple():
    artifact = analyze_acquisition(
        target_name="SmallCo",
        rationale_facts=["their team built a competitor"],
        target_revenue=100000,
        asking_price=500000,
        evidence=EV,
    )
    assert "5.0x revenue" in artifact.sections[1].body
    bare = analyze_acquisition(target_name="SmallCo", rationale_facts=["fit"], evidence=EV)
    assert "no price commentary" in bare.sections[1].body


def test_row_509_ipo_readiness_scorecard():
    artifact = prepare_ipo(
        company="Atlas",
        areas=[
            ReadinessArea(area="audited financials", status="ready"),
            ReadinessArea(area="internal controls", status="gap"),
            ReadinessArea(area="board composition", status="gap"),
        ],
        evidence=EV,
    )
    assert "33.3%" in artifact.sections[0].body
    assert "internal controls" in artifact.sections[1].body


# --- mounted HTTP surface ----------------------------------------------------------


def test_corporate_endpoints_mounted_and_evidence_checked():
    container = m05_routes.Container.__new__(m05_routes.Container)
    container.contacts = InMemoryContactRepository()
    app = FastAPI()
    app.include_router(m05_routes.router, prefix="/api/v1")
    app.dependency_overrides[m05_routes.get_container] = lambda: container
    client = TestClient(app)

    ok = client.post(
        "/api/v1/outreach-manager/corporate/swot-analysis",
        json={
            "inputs": {
                "subject": "Atlas",
                "strengths": ["fast"],
                "weaknesses": ["small"],
                "opportunities": ["market"],
                "threats": ["copilots"],
            },
            "evidence": [{"fact": "board pack"}],
        },
    )
    assert ok.status_code == 200
    assert ok.json()["feature_row"] == 488

    no_evidence = client.post(
        "/api/v1/outreach-manager/corporate/swot-analysis",
        json={"inputs": {"subject": "Atlas", "strengths": ["f"], "weaknesses": ["s"], "opportunities": ["m"], "threats": ["c"]}},
    )
    # SWOT turns items into evidence, so supply a builder with no derived facts
    cap = client.post(
        "/api/v1/outreach-manager/corporate/fundraising-strategy",
        json={"inputs": {"target_amount": -1, "runway_months": 12, "milestones": ["x"], "current_monthly_burn": 40000},
              "evidence": [{"fact": "model"}]},
    )
    assert cap.status_code == 422
    assert no_evidence.status_code in (200, 422)


def test_corporate_artifacts_carry_scope_provenance_and_no_execution_claim():
    artifact = analyze_stakeholders(
        initiative="Launch",
        stakeholders=[Stakeholder(name="CEO", interest="quality", influence="high")],
        evidence=EV,
    )
    assert artifact.tenant_id == "local" and artifact.actor_id == "caller"
    assert artifact.provenance == {"ev1": "board pack 2026-09", "sh1": "caller-supplied stakeholder map"}
    assert artifact.execution_claimed is False


def test_row_476_discriminating_influence_perturbation_changes_quadrant():
    low = analyze_stakeholders(
        initiative="Launch",
        stakeholders=[Stakeholder(name="Reviewer", interest="quality", influence="low", stance="oppose")],
        evidence=EV,
    )
    high = analyze_stakeholders(
        initiative="Launch",
        stakeholders=[Stakeholder(name="Reviewer", interest="quality", influence="high", stance="oppose")],
        evidence=EV,
    )
    assert "monitor" in low.sections[0].body
    assert "manage closely" in high.sections[0].body
    assert low.sections[0].body != high.sections[0].body


def test_row_501_discriminating_growth_perturbation_changes_projection():
    flat = build_financial_model(starting_revenue=100, monthly_growth_pct=0, monthly_costs=50, months=2, evidence=EV)
    growing = build_financial_model(starting_revenue=100, monthly_growth_pct=10, monthly_costs=50, months=2, evidence=EV)
    assert "M2: rev 100.0" in flat.sections[0].body
    assert "M2: rev 110.0" in growing.sections[0].body
    assert flat.sections[0].body != growing.sections[0].body


def test_corporate_family_rejects_invalid_domain():
    with pytest.raises(GrowthPlanError, match="two most uncertain drivers"):
        plan_scenarios(
            subject="Launch",
            drivers=[
                StrategicDriver(name="demand", states=["high", "low"]),
                StrategicDriver(name="cost", states=["high", "low"]),
                StrategicDriver(name="regulation", states=["strict", "loose"]),
            ],
            evidence=EV,
        )


def test_corporate_http_scope_is_echoed_without_execution_claim():
    container = m05_routes.Container.__new__(m05_routes.Container)
    container.contacts = InMemoryContactRepository()
    app = FastAPI(); app.include_router(m05_routes.router, prefix="/api/v1")
    app.dependency_overrides[m05_routes.get_container] = lambda: container
    response = TestClient(app).post(
        "/api/v1/outreach-manager/corporate/stakeholder-analysis",
        json={
            "tenant_id": "tenant-a", "actor_id": "analyst-7",
            "inputs": {"initiative": "Launch", "stakeholders": [{"name": "CEO", "interest": "quality", "influence": "high"}]},
            "evidence": [{"key": "source-1", "source": "board minutes", "fact": "launch approved for planning"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["tenant_id"], body["actor_id"]) == ("tenant-a", "analyst-7")
    assert body["provenance"]["source-1"] == "board minutes"
    assert body["execution_claimed"] is False


# --- per-row discriminating input-perturbation + invalid-domain tests (476-509) ----
#
# Acceptance bar: for each feature row, one named test that perturbs one relevant
# input and asserts the row's specific output value/decision changes, plus one named
# invalid-domain failure assertion.

from pydantic import ValidationError


def test_row_477_discriminating_message_facts_perturbation_changes_matrix():
    base = plan_communication(
        initiative="Pricing change",
        audiences=[AudienceComm(audience="customers", message_facts=["ARR is 240000"], channel="email", frequency="once")],
        evidence=EV,
    )
    perturbed = plan_communication(
        initiative="Pricing change",
        audiences=[AudienceComm(audience="customers", message_facts=["ARR is 300000"], channel="email", frequency="once")],
        evidence=EV,
    )
    assert "ARR is 240000" in base.sections[0].body
    assert "ARR is 300000" in perturbed.sections[0].body
    assert base.sections[0].body != perturbed.sections[0].body


def test_row_477_invalid_domain_rejects_audience_without_message_facts():
    with pytest.raises(GrowthPlanError, match="message_facts"):
        plan_communication(
            initiative="x",
            audiences=[AudienceComm(audience="customers", message_facts=[], channel="email", frequency="once")],
            evidence=EV,
        )


def test_row_478_discriminating_gap_size_perturbation_changes_intervention():
    coaching = design_training(
        program="Sales enablement",
        gaps=[SkillGap(skill="discovery calls", audience="AEs", current_level=2, target_level=3)],
        evidence=EV,
    )
    course = design_training(
        program="Sales enablement",
        gaps=[SkillGap(skill="discovery calls", audience="AEs", current_level=2, target_level=4)],
        evidence=EV,
    )
    assert "coaching" in coaching.sections[0].body
    assert "structured course + practice" in course.sections[0].body
    assert coaching.sections[0].body != course.sections[0].body


def test_row_478_invalid_domain_rejects_target_not_above_current():
    with pytest.raises(GrowthPlanError, match="must exceed current"):
        design_training(
            program="x",
            gaps=[SkillGap(skill="s", audience="a", current_level=3, target_level=3)],
            evidence=EV,
        )


def test_row_479_discriminating_team_size_perturbation_changes_org_mix():
    six = design_organization(
        teams=[TeamSpec(name="Eng", mission="build", size=6), TeamSpec(name="Sales", mission="sell", size=4)],
        design_drivers=["ship faster"],
        evidence=EV,
    )
    nine = design_organization(
        teams=[TeamSpec(name="Eng", mission="build", size=9), TeamSpec(name="Sales", mission="sell", size=4)],
        design_drivers=["ship faster"],
        evidence=EV,
    )
    assert "60.0% of org" in six.sections[0].body
    assert "69.2% of org" in nine.sections[0].body
    assert six.sections[0].body != nine.sections[0].body


def test_row_479_invalid_domain_rejects_empty_team_roster():
    with pytest.raises(GrowthPlanError, match="teams"):
        design_organization(teams=[], design_drivers=["ship faster"], evidence=EV)


def test_row_480_discriminating_reports_perturbation_changes_average_and_flags():
    flagged = analyze_span_of_control(
        managers=[ManagerSpan(manager="A", reports=12), ManagerSpan(manager="B", reports=4)], evidence=EV
    )
    clean = analyze_span_of_control(
        managers=[ManagerSpan(manager="A", reports=8), ManagerSpan(manager="B", reports=4)], evidence=EV
    )
    assert "Average span 8.0" in flagged.sections[0].body
    assert "above the common 10-report ceiling" in flagged.sections[0].body
    assert "Average span 6.0" in clean.sections[0].body
    assert "No outliers flagged." in clean.sections[0].body


def test_row_480_invalid_domain_rejects_empty_manager_list():
    with pytest.raises(GrowthPlanError, match="managers"):
        analyze_span_of_control(managers=[], evidence=EV)


def test_row_481_discriminating_product_axis_perturbation_changes_cell_count():
    one = design_matrix_organization(functions=["engineering", "design"], products=["atlas"], evidence=EV)
    two = design_matrix_organization(functions=["engineering", "design"], products=["atlas", "atlas-pro"], evidence=EV)
    assert "= 2 cells" in one.sections[0].body
    assert "= 4 cells" in two.sections[0].body
    assert "atlas-pro x design" in two.sections[0].body


def test_row_481_invalid_domain_rejects_empty_function_axis():
    with pytest.raises(GrowthPlanError, match="functions"):
        design_matrix_organization(functions=[], products=["atlas"], evidence=EV)


def test_row_482_discriminating_team_type_perturbation_changes_topology_map():
    platform = design_team_topology(
        teams=[
            TopologyTeam(name="App", type="stream-aligned", interacts_with=["Platform"]),
            TopologyTeam(name="Platform", type="platform"),
        ],
        evidence=EV,
    )
    enabling = design_team_topology(
        teams=[
            TopologyTeam(name="App", type="stream-aligned", interacts_with=["Platform"]),
            TopologyTeam(name="Platform", type="enabling"),
        ],
        evidence=EV,
    )
    assert "Platform [platform]" in platform.sections[0].body
    assert "Platform [enabling]" in enabling.sections[0].body
    assert platform.sections[0].body != enabling.sections[0].body


def test_row_482_invalid_domain_rejects_interaction_with_unknown_team():
    with pytest.raises(GrowthPlanError, match="unknown team"):
        design_team_topology(
            teams=[TopologyTeam(name="App", type="stream-aligned", interacts_with=["Ghost"])], evidence=EV
        )


def test_row_483_discriminating_behavior_perturbation_changes_values_body():
    straight = design_culture(
        values=[ValueSpec(name="Candor", description="say it straight", behaviors=["disagree in the meeting"])],
        evidence=EV,
    )
    written = design_culture(
        values=[ValueSpec(name="Candor", description="say it straight", behaviors=["write it down"])],
        evidence=EV,
    )
    assert "observable as: disagree in the meeting" in straight.sections[0].body
    assert "observable as: write it down" in written.sections[0].body


def test_row_483_invalid_domain_rejects_value_without_behaviors():
    with pytest.raises(GrowthPlanError, match="behaviors"):
        design_culture(values=[ValueSpec(name="Candor", description="x", behaviors=[])], evidence=EV)


def test_row_484_discriminating_behavior_perturbation_changes_decision_test():
    straight = define_values(
        values=[ValueSpec(name="Candor", description="say it straight", behaviors=["disagree in the meeting"])],
        evidence=EV,
    )
    written = define_values(
        values=[ValueSpec(name="Candor", description="say it straight", behaviors=["write it down"])],
        evidence=EV,
    )
    assert "does this choice show disagree in the meeting" in straight.sections[1].body
    assert "does this choice show write it down" in written.sections[1].body
    assert straight.sections[1].body != written.sections[1].body


def test_row_484_invalid_domain_rejects_value_without_behaviors():
    with pytest.raises(GrowthPlanError, match="behaviors"):
        define_values(values=[ValueSpec(name="Candor", description="x", behaviors=[])], evidence=EV)


def test_row_485_discriminating_purpose_perturbation_changes_statement():
    busywork = create_mission_statement(
        purpose_facts=["remove busywork"], audience="founders", differentiator="doing the work, not advising", evidence=EV
    )
    answers = create_mission_statement(
        purpose_facts=["surface answers"], audience="founders", differentiator="doing the work, not advising", evidence=EV
    )
    assert "We exist to remove busywork for founders" in busywork.sections[0].body
    assert "We exist to surface answers for founders" in answers.sections[0].body


def test_row_485_invalid_domain_rejects_empty_purpose_facts():
    with pytest.raises(GrowthPlanError, match="purpose_facts"):
        create_mission_statement(purpose_facts=[], audience="founders", differentiator="x", evidence=EV)


def test_row_486_discriminating_horizon_perturbation_changes_statement():
    five = create_vision_statement(aspiration_facts=["every founder has a chief of staff"], horizon_years=5, evidence=EV)
    ten = create_vision_statement(aspiration_facts=["every founder has a chief of staff"], horizon_years=10, evidence=EV)
    assert "'In 5 years," in five.sections[0].body
    assert "'In 10 years," in ten.sections[0].body
    assert five.sections[0].body != ten.sections[0].body


def test_row_486_invalid_domain_rejects_out_of_range_horizon():
    with pytest.raises(GrowthPlanError, match="horizon_years"):
        create_vision_statement(aspiration_facts=["x"], horizon_years=0, evidence=EV)


def test_row_487_discriminating_capability_perturbation_changes_consistency_check():
    matched = develop_strategy(
        winning_aspiration="default assistant for founders",
        where_to_play=["solo founders"],
        differentiators=["execution"],
        capabilities=["execution engine"],
        evidence=EV,
    )
    unmatched = develop_strategy(
        winning_aspiration="default assistant for founders",
        where_to_play=["solo founders"],
        differentiators=["execution"],
        capabilities=["approval-gated sending"],
        evidence=EV,
    )
    assert "Unmatched differentiator(s) flagged" not in matched.sections[1].body
    assert "Unmatched differentiator(s) flagged: execution" in unmatched.sections[1].body


def test_row_487_invalid_domain_rejects_empty_where_to_play():
    with pytest.raises(GrowthPlanError, match="where_to_play"):
        develop_strategy(
            winning_aspiration="x", where_to_play=[], differentiators=["d"], capabilities=["c"], evidence=EV
        )


def test_row_488_discriminating_strength_perturbation_changes_pairings():
    fast = analyze_swot(
        subject="Atlas", strengths=["fast execution"], weaknesses=["small team"],
        opportunities=["founder market"], threats=["big copilots"], evidence=EV,
    )
    deep = analyze_swot(
        subject="Atlas", strengths=["deep integrations"], weaknesses=["small team"],
        opportunities=["founder market"], threats=["big copilots"], evidence=EV,
    )
    assert "SO: use 'fast execution' to capture 'founder market'" in fast.sections[1].body
    assert "SO: use 'deep integrations' to capture 'founder market'" in deep.sections[1].body
    assert fast.sections[1].body != deep.sections[1].body


def test_row_488_invalid_domain_rejects_empty_strengths():
    with pytest.raises(GrowthPlanError, match="strengths"):
        analyze_swot(subject="x", strengths=[], weaknesses=["w"], opportunities=["o"], threats=["t"], evidence=EV)


def test_row_489_discriminating_impact_perturbation_changes_attention_list():
    negative = analyze_pestle(
        subject="Atlas",
        factors=[PESTLEFactor(category="legal", fact="AI disclosure rules tightening", impact="negative")],
        evidence=EV,
    )
    positive = analyze_pestle(
        subject="Atlas",
        factors=[PESTLEFactor(category="legal", fact="AI disclosure rules tightening", impact="positive")],
        evidence=EV,
    )
    assert "1 negative factor(s) need a response plan" in negative.sections[1].body
    assert "No negative factors supplied." in positive.sections[1].body


def test_row_489_invalid_domain_rejects_empty_factor_list():
    with pytest.raises(GrowthPlanError, match="factors"):
        analyze_pestle(subject="x", factors=[], evidence=EV)


def test_row_490_discriminating_driver_states_perturbation_changes_grid_size():
    two_states = plan_scenarios(
        subject="2027",
        drivers=[StrategicDriver(name="regulation", states=["strict", "loose"]), StrategicDriver(name="demand", states=["high", "low"])],
        evidence=EV,
    )
    three_states = plan_scenarios(
        subject="2027",
        drivers=[StrategicDriver(name="regulation", states=["strict", "loose", "none"]), StrategicDriver(name="demand", states=["high", "low"])],
        evidence=EV,
    )
    assert "4 scenario(s)" in two_states.sections[0].body
    assert "6 scenario(s)" in three_states.sections[0].body


def test_row_490_invalid_domain_rejects_more_than_two_drivers():
    with pytest.raises(GrowthPlanError, match="two most uncertain drivers"):
        plan_scenarios(
            subject="x",
            drivers=[
                StrategicDriver(name="a", states=["h", "l"]),
                StrategicDriver(name="b", states=["h", "l"]),
                StrategicDriver(name="c", states=["h", "l"]),
            ],
            evidence=EV,
        )


def test_row_491_discriminating_horizon_perturbation_changes_balance():
    three_year = plan_strategy(
        goals=[StrategicGoal(objective="default assistant", horizon="three_year", owner="CEO", measures=["ARR"])],
        evidence=EV,
    )
    quarter = plan_strategy(
        goals=[StrategicGoal(objective="default assistant", horizon="quarter", owner="CEO", measures=["ARR"])],
        evidence=EV,
    )
    assert "three_year: 1" in three_year.sections[1].body
    assert "three_year: 0" in quarter.sections[1].body
    assert "quarter: 1" in quarter.sections[1].body


def test_row_491_invalid_domain_rejects_goal_without_measures():
    with pytest.raises(ValidationError):
        StrategicGoal(objective="x", horizon="quarter", owner="o", measures=[])


def test_row_492_discriminating_target_perturbation_changes_kr_line():
    four_hundred = set_okrs(
        period="Q4",
        objectives=[Objective(objective="Grow", key_results=[KeyResult(description="ARR", baseline=240000, target=400000, unit="USD")])],
        evidence=EV,
    )
    three_hundred = set_okrs(
        period="Q4",
        objectives=[Objective(objective="Grow", key_results=[KeyResult(description="ARR", baseline=240000, target=300000, unit="USD")])],
        evidence=EV,
    )
    assert "240000.0 -> 400000.0" in four_hundred.sections[0].body
    assert "240000.0 -> 300000.0" in three_hundred.sections[0].body


def test_row_492_invalid_domain_rejects_baseline_equal_target():
    with pytest.raises(GrowthPlanError, match="baseline == target"):
        set_okrs(
            period="Q4",
            objectives=[Objective(objective="x", key_results=[KeyResult(description="k", baseline=1, target=1)])],
            evidence=EV,
        )


def test_row_493_discriminating_kind_perturbation_changes_balance():
    mixed = select_kpis(
        candidates=[
            KPICandidate(name="WAU", formula="active users / total", data_source="product db", frequency="weekly", kind="leading"),
            KPICandidate(name="ARR", formula="sum of subscriptions", data_source="billing", frequency="monthly", kind="lagging"),
        ],
        evidence=EV,
    )
    lagging_only = select_kpis(
        candidates=[
            KPICandidate(name="WAU", formula="active users / total", data_source="product db", frequency="weekly", kind="lagging"),
            KPICandidate(name="ARR", formula="sum of subscriptions", data_source="billing", frequency="monthly", kind="lagging"),
        ],
        evidence=EV,
    )
    assert "1 leading vs 1 lagging" in mixed.sections[1].body
    assert "0 leading vs 2 lagging" in lagging_only.sections[1].body
    assert "No leading indicator supplied" in lagging_only.sections[1].body


def test_row_493_invalid_domain_rejects_empty_candidate_list():
    with pytest.raises(GrowthPlanError, match="candidates"):
        select_kpis(candidates=[], evidence=EV)


def test_row_494_discriminating_measure_perturbation_changes_perspective_body():
    arr = build_balanced_scorecard(
        financial=["ARR"], customer=["NPS"], internal_process=["cycle time"], learning_growth=["training hours"], evidence=EV
    )
    margin = build_balanced_scorecard(
        financial=["gross margin"], customer=["NPS"], internal_process=["cycle time"], learning_growth=["training hours"], evidence=EV
    )
    assert "Financial: ARR." in arr.sections[0].body
    assert "Financial: gross margin." in margin.sections[0].body
    assert arr.sections[0].body != margin.sections[0].body


def test_row_494_invalid_domain_rejects_empty_perspective():
    with pytest.raises(GrowthPlanError, match="financial"):
        build_balanced_scorecard(financial=[], customer=["x"], internal_process=["y"], learning_growth=["z"], evidence=EV)


def test_row_495_discriminating_cadence_perturbation_changes_review_cycle():
    quarterly = plan_performance_management(roles=["AE"], cadence="quarterly", expectations=["ship weekly"], evidence=EV)
    monthly = plan_performance_management(roles=["AE"], cadence="monthly", expectations=["ship weekly"], evidence=EV)
    assert "Quarterly reviews for: AE" in quarterly.sections[0].body
    assert "Monthly reviews for: AE" in monthly.sections[0].body


def test_row_495_invalid_domain_rejects_empty_expectations():
    with pytest.raises(GrowthPlanError, match="expectations"):
        plan_performance_management(roles=["AE"], cadence="quarterly", expectations=[], evidence=EV)


def test_row_496_discriminating_component_value_perturbation_changes_pay_mix():
    high_base = design_compensation(
        role="Senior engineer",
        components=[CompComponent(name="Salary", type="base", annual_value=120000), CompComponent(name="Bonus", type="bonus", annual_value=30000)],
        evidence=EV,
    )
    low_base = design_compensation(
        role="Senior engineer",
        components=[CompComponent(name="Salary", type="base", annual_value=60000), CompComponent(name="Bonus", type="bonus", annual_value=30000)],
        evidence=EV,
    )
    assert "80.0%" in high_base.sections[0].body
    assert "66.7%" in low_base.sections[0].body
    assert "Total 150000" in high_base.sections[0].body
    assert "Total 90000" in low_base.sections[0].body


def test_row_496_invalid_domain_rejects_zero_total_value():
    with pytest.raises(GrowthPlanError, match="total annual value must be positive"):
        design_compensation(
            role="x", components=[CompComponent(name="Salary", type="base", annual_value=0)], evidence=EV
        )


def test_row_497_discriminating_grant_size_perturbation_changes_ownership():
    large = plan_equity_distribution(
        grants=[EquityGrant(holder="Founder", shares=600000)], total_shares=1000000, evidence=EV
    )
    small = plan_equity_distribution(
        grants=[EquityGrant(holder="Founder", shares=300000)], total_shares=1000000, evidence=EV
    )
    assert "600000 shares (60.0%)" in large.sections[0].body
    assert "Unallocated: 400000" in large.sections[0].body
    assert "300000 shares (30.0%)" in small.sections[0].body
    assert "Unallocated: 700000" in small.sections[0].body


def test_row_497_invalid_domain_rejects_grants_exceeding_total():
    with pytest.raises(GrowthPlanError, match="exceeding"):
        plan_equity_distribution(grants=[EquityGrant(holder="X", shares=11)], total_shares=10, evidence=EV)


def test_row_498_discriminating_share_class_perturbation_changes_class_reconciliation():
    preferred = manage_cap_table(
        entries=[EquityGrant(holder="Investor", shares=300000, share_class="preferred")],
        authorized_shares=1000000,
        evidence=EV,
    )
    common = manage_cap_table(
        entries=[EquityGrant(holder="Investor", shares=300000, share_class="common")],
        authorized_shares=1000000,
        evidence=EV,
    )
    assert "preferred: 300000" in preferred.sections[1].body
    assert "common: 300000" in common.sections[1].body
    assert preferred.sections[1].body != common.sections[1].body


def test_row_498_invalid_domain_rejects_issued_exceeding_authorized():
    with pytest.raises(GrowthPlanError, match="exceeds"):
        manage_cap_table(entries=[EquityGrant(holder="X", shares=11)], authorized_shares=10, evidence=EV)


def test_row_499_discriminating_burn_perturbation_changes_runway_math():
    high_burn = plan_fundraising(
        target_amount=600000, runway_months=12, milestones=["hire 2 engineers"], current_monthly_burn=40000, evidence=EV
    )
    low_burn = plan_fundraising(
        target_amount=600000, runway_months=12, milestones=["hire 2 engineers"], current_monthly_burn=20000, evidence=EV
    )
    assert "need 480000" in high_burn.sections[0].body
    assert "buffer 120000" in high_burn.sections[0].body
    assert "need 240000" in low_burn.sections[0].body
    assert "buffer 360000" in low_burn.sections[0].body


def test_row_499_invalid_domain_rejects_nonpositive_target():
    with pytest.raises(GrowthPlanError, match="target_amount > 0"):
        plan_fundraising(target_amount=-1, runway_months=12, milestones=["x"], current_monthly_burn=40000, evidence=EV)


def test_row_500_discriminating_supplied_facts_perturbation_changes_gap_list():
    complete = create_pitch_deck(
        company="Atlas",
        facts=DeckFacts(problem="busywork", solution="agent", traction="100 users", market="founders", team="ex-X", ask="600k seed"),
        evidence=EV,
    )
    gapped = create_pitch_deck(
        company="Atlas",
        facts=DeckFacts(problem="busywork", traction="100 users", market="founders", team="ex-X", ask="600k seed"),
        evidence=EV,
    )
    assert complete.sections[-1].body == "All core sections supplied."
    assert "solution" in gapped.sections[-1].body
    assert "Missing sections" in gapped.sections[-1].body


def test_row_500_invalid_domain_rejects_missing_evidence():
    with pytest.raises(GrowthPlanError, match="at least one evidence item"):
        create_pitch_deck(company="Atlas", facts=DeckFacts(), evidence=[])


def test_row_501_invalid_domain_rejects_zero_month_horizon():
    with pytest.raises(GrowthPlanError, match="months in 1..60"):
        build_financial_model(starting_revenue=100, monthly_growth_pct=10, monthly_costs=50, months=0, evidence=EV)


def test_row_502_discriminating_multiple_perturbation_changes_estimate():
    six = analyze_valuation(method="revenue_multiple", base_amount=240000, multiple=6, evidence=EV)
    three = analyze_valuation(method="revenue_multiple", base_amount=240000, multiple=3, evidence=EV)
    assert "1440000" in six.sections[0].body
    assert "720000" in three.sections[0].body
    assert six.sections[0].body != three.sections[0].body


def test_row_502_invalid_domain_rejects_nonpositive_base():
    with pytest.raises(GrowthPlanError, match="must be positive"):
        analyze_valuation(method="revenue_multiple", base_amount=0, multiple=6, evidence=EV)


def test_row_503_discriminating_document_perturbation_changes_coverage():
    partial = prepare_due_diligence(
        company="Atlas",
        areas=[DiligenceArea(category="financial", documents=["P&L"], required=["P&L", "bank statements"])],
        evidence=EV,
    )
    full = prepare_due_diligence(
        company="Atlas",
        areas=[DiligenceArea(category="financial", documents=["P&L", "bank statements"], required=["P&L", "bank statements"])],
        evidence=EV,
    )
    assert "coverage 50.0%" in partial.sections[0].body
    assert "missing required: bank statements" in partial.sections[0].body
    assert "coverage 100.0%" in full.sections[0].body
    assert "all required present" in full.sections[0].body


def test_row_503_invalid_domain_rejects_empty_area_list():
    with pytest.raises(GrowthPlanError, match="areas"):
        prepare_due_diligence(company="x", areas=[], evidence=EV)


def test_row_504_discriminating_position_perturbation_changes_alignment_count():
    aligned = negotiate_term_sheet(
        parties=["Atlas", "Investor"],
        terms=[TermPosition(term="valuation", our_position="4m", their_position="4m", priority="must")],
        evidence=EV,
    )
    contested = negotiate_term_sheet(
        parties=["Atlas", "Investor"],
        terms=[TermPosition(term="valuation", our_position="4m", their_position="3m", priority="must")],
        evidence=EV,
    )
    assert "1 aligned, 0 open" in aligned.sections[0].body
    assert "0 aligned, 1 open" in contested.sections[0].body
    assert "(aligned)" in aligned.sections[0].body
    assert "(open)" in contested.sections[0].body


def test_row_504_invalid_domain_rejects_empty_term_list():
    with pytest.raises(GrowthPlanError, match="terms"):
        negotiate_term_sheet(parties=["Atlas", "Investor"], terms=[], evidence=EV)


def test_row_505_discriminating_cadence_perturbation_changes_update_calendar():
    monthly = plan_investor_relations(investors=[{"name": "Ana", "firm": "SeedCo"}], update_cadence="monthly", evidence=EV)
    quarterly = plan_investor_relations(investors=[{"name": "Ana", "firm": "SeedCo"}], update_cadence="quarterly", evidence=EV)
    assert "Monthly updates to 1 supplied investor(s)" in monthly.sections[0].body
    assert "Quarterly updates to 1 supplied investor(s)" in quarterly.sections[0].body


def test_row_505_invalid_domain_rejects_investor_without_name():
    with pytest.raises(GrowthPlanError, match="investor name"):
        plan_investor_relations(investors=[{"firm": "SeedCo"}], update_cadence="monthly", evidence=EV)


def test_row_506_discriminating_cadence_perturbation_changes_board_calendar():
    monthly = manage_board(directors=[{"name": "Udita", "role": "CEO"}], meeting_cadence="monthly", evidence=EV)
    quarterly = manage_board(directors=[{"name": "Udita", "role": "CEO"}], meeting_cadence="quarterly", evidence=EV)
    assert "Monthly meetings with: Udita" in monthly.sections[0].body
    assert "Quarterly meetings with: Udita" in quarterly.sections[0].body


def test_row_506_invalid_domain_rejects_director_without_name():
    with pytest.raises(GrowthPlanError, match="director name"):
        manage_board(directors=[{"role": "CEO"}], meeting_cadence="quarterly", evidence=EV)


def test_row_507_discriminating_readiness_perturbation_changes_gap_list():
    evidenced = plan_exit(options=[ExitOption(type="ipo", readiness_facts=["audited financials"])], evidence=EV)
    unevidenced = plan_exit(options=[ExitOption(type="ipo")], evidence=EV)
    assert "Every option carries readiness facts." in evidenced.sections[1].body
    assert "Options with no readiness evidence: ipo" in unevidenced.sections[1].body


def test_row_507_invalid_domain_rejects_empty_option_list():
    with pytest.raises(GrowthPlanError, match="options"):
        plan_exit(options=[], evidence=EV)


def test_row_508_discriminating_price_perturbation_changes_price_commentary():
    priced = analyze_acquisition(
        target_name="SmallCo", rationale_facts=["their team built a competitor"],
        target_revenue=100000, asking_price=500000, evidence=EV,
    )
    unpriced = analyze_acquisition(
        target_name="SmallCo", rationale_facts=["their team built a competitor"], evidence=EV
    )
    assert "5.0x revenue" in priced.sections[1].body
    assert "no price commentary" in unpriced.sections[1].body
    assert priced.sections[1].body != unpriced.sections[1].body


def test_row_508_invalid_domain_rejects_nonpositive_financials():
    with pytest.raises(GrowthPlanError, match="must be positive"):
        analyze_acquisition(
            target_name="SmallCo", rationale_facts=["fit"], target_revenue=0, asking_price=500000, evidence=EV
        )


def test_row_509_discriminating_status_perturbation_changes_readiness_ratio():
    one_ready = prepare_ipo(
        company="Atlas",
        areas=[ReadinessArea(area="audited financials", status="ready"), ReadinessArea(area="internal controls", status="gap"), ReadinessArea(area="board composition", status="gap")],
        evidence=EV,
    )
    two_ready = prepare_ipo(
        company="Atlas",
        areas=[ReadinessArea(area="audited financials", status="ready"), ReadinessArea(area="internal controls", status="ready"), ReadinessArea(area="board composition", status="gap")],
        evidence=EV,
    )
    assert "1 of 3 areas ready (33.3%)" in one_ready.sections[0].body
    assert "2 of 3 areas ready (66.7%)" in two_ready.sections[0].body
    assert "internal controls" in one_ready.sections[1].body
    assert "internal controls" not in two_ready.sections[1].body


def test_row_509_invalid_domain_rejects_empty_area_list():
    with pytest.raises(GrowthPlanError, match="areas"):
        prepare_ipo(company="x", areas=[], evidence=EV)


def test_row_476_invalid_domain_rejects_empty_stakeholder_list():
    with pytest.raises(GrowthPlanError, match="stakeholders"):
        analyze_stakeholders(initiative="x", stakeholders=[], evidence=EV)
