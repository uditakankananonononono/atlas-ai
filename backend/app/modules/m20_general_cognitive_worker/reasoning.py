"""Computable reasoning operators (features doc, Category 1: Executive
Function & Meta-Cognition, and spec 4.2.7 structured reasoning).

Each operator is a pure, tested function the executive can invoke as a
reasoning skill. Judgment-style rows (devil's advocate, steel-manning,
reframing) live in the skill library as prompt-chain skills, not here.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Callable


def expected_value(outcomes: list[tuple[float, float]]) -> float:
    """Expected Value Calculation: sum of probability-weighted outcomes."""
    if not outcomes:
        raise ValueError("outcomes required")
    total_p = sum(p for p, _ in outcomes)
    if total_p <= 0:
        raise ValueError("probabilities must sum to a positive value")
    return sum(p * v for p, v in outcomes) / total_p


def kelly_criterion(prob_win: float, win_odds: float) -> float:
    """Kelly Criterion Bet Sizing: optimal growth fraction f* = p - q/b."""
    if not 0.0 <= prob_win <= 1.0 or win_odds <= 0:
        raise ValueError("need 0<=p<=1 and positive odds")
    fraction = prob_win - (1 - prob_win) / win_odds
    return max(0.0, fraction)


def hyperbolic_discount(value: float, delay_days: float, k: float = 0.02) -> float:
    """Temporal Discounting Optimization: V = A / (1 + kD)."""
    if delay_days < 0 or k < 0:
        raise ValueError("delay and k must be non-negative")
    return value / (1.0 + k * delay_days)


def bayesian_update(prior: float, sensitivity: float, specificity: float, *, positive: bool = True) -> float:
    """Bayesian Belief Updating with base-rate integration."""
    for name, v in (("prior", prior), ("sensitivity", sensitivity), ("specificity", specificity)):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]")
    if positive:
        num = sensitivity * prior
        den = num + (1 - specificity) * (1 - prior)
    else:
        num = (1 - sensitivity) * prior
        den = num + specificity * (1 - prior)
    return num / den if den else 0.0


def monte_carlo_simulation(
    sampler: Callable[[random.Random], float], *, trials: int = 1000, seed: int | None = None,
) -> dict[str, float]:
    """Monte Carlo Simulation over an outcome sampler -> distribution stats."""
    if trials < 10:
        raise ValueError("trials must be >= 10")
    rng = random.Random(seed)
    samples = sorted(sampler(rng) for _ in range(trials))
    n = len(samples)
    return {
        "trials": float(n),
        "mean": mean(samples),
        "median": median(samples),
        "p5": samples[int(0.05 * n)],
        "p95": samples[min(n - 1, int(0.95 * n))],
        "min": samples[0],
        "max": samples[-1],
        "std": math.sqrt(sum((s - mean(samples)) ** 2 for s in samples) / n),
    }


def sensitivity_analysis(
    evaluate: Callable[[dict[str, float]], float],
    base_params: dict[str, float],
    *,
    swing: float = 0.2,
) -> list[dict[str, Any]]:
    """Sensitivity Analysis + Tornado Diagram data: swing each parameter
    +/-swing and rank by impact on the output."""
    base = evaluate(base_params)
    rows = []
    for name, value in base_params.items():
        low_params = {**base_params, name: value * (1 - swing)}
        high_params = {**base_params, name: value * (1 + swing)}
        low, high = evaluate(low_params), evaluate(high_params)
        rows.append({
            "parameter": name, "base": base,
            "low_output": low, "high_output": high,
            "impact": abs(high - low),
        })
    rows.sort(key=lambda r: r["impact"], reverse=True)
    return rows


@dataclass
class DecisionNode:
    """Decision Tree Construction: chance or decision node."""
    kind: str  # "chance" | "decision" | "leaf"
    value: float = 0.0
    children: list[tuple[float, "DecisionNode"]] | None = None  # (prob, child)
    label: str = ""


def evaluate_decision_tree(node: DecisionNode) -> float:
    """Roll back a decision tree: max at decision nodes, EV at chance nodes."""
    if node.kind == "leaf" or not node.children:
        return node.value
    if node.kind == "chance":
        return sum(prob * evaluate_decision_tree(child) for prob, child in node.children)
    if node.kind == "decision":
        return max(evaluate_decision_tree(child) for _, child in node.children)
    raise ValueError(f"unknown node kind {node.kind!r}")


def littles_law(*, wip: float | None = None, throughput: float | None = None,
                cycle_time: float | None = None) -> float:
    """Little's Law Application: L = lambda * W; provide any two."""
    provided = [x is not None for x in (wip, throughput, cycle_time)]
    if sum(provided) != 2:
        raise ValueError("provide exactly two of wip, throughput, cycle_time")
    if wip is None:
        return throughput * cycle_time  # type: ignore[operator]
    if throughput is None:
        return wip / cycle_time  # type: ignore[operator]
    return wip / throughput  # type: ignore[return-value]


