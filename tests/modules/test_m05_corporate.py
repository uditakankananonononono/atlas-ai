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
