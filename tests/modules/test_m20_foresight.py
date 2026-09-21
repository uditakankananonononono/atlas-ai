"""Focused tests for rows 35-59: simulation, forecasting, decision analysis."""
import math

import pytest

from app.modules.m20_general_cognitive_worker.foresight import (
    DECISION_SUPPORT_CAVEAT, AntifragilityAssessor, AsymmetryFinder,
    BaseRateIntegrator, BayesianUpdater, CausalAssessor, ConstraintAnalyzer,
    EVCalculator, HypothesisTracker, InsightCapture, KellySizer, LeverageFinder,
    OptimismCalibrator, OptionalityAnalyzer, OutsideView, PlanningFallacyCorrector, PremortemEngine,
    RedTeamer, ReferenceClassForecaster, ReversibilityAssessor,
    RiskOfRuinAnalyzer, ScenarioPlanner, SecondOrderTracer, SerendipityEngine,
    SimulationFidelityTracker, SystemsModel,
)
from app.modules.m20_general_cognitive_worker.semantic_memory import SemanticMemory


def test_row35_serendipity_slots_bounded_and_seeded():
    engine = SerendipityEngine(epsilon=0.4)
    gaps = ["caching", "pricing", "onboarding"]
    a = engine.plan(gaps, available_slots=10, seed=7)
    b = engine.plan(gaps, available_slots=10, seed=7)
    assert [s.action for s in a] == [s.action for s in b]  # reproducible
    assert 0 < len(a) <= round(10 * 0.4)  # bounded by epsilon
    assert all(s.source_gap in gaps for s in a)
    collisions = engine.plan([], available_slots=5, known_topics=["graph", "cooking"], seed=1)
    assert len(collisions) == 1 and collisions[0].source_gap.startswith("collision:")


def test_row36_insight_capture_links_and_develops():
    mem = SemanticMemory()
    mem.remember("python packaging uses pyproject", kind="fact")
    cap = InsightCapture()
    insight = cap.capture("a cli that lints pyproject files", context="shower thought",
                          semantic_memory=mem)
    assert insight.links  # auto-linked to related memory
    assert insight.status == "captured"
    prompts = cap.development_prompts(insight.insight_id)
    assert any("smallest test" in p for p in prompts)
    cap.develop(insight.insight_id, "prototype with click")
    assert cap.insights[insight.insight_id].status == "developed"
    stale = cap.stale(older_than_days=-1)  # everything is stale with a negative cutoff
    assert stale == []  # developed insights are not stale


def test_row37_simulation_fidelity_calibration():
    tracker = SimulationFidelityTracker()
    r1 = tracker.record_prediction("estimates", 10.0, confidence=0.9)
    tracker.resolve(r1.record_id, 10.0)
    r2 = tracker.record_prediction("estimates", 10.0, confidence=0.9)
    tracker.resolve(r2.record_id, 20.0)
    f = tracker.fidelity(domain="estimates")
    assert f == pytest.approx((1.0 + 0.5) / 2)
    assert tracker.confidence_adjustment(domain="estimates") == pytest.approx(0.75)
    assert tracker.confidence_adjustment(domain="unknown") == 1.0


def test_row38_parallel_hypotheses_renormalize_and_retire():
    tracker = HypothesisTracker()
    a = tracker.add("cache bug", prior=0.4)
    b = tracker.add("network flakiness", prior=0.4)
    c = tracker.add("user error", prior=0.2)
    ranking = tracker.update({a.hypothesis_id: 3.0, b.hypothesis_id: 0.2, c.hypothesis_id: 0.01})
    assert ranking[0].hypothesis_id == a.hypothesis_id
    total = sum(h.probability for h in ranking)
    assert total == pytest.approx(1.0)
    assert tracker.hypotheses[c.hypothesis_id].status == "retired"


def test_row39_bayesian_updates():
    assert BayesianUpdater.update(0.5, 3.0) == pytest.approx(0.75)
    assert BayesianUpdater.update_binary(0.01, sensitivity=0.9, specificity=0.9) == pytest.approx(
        0.009 / (0.009 + 0.099), rel=1e-6)
    seq = BayesianUpdater.sequence(0.5, [2.0, 2.0, 0.5])
    assert seq == pytest.approx([2 / 3, 0.8, 2 / 3])
    beta = BayesianUpdater.update_beta(1.0, 1.0, successes=7, failures=3)
    assert beta["mean"] == pytest.approx(0.8 / 1.2 * 1.2 / 1.2)  # 8/12
    assert beta["mean"] == pytest.approx(8 / 12)