def critical_path(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Critical Path Analysis: longest dependency chain by duration.
    tasks: [{id, duration, depends_on: [id]}]."""
    by_id = {t["id"]: t for t in tasks}
    best: dict[str, tuple[float, list[str]]] = {}

    def resolve(task_id: str, seen: frozenset[str]) -> tuple[float, list[str]]:
        if task_id in seen:
            raise ValueError("cyclic dependency")
        if task_id in best:
            return best[task_id]
        task = by_id[task_id]
        duration = float(task["duration"])
        deps = task.get("depends_on", [])
        if not deps:
            best[task_id] = (duration, [task_id])
        else:
            dep_cost, dep_path = max(
                (resolve(d, seen | {task_id}) for d in deps), key=lambda x: x[0],
            )
            best[task_id] = (duration + dep_cost, dep_path + [task_id])
        return best[task_id]

    total, path = max((resolve(t["id"], frozenset()) for t in tasks), key=lambda x: x[0])
    return {"duration": total, "path": path}


def nash_equilibria_2x2(
    row_payoffs: list[list[float]], col_payoffs: list[list[float]],
) -> list[tuple[int, int]]:
    """Nash Equilibrium Identification for 2x2 games (pure strategies)."""
    equilibria = []
    for r in range(2):
        for c in range(2):
            row_best = row_payoffs[r][c] >= row_payoffs[1 - r][c]
            col_best = col_payoffs[r][c] >= col_payoffs[r][1 - c]
            if row_best and col_best:
                equilibria.append((r, c))
    return equilibria


def zopa(buyer_max: float, seller_min: float) -> tuple[float, float] | None:
    """ZOPA Mapping: zone of possible agreement, or None when none exists."""
    if buyer_max < seller_min:
        return None
    return (seller_min, buyer_max)


def pareto_frontier(points: list[dict[str, float]], *, maximize: list[str]) -> list[dict[str, float]]:
    """Pareto frontier over the named dimensions (all maximized)."""
    frontier = []
    for candidate in points:
        dominated = False
        for other in points:
            if other is candidate:
                continue
            if all(other[d] >= candidate[d] for d in maximize) and any(
                other[d] > candidate[d] for d in maximize
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return frontier


def planning_fallacy_correction(estimate_days: float, historical_overruns: list[float]) -> float:
    """Planning Fallacy Correction: scale the estimate by the observed
    median overrun ratio (reference class forecasting)."""
    if estimate_days <= 0:
        raise ValueError("estimate must be positive")
    ratios = [max(0.05, o) for o in historical_overruns if o > 0] or [1.0]
    return estimate_days * median(ratios)


def brier_score(predictions: list[tuple[float, bool]]) -> float:
    """Optimism/Pessimism Calibration: mean squared error of probabilistic
    predictions against outcomes. Lower is better calibrated."""
    if not predictions:
        raise ValueError("predictions required")
    return mean([(p - (1.0 if outcome else 0.0)) ** 2 for p, outcome in predictions])


def risk_of_ruin_ruin_probability(bankroll: float, bet: float, prob_loss: float) -> float:
    """Risk of Ruin Analysis (fixed bet, no edge): classic gambler's ruin
    approximation ((q/p)^(units)) when p != q; 1.0 when q >= p."""
    if bankroll <= 0 or bet <= 0 or bet > bankroll:
        raise ValueError("need 0 < bet <= bankroll")
    if not 0.0 <= prob_loss <= 1.0:
        raise ValueError("prob_loss in [0, 1]")
    q, p = prob_loss, 1.0 - prob_loss
    units = bankroll / bet
    if q >= p:
        return 1.0
    return (q / p) ** units


def second_order_effects(causal_edges: list[tuple[str, str]], start: str, *, depth: int = 3) -> list[list[str]]:
    """Second-Order Effects Tracing: follow consequences of consequences
    through a causal graph up to `depth` hops."""
    adjacency: dict[str, list[str]] = {}
    for src, dst in causal_edges:
        adjacency.setdefault(src, []).append(dst)
    chains: list[list[str]] = []

    def walk(node: str, chain: list[str], remaining: int) -> None:
        if remaining == 0:
            return
        for nxt in adjacency.get(node, []):
            if nxt in chain:
                continue
            chains.append(chain + [nxt])
            walk(nxt, chain + [nxt], remaining - 1)

    walk(start, [start], depth)
    return chains


def minimax_regret(options: dict[str, dict[str, float]]) -> str:
    """Regret Minimization Framework: choose the option whose worst-case
    regret across scenarios is smallest. options: {name: {scenario: payoff}}."""
    if not options:
        raise ValueError("options required")
    scenarios = next(iter(options.values())).keys()
    regrets: dict[str, float] = {}
    for name, payoffs in options.items():
        worst = 0.0
        for scenario in scenarios:
            best_in_scenario = max(o[scenario] for o in options.values())
            worst = max(worst, best_in_scenario - payoffs[scenario])
        regrets[name] = worst
    return min(regrets, key=regrets.get)  # type: ignore[arg-type]


def opportunity_cost(chosen_value: float, alternatives: list[float]) -> float:
    """Opportunity Cost Calculation: best foregone alternative minus chosen."""
    if not alternatives:
        return 0.0
    return max(alternatives) - chosen_value
