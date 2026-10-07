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
    """Supplied sum(p*v); any missing probability mass has value zero."""
    if not isinstance(outcomes, list) or not 1 <= len(outcomes) <= 10000:
        raise ValueError("need1..10000 outcome pairs")
    for item in outcomes:
        if not isinstance(item, (list, tuple)) or len(item) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in item):
            raise ValueError("finite numeric probability/value pairs required")
        if not 0 <= item[0] <= 1:
            raise ValueError("probabilities must be in [0,1]")
    total = math.fsum(p for p, _ in outcomes)
    if not 0 < total <= 1 + 1e-12:
        raise ValueError("probability mass must be positive and at most1")
    scale = max(abs(v) for _, v in outcomes) or 1.0
    result = math.fsum(p * (v / scale) for p, v in outcomes) * scale
    if not math.isfinite(result):
        raise ValueError("expected value exceeds numeric range")
    return result


def kelly_criterion(prob_win: float, win_odds: float) -> float:
    """Kelly Criterion Bet Sizing: optimal growth fraction f* = p - q/b."""
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (prob_win, win_odds)) or not 0.0 <= prob_win <= 1.0 or win_odds <= 0:
        raise ValueError("need finite numeric0<=p<=1 and positive odds")
    fraction = prob_win - (1 - prob_win) / win_odds
    return max(0.0, fraction)


def hyperbolic_discount(value: float, delay_days: float, k: float = 0.02) -> float:
    """Temporal Discounting Optimization: V = A / (1 + kD)."""
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (value, delay_days, k)):
        raise ValueError("finite numeric value/delay/k required, not bool")
    if delay_days < 0 or k < 0:
        raise ValueError("delay and k must be non-negative")
    product = k * delay_days
    if math.isfinite(product):
        return value / (1.0 + product)
    # Overflow implies nonzero k and delay; divide before multiplying.
    return (value / k) / (delay_days + 1.0 / k)