def test_row40_causal_vs_correlational():
    assessor = CausalAssessor()
    weak = assessor.assess(cause="ice cream sales", effect="drownings")
    assert weak.verdict == "correlational_only"
    assert any("confounder" in a for a in weak.alternative_explanations)
    strong = assessor.assess(cause="vaccine", effect="immunity",
                             evidence={"randomized": True, "temporal_order": True,
                                       "mechanism": True, "dose_response": True,
                                       "controlled": True})
    assert strong.verdict == "causal_supported"
    partial = assessor.assess(cause="coffee", effect="productivity",
                              evidence={"temporal_order": True})
    assert partial.verdict == "plausible_unproven"


def test_row41_base_rate_shrinks_weak_evidence():
    integ = BaseRateIntegrator()
    weak = integ.integrate(base_rate=0.1, case_estimate=0.9, evidence_reliability=0.2,
                           sample_size=1)
    strong = integ.integrate(base_rate=0.1, case_estimate=0.9, evidence_reliability=0.9,
                             sample_size=100)
    assert abs(weak.adjusted - 0.1) < abs(strong.adjusted - 0.1)
    assert strong.adjusted > weak.adjusted
    assert weak.base_rate == 0.1 and weak.weight_on_case < strong.weight_on_case


def test_row42_reference_class_forecast_distribution():
    fc = ReferenceClassForecaster(min_similar=3)
    fc.add_case("backend api migration project", 30.0, label="api")
    fc.add_case("backend service migration effort", 45.0, label="service")
    fc.add_case("backend data migration project", 60.0, label="data")
    fc.add_case("frontend redesign", 5.0, label="frontend")
    out = fc.forecast("backend migration project")
    assert out is not None and out.n_cases >= 3
    assert out.p25 <= out.median <= out.p75
    assert out.mean > 20.0  # dominated by migration cases
    assert ReferenceClassForecaster().forecast("anything") is None


def test_row43_outside_view_blends():
    fc = ReferenceClassForecaster(min_similar=1)
    for duration in (10.0, 12.0, 14.0):
        fc.add_case("similar past project", duration)
    view = OutsideView().adopt(inside_estimate=6.0,
                               reference_forecast=fc.forecast("similar project"),
                               outside_weight=0.5, subject="the rewrite")
    assert view.blended == pytest.approx(0.5 * 12.0 + 0.5 * 6.0)
    assert view.outside_median == pytest.approx(12.0)
    no_ref = OutsideView().adopt(inside_estimate=6.0, reference_forecast=None)
    assert no_ref.blended == 6.0 and no_ref.outside_weight == 0.0


def test_row44_planning_fallacy_correction():
    corr = PlanningFallacyCorrector()
    for _ in range(10):
        corr.record(kind="blog post", estimated=2.0, actual=4.0)
    out = corr.correct(kind="blog post", estimate=2.0)
    assert out["multiplier"] == pytest.approx(1.0 + 1.0 * 10 / 15)
    assert out["corrected"] == pytest.approx(2.0 * out["multiplier"])
    fresh = corr.correct(kind="never done", estimate=5.0)
    assert fresh["corrected"] == 5.0 and fresh["samples"] == 0


def test_row45_optimism_calibration_direction():
    cal = OptimismCalibrator(min_samples=3)
    for _ in range(4):
        cal.record(domain="launches", predicted_confidence=0.9, succeeded=False)
    bias, n = cal.bias("launches")
    assert bias == pytest.approx(0.9)  # strongly optimistic
    out = cal.adjust(domain="launches", confidence=0.9)
    assert out["adjusted"] == pytest.approx(0.0) and out["direction"] == "optimistic"
    thin = cal.adjust(domain="new domain", confidence=0.9)
    assert thin["adjusted"] == 0.9  # not enough samples to adjust


def test_row46_scenario_planning_structure():
    out = ScenarioPlanner().plan(objective="launch the beta",
                                 drivers=["signup conversion", "infra stability"])
    names = {s["name"] for s in out["scenarios"]}
    assert names == {"best", "base", "worst", "wildcard"}
    assert sum(s["probability"] for s in out["scenarios"]) == pytest.approx(1.0)
    best = next(s for s in out["scenarios"] if s["name"] == "best")
    assert any("signup conversion" in d for d in best["key_developments"])
    assert best["strategy"] and best["early_indicators"]


def test_row47_premortem_ranks_causes():
    out = PremortemEngine().analyze(
        goal="launch the new api with a vendor partner before the deadline",
        risks=["vendor api instability", "unclear ownership"])
    causes = out["causes"]
    assert causes[0]["score"] >= causes[-1]["score"]
    texts = [c["cause"] for c in causes]
    assert "vendor api instability" in texts
    assert any("dependency failure" in t for t in texts)  # generic matched by vocabulary
    assert all(c["prevention"] for c in causes)
    assert "failure_assumed_at" in out


