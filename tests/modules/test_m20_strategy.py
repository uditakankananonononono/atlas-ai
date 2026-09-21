"""Focused tests for rows 60-84: strategic and quantitative decision aids."""
import math

import pytest

from app.modules.m20_general_cognitive_worker.foresight import SystemsModel
from app.modules.m20_general_cognitive_worker.strategy import (
    DECISION_SUPPORT_CAVEAT, AuctionAdvisor, ConstraintsManager,
    CriticalPathAnalyzer, DecisionTreeBuilder, DisruptionAssessor,
    ErgodicityAnalyzer, FlywheelFinder, GameAnalyzer, JTBDFramer,
    LittlesLawAdvisor, MechanismDesigner, MoatAssessor, MonteCarloProjector,
    NashFinder, NetworkEffectAnalyzer, NonLinearModeler, ParetoAnalyzer,
    PrincipalAgentDesigner, QueueAnalyzer, RealOptionsValuer,
    SensitivityExplorer, SignalingAssessor, TippingPointDetector,
    TornadoBuilder, ValueChainMapper,
)


def test_row60_ergodicity_time_vs_ensemble():
    out = ErgodicityAnalyzer().analyze(outcomes=[(0.5, 1.5), (0.5, 0.6)])
    assert out["ensemble_average"] == pytest.approx(1.05)   # looks attractive
    assert out["time_average_growth"] == pytest.approx(math.sqrt(0.9))  # < 1: ruins you
    assert not out["ergodic"]
    assert "ruins you" in out["verdict"]
    flat = ErgodicityAnalyzer().analyze(outcomes=[(0.5, 1.3), (0.5, 0.75)])
    assert flat["ensemble_average"] > 1.0 > flat["time_average_growth"]
    with pytest.raises(ValueError):
        ErgodicityAnalyzer().analyze(outcomes=[])
    with pytest.raises(ValueError):
        ErgodicityAnalyzer().analyze(outcomes=[(1.5, 1.5)])


def test_row61_nonlinear_classification_and_extrapolation():
    modeler = NonLinearModeler()
    xs = [1.0, 2.0, 4.0, 8.0, 16.0]
    ys = [2.0 * x ** 3 for x in xs]
    out = modeler.classify(xs=xs, ys=ys)
    assert out["best_fit"] == "power_law"
    assert out["r_squared"] == pytest.approx(1.0)
    expo = modeler.classify(xs=[1, 2, 3, 4], ys=[math.exp(x) for x in [1, 2, 3, 4]])
    assert expo["best_fit"] == "exponential"
    value = modeler.extrapolate(model="power_law", slope=out["slope"],
                                intercept=out["intercept"], x=32.0)
    assert value == pytest.approx(2.0 * 32.0 ** 3, rel=1e-3)
    with pytest.raises(ValueError):
        modeler.classify(xs=[1.0, 2.0], ys=[1.0, 8.0])
    with pytest.raises(ValueError):
        modeler.classify(xs=[1.0, 2.0, 4.0], ys=[1.0, -8.0, 64.0])
    with pytest.raises(ValueError):
        modeler.extrapolate(model="zigzag", slope=1.0, intercept=0.0, x=2.0)


def test_row62_tipping_point_early_warning():
    detector = TippingPointDetector(window=5)
    calm = [1.0 + 0.01 * i for i in range(10)]
    jittery = [1.0, 1.9, 0.2, 2.2, 0.1, 2.5, 0.05, 3.0, 0.02, 3.5]
    out = detector.analyze(series=calm + jittery, threshold=3.6)
    assert out["warning"]
    assert any("variance rising" in s for s in out["signals"])
    stable = detector.analyze(series=[1.0 + 0.01 * ((-1) ** i) for i in range(20)])
    assert not stable["warning"]
    with pytest.raises(ValueError):
        TippingPointDetector(window=3)
    with pytest.raises(ValueError):
        detector.analyze(series=[1.0, 2.0, 3.0])


def test_row63_network_effect_models():
    analyzer = NetworkEffectAnalyzer()
    assert analyzer.value(n_users=10, model="sarnoff") == 10.0
    assert analyzer.value(n_users=10, model="metcalfe") == 45.0
    assert analyzer.value(n_users=10, model="reed") == 2 ** 10 - 1
    out = analyzer.analyze(n_users=100, two_sided=True)
    assert "two-sided" in out["network_kind"]
    assert out["assumptions"]
    with pytest.raises(ValueError):
        NetworkEffectAnalyzer.value(n_users=-1, model="metcalfe")
    with pytest.raises(ValueError):
        NetworkEffectAnalyzer.value(n_users=10, model="viral")


