"""Chunk 3 tests: computable reasoning operators."""
import random

import pytest

from app.modules.m20_general_cognitive_worker import reasoning as R


def test_expected_value():
    assert R.expected_value([(0.5, 100.0), (0.5, 0.0)]) == 50.0
    with pytest.raises(ValueError):
        R.expected_value([])


def test_kelly_criterion():
    assert R.kelly_criterion(0.6, 1.0) == pytest.approx(0.2)
    assert R.kelly_criterion(0.4, 1.0) == 0.0  # no edge, no bet
    with pytest.raises(ValueError):
        R.kelly_criterion(1.5, 1.0)


def test_hyperbolic_discounting():
    now_value = R.hyperbolic_discount(100.0, 0.0)
    later_value = R.hyperbolic_discount(100.0, 365.0)
    assert now_value == 100.0
    assert later_value < now_value
    with pytest.raises(ValueError):
        R.hyperbolic_discount(100.0, -1.0)


def test_bayesian_update_base_rates():
    # 1% base rate, 99% sensitive, 95% specific test
    posterior = R.bayesian_update(0.01, 0.99, 0.95)
    assert posterior == pytest.approx(0.166, abs=0.01)  # base rate keeps it low
    negative = R.bayesian_update(0.5, 0.9, 0.9, positive=False)
    assert negative < 0.5
    with pytest.raises(ValueError):
        R.bayesian_update(2.0, 0.9, 0.9)


def test_monte_carlo_distribution_stats():
    result = R.monte_carlo_simulation(lambda rng: rng.gauss(100, 15), trials=2000, seed=42)
    assert result["trials"] == 2000.0
    assert 95 < result["mean"] < 105
    assert result["p5"] < result["median"] < result["p95"]
    assert result["std"] > 10
    with pytest.raises(ValueError):
        R.monte_carlo_simulation(lambda r: 1.0, trials=5)


def test_sensitivity_analysis_ranks_impact():
    def evaluate(params):
        return params["price"] * params["volume"] - params["cost"]

    rows = R.sensitivity_analysis(evaluate, {"price": 10.0, "volume": 100.0, "cost": 200.0}, swing=0.2)
    assert rows[0]["parameter"] == "volume" or rows[0]["parameter"] == "price"
    assert rows[-1]["parameter"] == "cost"
    assert all("impact" in r for r in rows)


def test_decision_tree_rollback():
    tree = R.DecisionNode(kind="decision", children=[
        (1.0, R.DecisionNode(kind="chance", children=[
            (0.5, R.DecisionNode(kind="leaf", value=100.0, label="win")),
            (0.5, R.DecisionNode(kind="leaf", value=0.0, label="lose")),
        ], label="gamble")),
        (1.0, R.DecisionNode(kind="leaf", value=40.0, label="safe")),
    ])
    assert R.evaluate_decision_tree(tree) == 50.0  # gamble EV beats safe 40


def test_littles_law_all_forms():
    assert R.littles_law(wip=12.0, throughput=3.0) == 4.0
    assert R.littles_law(wip=12.0, cycle_time=4.0) == 3.0
    assert R.littles_law(throughput=3.0, cycle_time=4.0) == 12.0
    with pytest.raises(ValueError):
        R.littles_law(wip=1.0)


def test_critical_path():
    tasks = [
        {"id": "a", "duration": 3, "depends_on": []},
        {"id": "b", "duration": 2, "depends_on": ["a"]},
        {"id": "c", "duration": 10, "depends_on": ["a"]},
        {"id": "d", "duration": 1, "depends_on": ["b", "c"]},
    ]
    result = R.critical_path(tasks)
    assert result["duration"] == 14
    assert result["path"] == ["a", "c", "d"]
    with pytest.raises(ValueError):
        R.critical_path([
            {"id": "a", "duration": 1, "depends_on": ["b"]},
            {"id": "b", "duration": 1, "depends_on": ["a"]},
        ])


def test_nash_prisoners_dilemma():
    # cooperate=0, defect=1; defect dominates for both
    row = [[-1, -3], [0, -2]]
    col = [[-1, 0], [-3, -2]]
    assert R.nash_equilibria_2x2(row, col) == [(1, 1)]


def test_zopa():
    assert R.zopa(500.0, 300.0) == (300.0, 500.0)
    assert R.zopa(200.0, 300.0) is None


def test_pareto_frontier():
    points = [
        {"price": 10, "quality": 10},
        {"price": 5, "quality": 5},
        {"price": 9, "quality": 2},
    ]
    frontier = R.pareto_frontier(points, maximize=["price", "quality"])
    assert len(frontier) == 1 and frontier[0]["quality"] == 10


def test_planning_fallacy_and_calibration():
    adjusted = R.planning_fallacy_correction(10.0, [1.5, 2.0, 1.8])
    assert adjusted == pytest.approx(18.0)
    good = R.brier_score([(0.9, True), (0.1, False)])
    bad = R.brier_score([(0.9, False), (0.1, True)])
    assert good < bad


def test_risk_of_ruin():
    assert R.risk_of_ruin_ruin_probability(1000.0, 100.0, 0.6) == 1.0  # losing game
    p = R.risk_of_ruin_ruin_probability(1000.0, 100.0, 0.4)
    assert 0.0 < p < 1.0
    with pytest.raises(ValueError):
        R.risk_of_ruin_ruin_probability(100.0, 200.0, 0.5)


def test_second_order_effects():
    edges = [("raise prices", "fewer customers"), ("fewer customers", "less revenue"),
             ("fewer customers", "less support load"), ("raise prices", "higher margin")]
    chains = R.second_order_effects(edges, "raise prices", depth=2)
    assert ["raise prices", "fewer customers", "less revenue"] in chains
    assert ["raise prices", "higher margin"] in chains


def test_minimax_regret_and_opportunity_cost():
    options = {
        "safe": {"good": 50, "bad": 50},
        "risky": {"good": 200, "bad": 0},
    }
    choice = R.minimax_regret(options)
    assert choice in options  # safe: max regret 150; risky: max regret 50 -> risky wins? check
    # safe regret: good: 200-50=150, bad: 50-50=0 -> 150; risky: good 0, bad 50 -> 50
    assert choice == "risky"
    assert R.opportunity_cost(50.0, [200.0, 75.0]) == 150.0
    assert R.opportunity_cost(50.0, []) == 0.0
