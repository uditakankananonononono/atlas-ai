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
    assert "geometric growth is below1" in out["verdict"]
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


def test_vcg_later_high_value_agent_is_not_excluded_when_items_scarce():
 out=MechanismDesigner().vcg(agents={'a':{'x':1},'b':{'x':10},'c':{'x':8}})
 assert out['allocation']=={'b':'x'} and out['payments']=={'a':0.0,'b':8.0,'c':0.0}
 assert out['total_welfare']==10


def test_vcg_assignment_is_global_not_greedy_above_eight_items():
 agents={'a':{'x':9,'y':8},'b':{'x':10}}
 agents['a'].update({f'z{i}':0 for i in range(7)})
 out=MechanismDesigner().vcg(agents=agents)
 assert out['allocation']=={'a':'y','b':'x'} and out['total_welfare']==18
 assert out['payments']=={'a':0,'b':1}


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1,True,'2'])
def test_vcg_rejects_invalid_reported_valuations(value):
 with pytest.raises(ValueError):MechanismDesigner().vcg(agents={'a':{'x':value}})


def test_vcg_matches_independent_small_exhaustive_assignment_and_externalities():
 import itertools,random
 rng=random.Random(741)
 def optimum(agents,items):
  best=0
  for choices in itertools.product([None]+items,repeat=len(agents)):
   used=[item for item in choices if item is not None]
   if len(used)!=len(set(used)):continue
   best=max(best,sum(values.get(item,0) for values,item in zip(agents.values(),choices)))
  return best
 for agent_count in range(1,5):
  for item_count in range(1,4):
   items=[f'i{x}' for x in range(item_count)]
   for _ in range(8):
    agents={f'a{x}':{item:rng.randrange(12) for item in items} for x in range(agent_count)}
    out=MechanismDesigner().vcg(agents=agents)
    assert out['total_welfare']==optimum(agents,items)
    for agent,payment in out['payments'].items():
     expected=0 if agent not in out['allocation'] else optimum({k:v for k,v in agents.items() if k!=agent},items)-sum(agents[k][item] for k,item in out['allocation'].items() if k!=agent)
     assert payment==expected


def test_vcg_declared_bounds_and_empty_item_reports():
 with pytest.raises(ValueError):MechanismDesigner().vcg(agents={f'a{x}':{'x':1} for x in range(65)})
 with pytest.raises(ValueError):MechanismDesigner().vcg(agents={'a':{f'x{n}':1 for n in range(65)}})
 with pytest.raises(ValueError):MechanismDesigner().vcg(agents={'a':{1:2,'x':3}})
 out=MechanismDesigner().vcg(agents={'a':{},'b':{}})
 assert out['allocation']=={} and out['total_welfare']==0 and out['payments']=={'a':0,'b':0}


def test_geometric_growth_ignores_zero_probability_zero_multiplier():
 out=ErgodicityAnalyzer().analyze(outcomes=[(1,2),(0,0)])
 assert out['ensemble_average']==2 and out['time_average_growth']==2
 assert out['log_growth_rate']==pytest.approx(math.log(2))


def test_positive_probability_zero_multiplier_reports_json_safe_extinction_limit():
 import json
 out=ErgodicityAnalyzer().analyze(outcomes=[(.5,2),(.5,0)])
 assert out['time_average_growth']==0 and out['log_growth_rate'] is None
 assert out['log_growth_status']=='negative_infinity_positive_probability_zero_multiplier'
 json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('outcomes',[[(1,-1)],[(1,float('nan'))],[(1,float('inf'))],[(True,2)],[(1,True)],[(1e-320,1e308)]])
def test_growth_operator_rejects_invalid_or_unstable_inputs(outcomes):
 with pytest.raises(ValueError):ErgodicityAnalyzer().analyze(outcomes=outcomes)


def test_nonlinear_selection_compares_all_candidates_on_original_y_scale():
 model=NonLinearModeler();xs=[1,2,3,4,5];ys=[1,2,3,4,12]
 out=model.classify(xs=xs,ys=ys)
 assert out['selection_metric']=='original_y_r_squared'
 assert out['best_fit']==max(out['all_r_squared'],key=out['all_r_squared'].get)
 assert out['transformed_r_squared']


@pytest.mark.parametrize('xs,ys',[
 ([1,1,1],[2,3,4]),([1,2,float('nan')],[2,3,4]),([1,2,3],[2,3,float('inf')]),([True,2,3],[2,3,4])
])
def test_nonlinear_rejects_degenerate_nonfinite_or_bool_data(xs,ys):
 with pytest.raises(ValueError):NonLinearModeler().classify(xs=xs,ys=ys)


def test_nonlinear_large_finite_exact_line_remains_json_safe():
 import json
 out=NonLinearModeler().classify(xs=[1e150,2e150,3e150,4e150],ys=[2e150,4e150,6e150,8e150])
 assert out['best_fit']=='linear' and out['r_squared']==pytest.approx(1)
 json.dumps(out,allow_nan=False)


def test_nonlinear_report_scores_match_independent_polyfit_original_residuals():
 import numpy as np
 x=np.array([1.,2.,3.,4.,5.]);y=np.array([1.,2.,3.,4.,12.])
 out=NonLinearModeler().classify(xs=x.tolist(),ys=y.tolist())
 sst=sum((y-y.mean())**2)
 for name,fx,fy in [('linear',x,y),('exponential',x,np.log(y)),('logarithmic',np.log(x),y),('power_law',np.log(x),np.log(y))]:
  slope,intercept=np.polyfit(fx,fy,1)
  target=slope*fx+intercept
  prediction=np.exp(target) if name in ('exponential','power_law') else target
  expected=1-sum((y-prediction)**2)/sst
  assert out['all_r_squared'][name]==pytest.approx(expected,abs=1e-12)