def test_row64_flywheel_identification():
    model = SystemsModel()
    model.add_link("users", "content", sign="+")
    model.add_link("content", "users", sign="+", delay="weeks")
    model.add_link("servers", "cost", sign="+")
    model.add_link("cost", "servers", sign="-")
    out = FlywheelFinder().find(model)
    assert out["reinforcing_loop_count"] == 1
    wheel = out["flywheels"][0]
    assert wheel["touches_growth"] and "flywheel candidate" in wheel["reading"]
    assert "weeks" in wheel["delays"]
    with pytest.raises(ValueError):
        FlywheelFinder().find(SystemsModel())  # no causal links supplied


def test_row65_moat_assessment():
    out = MoatAssessor().assess(ratings={
        "network_effects": {"strength": 4.0, "durability_years": 5, "evidence": "user graph"},
        "brand": {"strength": 1.0, "durability_years": 1},
    })
    assert out["strongest"] == "network_effects"
    assert out["verdict"] in ("narrow", "wide")
    unclaimed = next(m for m in out["moats"] if m["moat"] == "switching_costs")
    assert unclaimed["score"] is None
    assert out["caveat"] == DECISION_SUPPORT_CAVEAT
    with pytest.raises(ValueError):
        MoatAssessor().assess(ratings={"brand": {"strength": 6.0}})


def test_row66_disruption_assessment():
    out = DisruptionAssessor().assess(
        entrant_improvement_rate=0.5, incumbent_improvement_rate=0.1,
        entrant_targets_underserved=False, entrant_cheaper=True,
        incumbent_overserving=True)
    assert out["disruption_type"] == "low-end"
    assert out["disruption_likely"]
    sustaining = DisruptionAssessor().assess(
        entrant_improvement_rate=0.05, incumbent_improvement_rate=0.1,
        entrant_targets_underserved=False, entrant_cheaper=False)
    assert not sustaining["disruption_likely"]
    assert sustaining["unmet_conditions"]
    with pytest.raises(ValueError):
        DisruptionAssessor().assess(entrant_improvement_rate=-0.1,
                                    incumbent_improvement_rate=0.1,
                                    entrant_targets_underserved=True,
                                    entrant_cheaper=True)


def test_row67_jtbd_framing():
    out = JTBDFramer().frame(product="rideshare", statements=[
        "When I leave work late, I want to get home quickly, so I can feel safe",
        "When it rains, I want to arrive dry, so I can look professional",
        "the price is fair",
    ])
    parsed = [j for j in out["jobs"] if j["parsed"]]
    assert len(parsed) == 2
    assert "emotional" in parsed[0]["dimensions"]
    assert "social" in parsed[1]["dimensions"]
    assert out["jobs"][2]["job_story"] is None
    assert out["core_job"].startswith("When")
    with pytest.raises(ValueError):
        JTBDFramer().frame(product="rideshare", statements=[])


def test_row68_value_chain_mapping():
    out = ValueChainMapper().map(stages=[
        {"name": "farm", "cost": 1.0, "price": 2.0},
        {"name": "roaster", "cost": 2.0, "price": 6.0},
        {"name": "cafe", "cost": 6.0, "price": 10.0},
    ])
    assert out["total_value"] == 9.0
    assert out["capture_concentration"] in {"roaster", "cafe"}
    shares = {s["stage"]: s["share_of_value"] for s in out["stages"]}
    assert sum(shares.values()) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        ValueChainMapper().map(stages=[])
    with pytest.raises(ValueError):
        ValueChainMapper().map(stages=[{"name": "farm", "cost": -1.0, "price": 2.0}])


def test_row69_pareto_vital_few():
    items = {f"task{i}": v for i, v in enumerate([50, 30, 10, 5, 3, 2], start=1)}
    out = ParetoAnalyzer().analyze(items=items)
    assert out["vital_few"] == ["task1", "task2"]
    assert out["share_covered"] == pytest.approx(0.8)
    assert out["pareto_holds"]
    even = ParetoAnalyzer().analyze(items={f"x{i}": 1.0 for i in range(10)})
    assert not even["pareto_holds"]  # needs 8 of 10 items for 80%
    with pytest.raises(ValueError):
        ParetoAnalyzer().analyze(items={})
    with pytest.raises(ValueError):
        ParetoAnalyzer().analyze(items={"a": -1.0})
    with pytest.raises(ValueError):
        ParetoAnalyzer().analyze(items={"a": 1.0}, target_share=0.0)