def test_row48_red_team_finds_spof_and_abuse():
    out = RedTeamer().probe(plan="We have only one person who can deploy; the launch will succeed.",
                            assets=["billing database", "admin panel"])
    vectors = {v["vector"] for v in out["vulnerabilities"]}
    assert "single point of failure" in vectors
    assert "unstated assumptions" in vectors
    assert "abuse case" in vectors
    severities = [v["severity"] for v in out["vulnerabilities"]]
    assert severities == sorted(severities, key={"high": 0, "medium": 1, "low": 2}.get)


def test_row49_second_order_trace_visible_rules():
    tracer = SecondOrderTracer()
    out = tracer.trace(action="cut prices", first_order=["product gets cheaper"], depth=3)
    effects = {e["effect"]: e for e in out["effects"]}
    assert "demand increases" in effects  # order 2 via the cheaper rule
    assert effects["demand increases"]["rule_fired"]  # the producing rule is visible
    assert any(e["order"] == 3 for e in out["effects"])  # chains to third order
    assert out["rules_used"]


def test_row50_systems_loops_classified():
    model = SystemsModel()
    model.add_link("users", "revenue", sign="+")
    model.add_link("revenue", "marketing", sign="+", delay="months")
    model.add_link("marketing", "users", sign="+")
    model.add_link("load", "performance", sign="-")
    model.add_link("performance", "load", sign="+")
    loops = model.loops()
    kinds = {tuple(sorted(loop.variables[:-1])): loop.kind for loop in loops}
    growth = next(loop for loop in loops if "users" in loop.variables)
    assert growth.kind == "reinforcing"
    balancing = next(loop for loop in loops if "load" in loop.variables)
    assert balancing.kind == "balancing"


def test_row51_leverage_ranking_prefers_reinforcing_loops():
    model = SystemsModel()
    model.add_link("users", "revenue", sign="+")
    model.add_link("revenue", "marketing", sign="+")
    model.add_link("marketing", "users", sign="+")
    model.add_link("logo color", "users", sign="+")
    points = LeverageFinder().rank(model)
    assert points[0].variable in {"users", "revenue", "marketing"}
    assert points[0].score > next(p for p in points if p.variable == "logo color").score
    loop_point = next(p for p in points if p.variable == "users")
    assert loop_point.level == "structure" and "reinforcing loop" in loop_point.rationale
    with pytest.raises(ValueError):
        LeverageFinder().rank(SystemsModel())  # no causal links supplied


def test_row52_constraint_analysis_finds_bottleneck():
    out = ConstraintAnalyzer().analyze(stages=[
        {"name": "intake", "capacity": 100, "demand": 60},
        {"name": "review", "capacity": 20, "demand": 60},
        {"name": "ship", "capacity": 80, "demand": 60},
    ])
    assert out["bottleneck"] == "review"
    assert out["system_throughput"] == 20
    review = next(s for s in out["stages"] if s["name"] == "review")
    assert review["is_bottleneck"] and review["utilization"] == pytest.approx(3.0)
    assert any("ELEVATE" in step for step in out["focusing_steps"])
    with pytest.raises(ValueError):
        ConstraintAnalyzer().analyze(stages=[])
    with pytest.raises(ValueError):
        ConstraintAnalyzer().analyze(stages=[{"name": "x", "capacity": 0, "demand": 1}])


def test_row53_antifragility_classification():
    out = AntifragilityAssessor().assess(components=[
        {"name": "single supplier", "stress_response": -0.8},
        {"name": "static faq page", "stress_response": 0.0},
        {"name": "open source community", "stress_response": 0.5},
    ])
    by_name = {c["name"]: c for c in out["components"]}
    assert by_name["single supplier"]["classification"] == "fragile"
    assert by_name["static faq page"]["classification"] == "robust"
    assert by_name["open source community"]["classification"] == "antifragile"
    assert by_name["single supplier"]["redesign"]
    assert out["verdict"] in {"fragile-heavy", "mixed"}
    with pytest.raises(ValueError):
        AntifragilityAssessor().assess(components=[])


def test_row54_optionality_scoring():
    low = OptionalityAnalyzer().assess(
        decision="sign 5-year exclusive lease",
        options_kept=["sublet"], options_closed=["remote-first", "coworking", "move cities"],
        reversible=False)
    assert low["optionality_score"] == pytest.approx(0.25)
    assert any("Stage" in r or "pilot" in r for r in low["recommendations"])
    high = OptionalityAnalyzer().assess(
        decision="month-to-month office", options_kept=["a", "b", "c"],
        options_closed=["d"], reversible=True)
    assert high["optionality_score"] > low["optionality_score"]
    with pytest.raises(ValueError):
        OptionalityAnalyzer().assess(decision="d", options_kept=[], options_closed=[],
                                     reversible=True)