def test_critical_path_parallel_equal_branches_are_all_zero_slack_critical():
 out=CriticalPathAnalyzer().analyze(tasks=[{'id':'a','duration':2},{'id':'b','duration':2},{'id':'end','duration':1,'depends_on':['a','b']}])
 assert out['duration']==3
 assert all(row['critical'] and row['slack']==0 for row in out['tasks'])


@pytest.mark.parametrize('tasks',[
 [{'id':'a','duration':1},{'id':'a','duration':2}],
 [{'id':'a','duration':1,'depends_on':['missing']}],
 [{'id':'a','duration':-1}], [{'id':'a','duration':float('inf')}],
])
def test_critical_path_rejects_invalid_task_graph(tasks):
 with pytest.raises(ValueError):CriticalPathAnalyzer().analyze(tasks=tasks)


def test_critical_path_long_chain_avoids_python_recursion_limit():
 tasks=[{'id':str(i),'duration':1,'depends_on':[str(i-1)] if i else []} for i in range(1200)]
 out=CriticalPathAnalyzer().analyze(tasks=tasks)
 assert out['duration']==1200 and len(out['critical_path'])==1200


@pytest.mark.parametrize('spec',[
 {'kind':'chance','children':[{'prob':-1,'node':{'value':2}},{'prob':2,'node':{'value':4}}]},
 {'kind':'decision','children':[]}, {'kind':'unknown'}, {'value':float('nan')}, {'value':True}
])
def test_decision_tree_rejects_invalid_branch_or_leaf(spec):
 with pytest.raises(ValueError):DecisionTreeBuilder().build(spec=spec)


def test_decision_tree_cycle_fails_with_controlled_error():
 spec={'kind':'decision','children':[]};spec['children'].append({'node':spec})
 with pytest.raises(ValueError,match='cyclic'):DecisionTreeBuilder().build(spec=spec)


@pytest.mark.parametrize('expression,params',[
 ('1/x',{'x':0}),('x',{}),('x',{'x':float('nan')}),('x',{'x':True}),('"x"',{'x':1}),('x ** 1001',{'x':2}),('bad +',{'x':1})
])
def test_sensitivity_arithmetic_rejects_unbounded_or_invalid_inputs(expression,params):
 with pytest.raises(ValueError):SensitivityExplorer().analyze(expression=expression,params=params)


def test_erlang_c_large_server_count_is_finite_and_matches_mm1_at_one_server():
 import json
 q=QueueAnalyzer();out=q.mmc(arrival_rate=450,service_rate=1,servers=500)
 assert out['stable'] and 0<out['p_wait']<1 and out['avg_wait_in_queue']>0
 json.dumps(out,allow_nan=False)
 single=q.mmc(arrival_rate=4,service_rate=5,servers=1)
 reference=q.mm1(arrival_rate=4,service_rate=5)
 assert single['p_wait']==pytest.approx(.8) and single['avg_wait_in_queue']==pytest.approx(reference['avg_wait_in_queue'])


@pytest.mark.parametrize('kwargs',[
 {'arrival_rate':float('nan'),'service_rate':1,'servers':2},
 {'arrival_rate':1,'service_rate':float('inf'),'servers':2},
 {'arrival_rate':1,'service_rate':2,'servers':True},
 {'arrival_rate':1,'service_rate':2,'servers':10001},
])
def test_queueing_invalid_rate_or_count_rejects(kwargs):
 with pytest.raises(ValueError):QueueAnalyzer.mmc(**kwargs)


@pytest.mark.parametrize("col", [[[1]], [[float("nan"), 0], [0, 1]], [[True, 0], [0, 1]]])
def test_nash_rejects_invalid_column_matrix(col):
    with pytest.raises(ValueError):
        NashFinder().find(row_payoffs=[[1, 0], [0, 1]], col_payoffs=col)


def test_nash_large_finite_matching_pennies_keeps_mixed():
    out = NashFinder().find(row_payoffs=[[1e308, -1e308], [-1e308, 1e308]], col_payoffs=[[-1e308, 1e308], [1e308, -1e308]])
    assert out["mixed_equilibrium"] == {"row_plays_first_with": 0.5, "col_plays_first_with": 0.5}


def test_nash_one_pure_does_not_claim_stability_or_full_uniqueness():
    out = NashFinder().find(row_payoffs=[[3, 0], [5, 1]], col_payoffs=[[3, 5], [0, 1]])
    assert "stable" not in out["reading"]
    assert "degenerate" in out["scope"]


def test_nash_asymmetric_mixed_independent_indifference_check():
    row = [[4, 0], [1, 2]]
    col = [[0, 3], [2, 1]]
    out = NashFinder().find(row_payoffs=row, col_payoffs=col)
    p = out["mixed_equilibrium"]["row_plays_first_with"]
    q = out["mixed_equilibrium"]["col_plays_first_with"]
    assert p == pytest.approx(0.25)
    assert q == pytest.approx(0.4)
    assert q * row[0][0] + (1-q) * row[0][1] == pytest.approx(q * row[1][0] + (1-q) * row[1][1])
    assert p * col[0][0] + (1-p) * col[1][0] == pytest.approx(p * col[0][1] + (1-p) * col[1][1])