def test_row70_toc_management_loop():
    toc = ConstraintsManager()
    first = toc.observe(stages=[{"name": "build", "capacity": 50, "demand": 40},
                                {"name": "test", "capacity": 20, "demand": 40}])
    assert first["bottleneck"] == "test"
    assert first["release_pace"] == 20 and first["wip_cap"] == 40
    second = toc.observe(stages=[{"name": "build", "capacity": 50, "demand": 60},
                                 {"name": "test", "capacity": 100, "demand": 40}])
    assert second["bottleneck"] == "build"
    assert second["migrated_from"] == "test"
    with pytest.raises(ValueError):
        toc.observe(stages=[])
    with pytest.raises(ValueError):
        toc.observe(stages=[{"name": "build", "capacity": 0, "demand": 40}])


def test_row71_queueing_metrics():
    q = QueueAnalyzer()
    out = q.mm1(arrival_rate=4.0, service_rate=5.0)
    assert out["stable"] and out["utilization"] == pytest.approx(0.8)
    assert out["avg_in_system"] == pytest.approx(4.0)
    unstable = q.mm1(arrival_rate=6.0, service_rate=5.0)
    assert not unstable["stable"]
    multi = q.mmc(arrival_rate=8.0, service_rate=5.0, servers=2)
    assert multi["stable"] and 0.0 < multi["p_wait"] < 1.0
    with pytest.raises(ValueError):
        q.mm1(arrival_rate=4.0, service_rate=0.0)
    with pytest.raises(ValueError):
        q.mmc(arrival_rate=8.0, service_rate=5.0, servers=0)


def test_row72_littles_law_solve_and_levers():
    out = LittlesLawAdvisor().relate(wip=12.0, throughput=3.0)
    assert out["cycle_time"] == pytest.approx(4.0)
    assert out["levers"] and "halves cycle time" in out["levers"][0]
    other = LittlesLawAdvisor().relate(throughput=3.0, cycle_time=4.0)
    assert other["wip"] == pytest.approx(12.0)
    with pytest.raises(ValueError):
        LittlesLawAdvisor().relate(wip=12.0)  # exactly two of the three are required
    with pytest.raises(ValueError):
        LittlesLawAdvisor().relate(wip=12.0, throughput=3.0, cycle_time=4.0)


def test_row73_critical_path_with_slack():
    out = CriticalPathAnalyzer().analyze(tasks=[
        {"id": "design", "duration": 5, "depends_on": []},
        {"id": "build", "duration": 10, "depends_on": ["design"]},
        {"id": "docs", "duration": 3, "depends_on": ["design"]},
        {"id": "ship", "duration": 2, "depends_on": ["build", "docs"]},
    ])
    assert out["duration"] == 17.0
    assert out["critical_path"] == ["design", "build", "ship"]
    by_task = {t["task"]: t for t in out["tasks"]}
    assert by_task["docs"]["slack"] == pytest.approx(7.0)
    assert by_task["docs"]["critical"] is False
    with pytest.raises(ValueError):
        CriticalPathAnalyzer().analyze(tasks=[])


def test_row74_monte_carlo_project_duration():
    out = MonteCarloProjector().simulate(
        tasks=[{"min": 1.0, "mode": 2.0, "max": 5.0},
               {"min": 2.0, "mode": 3.0, "max": 4.0}],
        trials=2000, seed=1)
    assert 3.0 < out["median"] < 9.0
    assert out["p95"] > out["median"] > out["p5"]
    again = MonteCarloProjector().simulate(
        tasks=[{"min": 1.0, "mode": 2.0, "max": 5.0},
               {"min": 2.0, "mode": 3.0, "max": 4.0}],
        trials=2000, seed=1)
    assert again["median"] == out["median"]  # seeded reproducibility
    with pytest.raises(ValueError):
        MonteCarloProjector().simulate(tasks=[])
    with pytest.raises(ValueError):
        MonteCarloProjector().simulate(tasks=[{"min": 5.0, "mode": 2.0, "max": 9.0}])


def test_row75_sensitivity_ranks_parameters():
    out = SensitivityExplorer().analyze(
        expression="price * volume - fixed",
        params={"price": 10.0, "volume": 100.0, "fixed": 200.0})
    assert out["base_output"] == pytest.approx(800.0)
    assert out["most_influential"] in {"price", "volume"}
    impacts = [r["impact"] for r in out["ranked"]]
    assert impacts == sorted(impacts, reverse=True)
    with pytest.raises(ValueError):
        SensitivityExplorer().analyze(expression="__import__('os')", params={"x": 1.0})