def bayesian_update(prior: float, sensitivity: float, specificity: float, *, positive: bool = True) -> float:
    """Bayesian Belief Updating with base-rate integration."""
    for name, value in (("prior", prior), ("sensitivity", sensitivity), ("specificity", specificity)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be finite numeric in [0,1]")
    if type(positive) is not bool:
        raise ValueError("positive must be bool")
    likelihood_h = sensitivity if positive else 1 - sensitivity
    likelihood_not_h = 1 - specificity if positive else specificity
    log_h = math.log(prior) + math.log(likelihood_h) if prior > 0 and likelihood_h > 0 else -math.inf
    log_not_h = math.log1p(-prior) + math.log(likelihood_not_h) if prior < 1 and likelihood_not_h > 0 else -math.inf
    if log_h == log_not_h == -math.inf:
        raise ValueError("conditioning event has zero probability; posterior undefined")
    if log_h == -math.inf:
        return 0.0
    if log_not_h == -math.inf:
        return 1.0
    difference = log_h - log_not_h
    if difference >= 0:
        return 1 / (1 + math.exp(-difference))
    odds = math.exp(difference)
    return odds / (1 + odds)


def monte_carlo_simulation(
    sampler: Callable[[random.Random], float], *, trials: int = 1000, seed: int | None = None,
) -> dict[str, Any]:
    """Monte Carlo Simulation over an outcome sampler -> distribution stats."""
    if type(trials) is not int or not 10 <= trials <= 100000:
        raise ValueError("trials must be integer10..100000")
    rng = random.Random(seed)
    samples = []
    for _ in range(trials):
        value = sampler(rng)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("sampler must return finite numeric values, not bool")
        samples.append(float(value))
    samples.sort(); n = len(samples)
    scale = max(abs(value) for value in samples) or 1.0
    normalized = [value / scale for value in samples]
    center = math.fsum(normalized) / n
    average = center * scale
    deviation = math.sqrt(math.fsum((value - center) ** 2 for value in normalized) / n) * scale
    if n % 2:
        middle = samples[n // 2]
    else:
        left, right = samples[n // 2 - 1], samples[n // 2]
        middle = left + (right - left) / 2 if (left >= 0) == (right >= 0) else (left + right) / 2
    return {
        "trials": float(n), "mean": average, "median": middle,
        "p5": samples[int(0.05 * n)], "p95": samples[min(n - 1, int(0.95 * n))],
        "min": samples[0], "max": samples[-1], "std": deviation,
        "status": "supplied_sampler_simulation_statistics_only",
        "quantile_method": "sorted_index_floor_percent_times_n",
        "std_method": "scaled_population_standard_deviation",
    }


def sensitivity_analysis(
    evaluate: Callable[[dict[str, float]], float],
    base_params: dict[str, float],
    *,
    swing: float = 0.2,
) -> list[dict[str, Any]]:
    """Sensitivity Analysis + Tornado Diagram data: swing each parameter
    +/-swing and rank by impact on the output."""
    def finite(value):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("finite numeric sensitivity values required, not bool")
        return value
    finite(swing)
    if swing < 0:
        raise ValueError("swing must be nonnegative")
    for value in base_params.values():
        finite(value)
    variations = []
    for name, value in base_params.items():
        low = finite(value * (1 - swing))
        high = finite(value * (1 + swing))
        variations.append((name, {**base_params, name: low}, {**base_params, name: high}))
    base = finite(evaluate(dict(base_params)))
    rows = []
    for name, low_params, high_params in variations:
        low, high = finite(evaluate(low_params)), finite(evaluate(high_params))
        impact = finite(abs(high - low))
        rows.append({"parameter": name, "base": base,
                     "low_output": low, "high_output": high, "impact": impact})
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
    """Finite supplied-tree rollback; depth128/node10000 bounded."""
    count = 0
    def visit(current, active, depth):
        nonlocal count
        count += 1
        if not isinstance(current, DecisionNode) or depth > 128 or count > 10000:
            raise ValueError("invalid node or tree depth/node bound exceeded")
        if id(current) in active:
            raise ValueError("cyclic decision tree")
        if current.kind not in ("leaf", "chance", "decision"):
            raise ValueError("unknown node kind")
        if current.kind == "leaf":
            if current.children or type(current.value) not in (int, float) or not math.isfinite(current.value):
                raise ValueError("finite numeric leaf without children required")
            return float(current.value)
        if not isinstance(current.children, list) or not current.children:
            raise ValueError("branch needs nonempty child list")
        probabilities = []
        for branch in current.children:
            if not isinstance(branch, (tuple, list)) or len(branch) != 2:
                raise ValueError("branch must be probability/node pair")
            prob, child = branch
            if type(prob) not in (int, float) or not math.isfinite(prob) or prob < 0:
                raise ValueError("finite nonnegative branch probability required")
            probabilities.append(prob)
        if current.kind == "chance" and (any(p > 1 for p in probabilities) or not math.isclose(math.fsum(probabilities),1,rel_tol=0,abs_tol=1e-6)):
            raise ValueError("chance probabilities must sum to1")
        values = [visit(child, active | {id(current)}, depth + 1) for _, child in current.children]
        result = math.fsum(p * value for p, value in zip(probabilities, values)) if current.kind == "chance" else max(values)
        if not math.isfinite(result):
            raise ValueError("tree result exceeds numeric range")
        return result
    return visit(node, set(), 0)


def littles_law(*, wip: float | None = None, throughput: float | None = None,
                cycle_time: float | None = None) -> float:
    """Little's Law Application: L = lambda * W; provide any two."""
    provided = [x is not None for x in (wip, throughput, cycle_time)]
    if sum(provided) != 2:
        raise ValueError("provide exactly two of wip, throughput, cycle_time")
    for value in (wip, throughput, cycle_time):
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError("finite nonnegative numeric queue values required, not bool")
    if wip is None:
        result = throughput * cycle_time
    elif throughput is None:
        if cycle_time == 0:
            raise ValueError("zero cycle time cannot determine throughput")
        result = wip / cycle_time
    else:
        if throughput == 0:
            raise ValueError("zero throughput cannot determine cycle time")
        result = wip / throughput
    if not math.isfinite(result):
        raise ValueError("Little's-law result exceeds numeric range")
    return result


def critical_path(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Bounded supplied DAG point-duration CPM; no resource constraints."""
    from collections import deque
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 10000:
        raise ValueError("need1..10000 tasks")
    by_id = {}; successors = {}; degrees = {}
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str) or not task["id"]:
            raise ValueError("nonempty string task id required")
        name = task["id"]
        if name in by_id:
            raise ValueError("duplicate task id")
        value = task.get("duration")
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("finite nonnegative duration required")
        deps = task.get("depends_on", [])
        if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps) or len(set(deps)) != len(deps):
            raise ValueError("unique dependency id list required")
        by_id[name] = {"duration": float(value), "depends_on": list(deps)}
        successors[name] = []; degrees[name] = len(deps)
    for name, task in by_id.items():
        for dep in task["depends_on"]:
            if dep not in by_id:
                raise ValueError("unknown task dependency")
            successors[dep].append(name)
    queue = deque(name for name in by_id if degrees[name] == 0)
    order = []; finishes = {}; predecessors = {}
    while queue:
        name = queue.popleft(); order.append(name)
        deps = by_id[name]["depends_on"]
        predecessor = max(deps, key=finishes.get) if deps else None
        finish = (finishes[predecessor] if predecessor is not None else 0) + by_id[name]["duration"]
        if not math.isfinite(finish):
            raise ValueError("path duration exceeds numeric range")
        finishes[name] = finish; predecessors[name] = predecessor
        for child in successors[name]:
            degrees[child] -= 1
            if degrees[child] == 0:queue.append(child)
    if len(order) != len(by_id):
        raise ValueError("cyclic dependency")
    end = max(order, key=finishes.get); total = finishes[end]
    path = []; current = end
    while current is not None:
        path.append(current); current = predecessors[current]
    path.reverse()
    forward = {}
    for name in reversed(order):
        forward[name] = max((by_id[child]["duration"] + forward[child] for child in successors[name]), default=0.0)
    rows = []
    for name, task in by_id.items():
        slack = max(0.0, total - finishes[name] - forward[name])
        critical = math.isclose(slack, 0.0, rel_tol=0, abs_tol=1e-12 * max(1.0, total))
        rows.append({"task": name, "duration": task["duration"], "slack": slack, "critical": critical})
    return {"duration": total, "path": path, "tasks": rows,
            "status": "supplied_dag_point_duration_cpm_only"}


def validate_game_2x2(row_payoffs, col_payoffs) -> None:
    for matrix in (row_payoffs, col_payoffs):
        if not isinstance(matrix, list) or len(matrix) != 2 or any(not isinstance(row, list) or len(row) != 2 for row in matrix):
            raise ValueError("two 2x2 payoff matrices required")
        if any(type(value) not in (int, float) or not math.isfinite(value) for row in matrix for value in row):
            raise ValueError("finite numeric payoffs required, not bool")


def nash_equilibria_2x2(
    row_payoffs: list[list[float]], col_payoffs: list[list[float]],
) -> list[tuple[int, int]]:
    """Nash Equilibrium Identification for 2x2 games (pure strategies)."""
    validate_game_2x2(row_payoffs, col_payoffs)
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
    """Supplied median-ratio heuristic with0.05floor; empty history uses1.

    Does not verify durations, reference-class relevance or forecast validity.
    """
    if type(estimate_days) not in (int, float) or not math.isfinite(estimate_days) or estimate_days <= 0:
        raise ValueError("estimate must be positive finite numeric, not bool")
    if not isinstance(historical_overruns, list) or any(type(ratio) not in (int, float) or not math.isfinite(ratio) or ratio <= 0 for ratio in historical_overruns):
        raise ValueError("historical ratios must be positive finite numeric, not bool")
    ratios = sorted(max(0.05, ratio) for ratio in historical_overruns) or [1.0]
    n = len(ratios)
    factor = ratios[n // 2] if n % 2 else ratios[n // 2 - 1] + (ratios[n // 2] - ratios[n // 2 - 1]) / 2
    corrected = estimate_days * factor
    if not math.isfinite(corrected):
        raise ValueError("corrected estimate exceeds numeric range")
    return corrected


def brier_score(predictions: list[tuple[float, bool]]) -> float:
    """Mean squared probability error against supplied exact-bool labels.

    A lower proper score does not independently establish calibration or label truth.
    """
    if not isinstance(predictions, list) or not predictions:
        raise ValueError("prediction pairs required")
    errors = []
    for pair in predictions:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("probability/outcome pairs required")
        probability, outcome = pair
        if type(probability) not in (int, float) or not math.isfinite(probability) or not 0 <= probability <= 1 or type(outcome) is not bool:
            raise ValueError("finite numeric probability in [0,1] and exact bool outcome required")
        errors.append((probability - float(outcome)) ** 2)
    return math.fsum(errors) / len(errors)


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
    if not isinstance(options, dict) or not options:
        raise ValueError("options required")
    tables = list(options.values())
    if any(not isinstance(table, dict) or not table for table in tables):
        raise ValueError("nonempty scenario payoff tables required")
    scenarios = list(tables[0])
    if any(set(table) != set(scenarios) for table in tables):
        raise ValueError("all payoff tables must use identical scenarios")
    if any(type(value) not in (int, float) or not math.isfinite(value) for table in tables for value in table.values()):
        raise ValueError("finite numeric payoffs required, not bool")
    scale = max(abs(value) for table in tables for value in table.values()) or 1.0
    normalized = {name: {scenario: value / scale for scenario, value in table.items()} for name, table in options.items()}
    best = {scenario: max(table[scenario] for table in normalized.values()) for scenario in scenarios}
    regrets = {name: max(best[scenario] - table[scenario] for scenario in scenarios)
               for name, table in normalized.items()}
    return min(regrets, key=regrets.get)


def opportunity_cost(chosen_value: float, alternatives: list[float]) -> float:
    """Opportunity Cost Calculation: best foregone alternative minus chosen."""
    if not alternatives:
        return 0.0
    return max(alternatives) - chosen_value