def test_row55_reversibility_doors():
    assessor = ReversibilityAssessor()
    two_way = assessor.assess(decision="change button color", undo_cost=1, undo_days=0.1,
                              blast_radius=1)
    assert two_way["classification"] == "two_way_door"
    assert not two_way["requires_approval_review"]
    one_way = assessor.assess(decision="delete production data", undo_cost=10, undo_days=365,
                              blast_radius=10)
    assert one_way["classification"] == "one_way_door"
    assert one_way["requires_approval_review"]
    mid = assessor.assess(decision="migrate database", undo_cost=5, undo_days=14,
                          blast_radius=5)
    assert mid["classification"] == "costly_reversible"
    with pytest.raises(ValueError):
        assessor.assess(decision="d", undo_cost=11.0, undo_days=1.0, blast_radius=1.0)
    with pytest.raises(ValueError):
        assessor.assess(decision="d", undo_cost=1.0, undo_days=-1.0, blast_radius=1.0)


def test_row56_asymmetry_flags_and_rejects_unbounded():
    out = AsymmetryFinder().evaluate(options=[
        {"name": "oss side project", "downside": 100.0, "upside": 5000.0, "prob_upside": 0.1},
        {"name": "unhedged short", "upside": 500.0, "prob_upside": 0.5},
        {"name": "safe chore", "downside": 100.0, "upside": 150.0, "prob_upside": 0.9},
    ])
    by_name = {o["name"]: o for o in out["options"]}
    assert by_name["oss side project"]["asymmetric"]
    assert by_name["unhedged short"]["flag"].startswith("unbounded downside")
    assert not by_name["safe chore"]["asymmetric"]
    assert out["caveat"] == DECISION_SUPPORT_CAVEAT
    with pytest.raises(ValueError):
        AsymmetryFinder().evaluate(options=[])
    with pytest.raises(ValueError):
        AsymmetryFinder().evaluate(options=[{"name": "x", "upside": 10.0, "prob_upside": 1.5}])


def test_row57_expected_value_ranked_with_sensitivity():
    out = EVCalculator().compute(options=[
        {"name": "a", "outcomes": [[0.5, 100.0], [0.5, 0.0]]},
        {"name": "b", "outcomes": [[0.9, 20.0], [0.1, -10.0]]},
    ])
    assert out["options"][0]["name"] == "a"
    assert out["options"][0]["ev"] == pytest.approx(50.0)
    assert out["options"][1]["ev"] == pytest.approx(17.0)
    assert out["options"][0]["ev_if_best_+10pp"] > out["options"][0]["ev_if_best_-10pp"]
    assert out["caveat"] == DECISION_SUPPORT_CAVEAT
    with pytest.raises(ValueError):
        EVCalculator().compute(options=[])
    with pytest.raises(ValueError):
        EVCalculator().compute(options=[{"name": "x", "outcomes": [[0.9, 1.0], [0.9, 2.0]]}])


def test_row58_risk_of_ruin_verdicts():
    analyzer = RiskOfRuinAnalyzer()
    good = analyzer.analyze(capital=1000.0, bet_size=10.0, win_prob=0.6)
    assert good["method"] == "closed_form"
    assert good["ruin_probability"] == pytest.approx((0.4 / 0.6) ** 100)
    assert good["verdict"] == "acceptable"
    bad = analyzer.analyze(capital=100.0, bet_size=50.0, win_prob=0.4)
    assert bad["ruin_probability"] == 1.0 and bad["verdict"] == "danger"
    mc = analyzer.analyze(capital=100.0, bet_size=10.0, win_prob=0.55, payoff_ratio=2.0)
    assert mc["method"] == "monte_carlo"
    assert 0.0 <= mc["ruin_probability"] <= 1.0
    assert mc["caveat"] == DECISION_SUPPORT_CAVEAT
    with pytest.raises(ValueError):
        analyzer.analyze(capital=100.0, bet_size=500.0, win_prob=0.5)
    with pytest.raises(ValueError):
        analyzer.analyze(capital=100.0, bet_size=10.0, win_prob=1.5)


def test_row59_kelly_sizing():
    sizer = KellySizer(fraction=0.5, cap=0.25)
    out = sizer.size(win_prob=0.6, payoff_ratio=1.0)
    assert out["full_kelly"] == pytest.approx(0.2)
    assert out["recommended"] == pytest.approx(0.1)
    assert out["growth_rate"] > 0
    capped = sizer.size(win_prob=0.9, payoff_ratio=1.0)
    assert capped["recommended"] == 0.25  # half-Kelly of 0.8 exceeds the cap
    no_edge = sizer.size(win_prob=0.4, payoff_ratio=1.0)
    assert no_edge["recommended"] == 0.0 and "No edge" in no_edge["note"]
    assert out["caveat"] == DECISION_SUPPORT_CAVEAT
    with pytest.raises(ValueError):
        sizer.size(win_prob=1.5, payoff_ratio=1.0)
    with pytest.raises(ValueError):
        KellySizer(fraction=0.0, cap=0.25)