def test_row76_tornado_bars_ordered():
    out = TornadoBuilder().build(
        expression="price * volume - fixed",
        params={"price": 10.0, "volume": 100.0, "fixed": 200.0})
    impacts = [b["impact"] for b in out["bars"]]
    assert impacts == sorted(impacts, reverse=True)
    assert "|" in out["bars"][0]["bar"]
    assert out["base_output"] == pytest.approx(800.0)
    with pytest.raises(ValueError):
        TornadoBuilder().build(expression="x", params={"x": 1.0}, swing=0.0)


def test_row77_decision_tree_rollback():
    spec = {"kind": "decision", "children": [
        {"node": {"kind": "leaf", "value": 10.0, "label": "safe"}},
        {"node": {"kind": "chance", "label": "risky", "children": [
            {"prob": 0.5, "node": {"kind": "leaf", "value": 30.0}},
            {"prob": 0.5, "node": {"kind": "leaf", "value": 0.0}},
        ]}},
    ]}
    out = DecisionTreeBuilder().build(spec=spec)
    assert out["value"] == pytest.approx(15.0)
    assert out["best_first_choice"] == "risky"
    bad = {"kind": "chance", "children": [
        {"prob": 0.3, "node": {"kind": "leaf", "value": 1.0}},
        {"prob": 0.3, "node": {"kind": "leaf", "value": 2.0}}]}
    with pytest.raises(ValueError):
        DecisionTreeBuilder().build(spec=bad)


def test_row78_real_options_binomial():
    valuer = RealOptionsValuer()
    out = valuer.value(underlying=100.0, up=1.5, down=0.6,
                       exercise_cost=120.0, kind="expand", steps=10)
    assert out["option_value"] > 0.0
    assert out["caveat"] == DECISION_SUPPORT_CAVEAT
    abandon = valuer.value(underlying=100.0, up=1.5, down=0.6,
                           exercise_cost=80.0, kind="abandon", steps=10)
    assert abandon["option_value"] > 0.0
    deep_itm_expand = valuer.value(underlying=1000.0, up=1.5, down=0.6,
                                   exercise_cost=10.0, kind="expand", steps=5)
    assert deep_itm_expand["option_value"] == pytest.approx(990.0, rel=1e-6)
    with pytest.raises(ValueError):
        valuer.value(underlying=100.0, up=0.9, down=1.1, exercise_cost=10.0)
    with pytest.raises(ValueError):
        valuer.value(underlying=100.0, up=1.5, down=0.6, exercise_cost=10.0, steps=0)
    with pytest.raises(ValueError):
        valuer.value(underlying=100.0, up=1.5, down=0.6, exercise_cost=10.0, kind="hold")
    with pytest.raises(ValueError):
        valuer.value(underlying=100.0, up=1.01, down=0.99, exercise_cost=10.0,
                     risk_free=3.0)  # arbitrage parameters


def test_row79_game_dominance_and_pareto():
    # Prisoner's dilemma payoffs
    out = GameAnalyzer().analyze(row_payoffs=[[3, 0], [5, 1]],
                                 col_payoffs=[[3, 5], [0, 1]])
    assert out["shape"] == [2, 2]
    assert 0 in out["dominated_rows"] and 0 in out["dominated_cols"]
    assert (0, 0) in [tuple(c) for c in out["pareto_optimal_cells"]]
    assert (1, 1) not in [tuple(c) for c in out["pareto_optimal_cells"]]
    with pytest.raises(ValueError):
        GameAnalyzer().analyze(row_payoffs=[[3, 0], [5]], col_payoffs=[[3, 5], [0, 1]])
    with pytest.raises(ValueError):
        GameAnalyzer().analyze(row_payoffs=[[3, 0], [5, 1]], col_payoffs=[[3, 5]])


def test_row80_nash_pure_and_mixed():
    finder = NashFinder()
    pd = finder.find(row_payoffs=[[3, 0], [5, 1]], col_payoffs=[[3, 5], [0, 1]])
    assert pd["pure_equilibria"] == [{"row": 1, "col": 1}]
    # Matching pennies: no pure, interior mixed at 50/50
    mp = finder.find(row_payoffs=[[1, -1], [-1, 1]], col_payoffs=[[-1, 1], [1, -1]])
    assert mp["pure_equilibria"] == []
    assert mp["mixed_equilibrium"]["row_plays_first_with"] == pytest.approx(0.5)
    assert mp["mixed_equilibrium"]["col_plays_first_with"] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        finder.find(row_payoffs=[[1, 2, 3]], col_payoffs=[[1, 2, 3]])


def test_row81_vcg_allocation_and_incentives():
    designer = MechanismDesigner()
    out = designer.vcg(agents={"a": {"x": 10.0, "y": 6.0},
                               "b": {"x": 8.0, "y": 9.0}})
    assert out["allocation"] == {"a": "x", "b": "y"}
    assert out["total_welfare"] == pytest.approx(19.0)
    # a's payment = b's loss: without a, b takes x (8) instead of y (9) -> 0? no:
    # without a, b takes the best item y=9; with a, b still gets y -> externality 0
    assert out["payments"]["a"] == pytest.approx(0.0)
    contested = designer.vcg(agents={"a": {"x": 10.0}, "b": {"x": 8.0}})
    assert contested["payments"]["a"] == pytest.approx(8.0)  # classic second price
    ic = designer.check_incentives(
        agent="a", true_values={"x": 10.0}, others={"b": {"x": 8.0}},
        deviations=[{"x": 100.0}, {"x": 1.0}, {"x": 8.5}])
    assert ic["incentive_compatible"]
    truthful = ic["outcomes"][0]["utility_at_true_values"]
    assert truthful == pytest.approx(2.0)  # wins x worth 10, pays 8
    with pytest.raises(ValueError):
        designer.vcg(agents={})


def test_row82_auction_guidance():
    advisor = AuctionAdvisor()
    sp = advisor.recommend(auction_type="second_price", value=100.0)
    assert sp["recommended_bid"] == 100.0
    fp = advisor.recommend(auction_type="first_price", value=100.0, n_bidders=5)
    assert fp["recommended_bid"] == pytest.approx(80.0)
    cv = advisor.recommend(auction_type="first_price", value=100.0, common_value=True)
    assert any("winner's curse" in w for w in cv["warnings"])
    assert fp["caveat"] == DECISION_SUPPORT_CAVEAT
    with pytest.raises(ValueError):
        advisor.recommend(auction_type="first_price", value=100.0, n_bidders=1)
    with pytest.raises(ValueError):
        advisor.recommend(auction_type="sealed", value=100.0)


def test_row83_signaling_regimes():
    assessor = SignalingAssessor()
    sep = assessor.assess(benefit=100.0, cost_high_type=40.0, cost_low_type=150.0)
    assert sep["separating"] and "separating" in sep["regime"]
    pool = assessor.assess(benefit=100.0, cost_high_type=40.0, cost_low_type=60.0)
    assert "pooling" in pool["regime"] and not pool["separating"]
    none = assessor.assess(benefit=100.0, cost_high_type=200.0, cost_low_type=300.0)
    assert "no signaling" in none["regime"]
    with pytest.raises(ValueError):
        assessor.assess(benefit=100.0, cost_high_type=-40.0, cost_low_type=150.0)


def test_row84_principal_agent_contract():
    out = PrincipalAgentDesigner().design(
        efforts=[{"level": "low", "cost": 0.0, "expected_output": 100.0},
                 {"level": "high", "cost": 30.0, "expected_output": 200.0}],
        target_effort="high")
    assert out["recommended_share"] is not None
    # at the recommended share the agent must prefer high effort
    rec = next(c for c in out["contracts"] if c["share"] == out["recommended_share"])
    assert rec["agent_chooses"] == "high" and rec["participation_ok"]
    assert out["principal_net"] == pytest.approx(
        (1 - out["recommended_share"]) * 200.0)
    impossible = PrincipalAgentDesigner().design(
        efforts=[{"level": "low", "cost": 0.0, "expected_output": 100.0},
                 {"level": "high", "cost": 200.0, "expected_output": 150.0}],
        target_effort="high")
    assert impossible["recommended_share"] is None
    assert "no tested share" in impossible["reading"]
    with pytest.raises(ValueError):
        PrincipalAgentDesigner().design(efforts=[], target_effort="high")
    with pytest.raises(ValueError):
        PrincipalAgentDesigner().design(
            efforts=[{"level": "low", "cost": 0.0, "expected_output": 100.0}],
            target_effort="high")
    with pytest.raises(ValueError):
        PrincipalAgentDesigner().design(
            efforts=[{"level": "low", "cost": 0.0, "expected_output": 100.0}],
            target_effort="low", shares=[1.5])
