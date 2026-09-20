"""Strategic and quantitative decision aids (features-doc rows 60-84).

Each row is an exact, typed capability: deterministic, offline, and
assumption-visible - every result carries the assumptions behind it.
Nothing here claims business certainty, and valuation-shaped rows return
an explicit decision-support caveat rather than advice.
"""
from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from .embeddings import tokenize
from .foresight import SystemsModel
from .reasoning import (
    DecisionNode, critical_path, evaluate_decision_tree, littles_law,
    monte_carlo_simulation, nash_equilibria_2x2, sensitivity_analysis,
)

DECISION_SUPPORT_CAVEAT = (
    "Decision-support arithmetic over the inputs you supplied, "
    "not business, financial or investment advice."
)


# ---------------------------------------------------------------- row 60 --
# Ergodicity Awareness: time averages vs ensemble averages.

class ErgodicityAnalyzer:
    """Compares the ensemble average (probability-weighted mean of one
    round's multipliers) with the time average (per-round geometric growth
    of repeating the bet forever). When they disagree, the ensemble view
    is misleading for anyone living through the sequence."""

    def analyze(self, *, outcomes: list[tuple[float, float]]) -> dict[str, Any]:
        if not outcomes:
            raise ValueError("outcomes required")
        total_p = sum(p for p, _ in outcomes)
        if not 0.0 < total_p <= 1.0 + 1e-9 or any(p < 0 for p, _ in outcomes):
            raise ValueError("invalid probabilities")
        ensemble = sum(p * m for p, m in outcomes) / total_p
        if any(m <= 0 for _, m in outcomes):
            time_avg = 0.0
            log_growth = -math.inf
        else:
            log_growth = sum(p * math.log(m) for p, m in outcomes) / total_p
            time_avg = math.exp(log_growth)
        ergodic = abs(ensemble - time_avg) < 1e-9
        verdict = ("ergodic: ensemble and time averages agree"
                   if ergodic else
                   "non-ergodic: positive ensemble average but NEGATIVE time-average growth - "
                   "repeating this bet ruins you even though the mean looks attractive"
                   if ensemble > 1.0 > time_avg else
                   "non-ergodic: time average beats the ensemble average"
                   if time_avg > ensemble else
                   "non-ergodic: ensemble average beats the time average")
        return {"ensemble_average": ensemble, "time_average_growth": time_avg,
                "log_growth_rate": log_growth, "ergodic": ergodic, "verdict": verdict,
                "assumptions": ["Multipliers apply to the whole stake each round",
                                 "Rounds are independent with stable probabilities"]}


# ---------------------------------------------------------------- row 61 --
# Non-Linear Thinking: classify exponential / logarithmic / power-law /
# linear relationships from samples, then extrapolate with the fitted form.

class NonLinearModeler:
    """Fits four candidate forms by least squares on transformed axes and
    keeps the best R^2. Extrapolation reports the model used - no silent
    linear projection."""

    def classify(self, *, xs: list[float], ys: list[float]) -> dict[str, Any]:
        if len(xs) != len(ys) or len(xs) < 3:
            raise ValueError("need >= 3 paired samples")
        if any(x <= 0 or y <= 0 for x, y in zip(xs, ys)):
            raise ValueError("samples must be positive (log transforms)")
        lnx, lny = [math.log(x) for x in xs], [math.log(y) for y in ys]

        def r2(fx: list[float], fy: list[float]) -> tuple[float, float, float]:
            mx, my = mean(fx), mean(fy)
            sxx = sum((x - mx) ** 2 for x in fx)
            sxy = sum((x - mx) * (y - my) for x, y in zip(fx, fy))
            syy = sum((y - my) ** 2 for y in fy)
            slope = sxy / sxx if sxx else 0.0
            intercept = my - slope * mx
            return (sxy * sxy / (sxx * syy) if sxx and syy else 0.0), slope, intercept

        candidates = {
            "linear": r2(xs, ys),
            "exponential": r2(xs, lny),
            "logarithmic": r2(lnx, ys),
            "power_law": r2(lnx, lny),
        }
        best = max(candidates, key=lambda k: candidates[k][0])
        r2v, slope, intercept = candidates[best]
        return {"best_fit": best, "r_squared": r2v, "slope": slope, "intercept": intercept,
                "all_r_squared": {k: v[0] for k, v in candidates.items()},
                "assumptions": ["Positive samples only; ties broken by dict order",
                                 "Classification is over 4 candidate forms, not all of math"]}

    def extrapolate(self, *, model: str, slope: float, intercept: float, x: float) -> float:
        if x <= 0:
            raise ValueError("x must be positive")
        if model == "linear":
            return slope * x + intercept
        if model == "exponential":
            return math.exp(intercept + slope * x)
        if model == "logarithmic":
            return slope * math.log(x) + intercept
        if model == "power_law":
            return math.exp(intercept) * x ** slope
        raise ValueError(f"unknown model {model!r}")


# ---------------------------------------------------------------- row 62 --
# Tipping Point Detection: early-warning signals of phase transitions.

class TippingPointDetector:
    """Critical-slowing-down signals over a rolling window: rising variance
    and rising lag-1 autocorrelation precede many phase transitions. Also
    reports distance to a caller-supplied threshold."""

    def __init__(self, *, window: int = 10) -> None:
        if window < 4:
            raise ValueError("window must be >= 4")
        self.window = window

    @staticmethod
    def _var(xs: list[float]) -> float:
        m = mean(xs)
        return sum((x - m) ** 2 for x in xs) / len(xs)

    @staticmethod
    def _lag1(xs: list[float]) -> float:
        m = mean(xs)
        num = sum((xs[i] - m) * (xs[i - 1] - m) for i in range(1, len(xs)))
        den = sum((x - m) ** 2 for x in xs)
        return num / den if den else 0.0

    def analyze(self, *, series: list[float], threshold: float | None = None) -> dict[str, Any]:
        if len(series) < self.window * 2:
            raise ValueError(f"need >= {self.window * 2} points")
        first, last = series[: self.window], series[-self.window:]
        var_early, var_late = self._var(first), self._var(last)
        ac_early, ac_late = self._lag1(first), self._lag1(last)
        signals = []
        if var_late > var_early * 1.5:
            signals.append(f"variance rising ({var_early:.4g} -> {var_late:.4g})")
        if ac_late > ac_early + 0.1:
            signals.append(f"lag-1 autocorrelation rising ({ac_early:.2f} -> {ac_late:.2f}) - "
                           "the system is recovering from shocks more slowly")
        distance = None
        if threshold is not None:
            distance = threshold - series[-1]
            if distance <= 0:
                signals.append("threshold already crossed")
            elif distance < 0.1 * abs(threshold or 1.0):
                signals.append(f"within 10% of threshold {threshold:g}")
        warning = len(signals) >= 2 or (threshold is not None and distance is not None and distance <= 0)
        return {"warning": warning, "signals": signals,
                "variance_early": var_early, "variance_late": var_late,
                "autocorr_early": ac_early, "autocorr_late": ac_late,
                "distance_to_threshold": distance,
                "assumptions": [f"Rolling window of {self.window} points",
                                 "Early-warning signals indicate rising fragility, not a certain flip"]}


# ---------------------------------------------------------------- row 63 --
# Network Effect Analysis.

class NetworkEffectAnalyzer:
    """Value scaling under the three classic network laws and a typed
    classification of the network structure. The laws are heuristics with
    known limits, returned alongside the numbers."""

    @staticmethod
    def value(*, n_users: int, model: str = "metcalfe") -> float:
        if n_users < 0:
            raise ValueError("n_users must be >= 0")
        if model == "sarnoff":
            return float(n_users)
        if model == "metcalfe":
            return float(n_users * (n_users - 1)) / 2.0
        if model == "reed":
            return float(2 ** min(n_users, 30) - 1)  # capped: Reed grows absurdly fast
        raise ValueError("model must be sarnoff | metcalfe | reed")

    def analyze(self, *, n_users: int, two_sided: bool = False,
                same_side: bool = True) -> dict[str, Any]:
        values = {m: self.value(n_users=n_users, model=m)
                  for m in ("sarnoff", "metcalfe", "reed")}
        kind = ("two-sided marketplace (cross-side effects dominate)"
                if two_sided else
                "direct same-side network" if same_side else "indirect/platform network")
        strength = ("strong: each user adds value for every other user"
                    if same_side and not two_sided else
                    "moderate: growth on one side attracts the other side"
                    if two_sided else "indirect: value arrives via complements")
        return {"n_users": n_users, "network_kind": kind, "strength": strength,
                "value_estimates": values,
                "assumptions": ["Sarnoff=n, Metcalfe=n(n-1)/2, Reed=2^n-1 (capped at n=30)",
                                 "These laws bound potential, not realized engagement",
                                 DECISION_SUPPORT_CAVEAT]}


# ---------------------------------------------------------------- row 64 --
# Flywheel Identification: self-reinforcing growth loops, found with the
# row-50 systems model.

class FlywheelFinder:
    """Reinforcing loops that pass through a growth variable are flywheel
    candidates; longer loops spin slower."""

    GROWTH_WORDS = ("user", "growth", "revenue", "customer", "adoption", "traffic")

    def find(self, model: SystemsModel) -> dict[str, Any]:
        loops = model.loops()
        reinforcing = [loop for loop in loops if loop.kind == "reinforcing"]
        candidates = []
        for loop in reinforcing:
            touches_growth = any(any(w in v.lower() for w in self.GROWTH_WORDS)
                                 for v in loop.variables)
            candidates.append({
                "variables": loop.variables, "length": len(loop.variables) - 1,
                "touches_growth": touches_growth, "delays": loop.delay_notes,
                "reading": ("flywheel candidate: self-reinforcing loop through a growth variable"
                            if touches_growth else
                            "reinforcing loop without an obvious growth variable"),
            })
        candidates.sort(key=lambda c: (not c["touches_growth"], c["length"]))
        return {"flywheels": candidates, "reinforcing_loop_count": len(reinforcing),
                "assumptions": ["Loop polarity from the supplied link signs",
                                 "Shorter loops compound faster than longer ones, all else equal"]}


# ---------------------------------------------------------------- row 65 --
# Moat Analysis.

class MoatAssessor:
    """Scores six classic moat types from caller-supplied evidence ratings
    (0-5) and durability years; the moat is only as strong as its weakest
    claimed pillar with evidence."""

    MOAT_TYPES = ("network_effects", "switching_costs", "brand", "cost_advantage",
                  "scale_economies", "intangibles")

    def assess(self, *, ratings: dict[str, dict[str, Any]]) -> dict[str, Any]:
        rows = []
        for moat in self.MOAT_TYPES:
            entry = ratings.get(moat)
            if not entry:
                rows.append({"moat": moat, "score": None, "note": "not claimed"})
                continue
            strength = float(entry["strength"])
            if not 0.0 <= strength <= 5.0:
                raise ValueError("strength must be in [0, 5]")
            durability = float(entry.get("durability_years", 1.0))
            evidence = entry.get("evidence", "")
            score = strength * math.log1p(durability)
            rows.append({"moat": moat, "score": score, "strength": strength,
                         "durability_years": durability, "evidence": evidence})
        claimed = [r for r in rows if r["score"] is not None]
        verdict = ("no moat claimed" if not claimed else
                   "wide" if max(r["score"] for r in claimed) >= 8 else
                   "narrow" if max(r["score"] for r in claimed) >= 3 else "none")
        return {"moats": rows, "verdict": verdict,
                "strongest": max(claimed, key=lambda r: r["score"])["moat"] if claimed else None,
                "caveat": DECISION_SUPPORT_CAVEAT,
                "assumptions": ["Ratings and durability are caller judgments",
                                 "score = strength x log(1 + durability_years)"]}


# ---------------------------------------------------------------- row 66 --
# Disruption Theory Application.

class DisruptionAssessor:
    """Christensen-style check: entrants win from below when they start in
    segments the incumbent ignores and improve faster than the incumbent's
    trajectory."""

    def assess(self, *, entrant_improvement_rate: float, incumbent_improvement_rate: float,
               entrant_targets_underserved: bool, entrant_cheaper: bool,
               incumbent_overserving: bool = False) -> dict[str, Any]:
        if entrant_improvement_rate < 0 or incumbent_improvement_rate < 0:
            raise ValueError("improvement rates must be >= 0")
        if entrant_targets_underserved and not entrant_cheaper:
            kind = "new-market"
        elif entrant_cheaper:
            kind = "low-end"
        else:
            kind = "sustaining"
        closing = entrant_improvement_rate > incumbent_improvement_rate
        likely = (kind in ("low-end", "new-market") and closing
                  and (incumbent_overserving or entrant_targets_underserved))
        conditions = []
        if not closing:
            conditions.append("entrant must improve faster than the incumbent")
        if kind == "sustaining":
            conditions.append("entrant must enter a segment the incumbent is motivated to flee")
        if not incumbent_overserving and not entrant_targets_underserved:
            conditions.append("disruption needs an overserved or ignored foothold")
        return {"disruption_type": kind, "performance_gap_closing": closing,
                "disruption_likely": likely, "unmet_conditions": conditions,
                "caveat": DECISION_SUPPORT_CAVEAT,
                "assumptions": ["Improvement rates are caller estimates",
                                 "Incumbents rationally flee low-margin footholds"]}


# ---------------------------------------------------------------- row 67 --
# Jobs-to-be-Done Framing.

class JTBDFramer:
    """Turns customer statements into job stories and classifies each job's
    functional, emotional and social dimensions from explicit markers."""

    EMOTIONAL = ("feel", "afraid", "anxious", "confident", "proud", "embarrass", "stress")
    SOCIAL = ("look", "appear", "status", "impress", "perceived", "reputation")

    def frame(self, *, product: str, statements: list[str]) -> dict[str, Any]:
        if not statements:
            raise ValueError("at least one statement is required")
        jobs = []
        for s in statements:
            when = re.search(r"when (.+?)(?:,|$)", s, re.IGNORECASE)
            want = re.search(r"i want to (.+?)(?:,| so i can|$)", s, re.IGNORECASE)
            outcome = re.search(r"so i can (.+?)$", s, re.IGNORECASE)
            tokens = set(tokenize(s))
            dimensions = ["functional"]
            if tokens & set(self.EMOTIONAL):
                dimensions.append("emotional")
            if tokens & set(self.SOCIAL):
                dimensions.append("social")
            jobs.append({
                "statement": s,
                "job_story": (f"When {when.group(1)}, I want to {want.group(1)}, "
                              f"so I can {outcome.group(1)}"
                              if when and want and outcome else None),
                "dimensions": dimensions,
                "parsed": bool(when and want and outcome),
            })
        parsed = [j for j in jobs if j["parsed"]]
        return {"product": product, "jobs": jobs,
                "core_job": parsed[0]["job_story"] if parsed else None,
                "assumptions": ["Job stories extracted from 'when ... I want to ... so I can ...' phrasing",
                                 "Unparsed statements are kept raw for manual framing",
                                 "Dimensions detected from explicit emotional/social markers"]}


# ---------------------------------------------------------------- row 68 --
# Value Chain Mapping.

class ValueChainMapper:
    """Traces where value is created (price a stage can command minus its
    cost) versus captured (margin share) across chain stages."""

    def map(self, *, stages: list[dict[str, Any]]) -> dict[str, Any]:
        if not stages:
            raise ValueError("at least one stage is required")
        rows = []
        for s in stages:
            cost, price = float(s["cost"]), float(s["price"])
            if cost < 0 or price < 0:
                raise ValueError("cost and price must be >= 0")
            rows.append({"stage": s["name"], "cost": cost, "price": price,
                         "value_created": price - cost})
        total = sum(r["value_created"] for r in rows)
        for r in rows:
            r["share_of_value"] = (r["value_created"] / total) if total > 0 else 0.0
        top = max(rows, key=lambda r: r["share_of_value"])
        return {"stages": rows, "total_value": total,
                "capture_concentration": top["stage"],
                "reading": (f"'{top['stage']}' captures {top['share_of_value']:.0%} of chain value"
                            if total > 0 else "no positive value created in this chain"),
                "caveat": DECISION_SUPPORT_CAVEAT,
                "assumptions": ["Stage price = what the next stage pays; final price = end price",
                                 "Value created = price - cost per stage"]}


# ---------------------------------------------------------------- row 69 --
# Pareto Principle Application.

class ParetoAnalyzer:
    """Finds the smallest set of items covering a target share of total
    value (default 80%), and reports the actual concentration."""

    def analyze(self, *, items: dict[str, float], target_share: float = 0.8) -> dict[str, Any]:
        if not items or any(v < 0 for v in items.values()):
            raise ValueError("items must map names to non-negative values")
        if not 0.0 < target_share <= 1.0:
            raise ValueError("target_share must be in (0, 1]")
        total = sum(items.values())
        if total <= 0:
            raise ValueError("total value must be positive")
        ranked = sorted(items.items(), key=lambda kv: kv[1], reverse=True)
        picked, acc = [], 0.0
        for name, value in ranked:
            picked.append(name)
            acc += value
            if acc / total >= target_share:
                break
        concentration = len(picked) / len(items)
        return {"vital_few": picked, "share_covered": acc / total,
                "fraction_of_items": concentration,
                "pareto_holds": abs(concentration - 0.2) <= 0.15,
                "reading": (f"{len(picked)} of {len(items)} items ({concentration:.0%}) "
                            f"deliver {acc / total:.0%} of value"),
                "assumptions": [f"Target share {target_share:.0%}",
                                 "All item values treated as additive and comparable"]}


# ---------------------------------------------------------------- row 70 --
# Theory of Constraints (management loop): distinct from row 52's one-shot
# analysis - this tracks the constraint over time and paces releases to it.

class ConstraintsManager:
    """Drum-buffer-rope style management: the bottleneck sets the release
    pace (drum), a time buffer protects it, and WIP is capped so queues
    stay visible. Bottleneck migration between snapshots is reported."""

    def __init__(self) -> None:
        self.snapshots: list[dict[str, Any]] = []

    def observe(self, *, stages: list[dict[str, Any]]) -> dict[str, Any]:
        if not stages:
            raise ValueError("at least one stage is required")
        utilization = {s["name"]: float(s.get("demand", 0.0)) / float(s["capacity"])
                       for s in stages if float(s["capacity"]) > 0}
        if not utilization:
            raise ValueError("capacities must be > 0")
        bottleneck = max(utilization, key=utilization.get)
        previous = self.snapshots[-1]["bottleneck"] if self.snapshots else None
        self.snapshots.append({"bottleneck": bottleneck, "utilization": utilization})
        capacity = next(float(s["capacity"]) for s in stages if s["name"] == bottleneck)
        return {
            "bottleneck": bottleneck,
            "utilization": utilization,
            "migrated_from": previous if previous != bottleneck else None,
            "release_pace": capacity,
            "wip_cap": 2.0 * capacity,
            "policy": [f"Release new work at {capacity:g} units/period - the bottleneck's rate",
                       f"Cap WIP near {2.0 * capacity:g} units so queues stay visible",
                       "Expedite nothing past the bottleneck: downstream idle time is free",
                       "Watch for migration after any capacity change"],
            "assumptions": ["Utilization = demand / capacity; > 1 means queueing",
                             "WIP cap heuristic: ~2x bottleneck rate"],
        }


# ---------------------------------------------------------------- row 71 --
# Queueing Theory: M/M/1 and M/M/c flow metrics.

class QueueAnalyzer:
    """Steady-state queue metrics. Unstable systems (arrival rate >= total
    service rate) are flagged, never smoothed over."""

    @staticmethod
    def mm1(*, arrival_rate: float, service_rate: float) -> dict[str, Any]:
        if arrival_rate < 0 or service_rate <= 0:
            raise ValueError("need arrival_rate >= 0 and service_rate > 0")
        rho = arrival_rate / service_rate
        if rho >= 1.0:
            return {"stable": False, "utilization": rho,
                    "reading": "unstable: arrivals outpace service; the queue grows without bound",
                    "assumptions": ["M/M/1: Poisson arrivals, exponential service"]}
        return {"stable": True, "utilization": rho,
                "avg_in_system": rho / (1 - rho),
                "avg_in_queue": rho * rho / (1 - rho),
                "avg_wait_in_system": 1.0 / (service_rate - arrival_rate),
                "avg_wait_in_queue": arrival_rate / (service_rate * (service_rate - arrival_rate)),
                "reading": f"at {rho:.0%} utilization the wait is dominated by the 1/(1-rho) blowup",
                "assumptions": ["M/M/1: Poisson arrivals, exponential service, one server"]}

    @staticmethod
    def mmc(*, arrival_rate: float, service_rate: float, servers: int) -> dict[str, Any]:
        if servers < 1 or arrival_rate < 0 or service_rate <= 0:
            raise ValueError("invalid rates or server count")
        rho = arrival_rate / (servers * service_rate)
        if rho >= 1.0:
            return {"stable": False, "utilization": rho,
                    "reading": f"unstable: need more than {arrival_rate / service_rate:.2f} servers",
                    "assumptions": ["M/M/c: Poisson arrivals, exponential service"]}
        a = arrival_rate / service_rate
        sum_terms = sum(a ** n / math.factorial(n) for n in range(servers))
        erlang_c = (a ** servers / (math.factorial(servers) * (1 - rho))) / \
                   (sum_terms + a ** servers / (math.factorial(servers) * (1 - rho)))
        wq = erlang_c / (servers * service_rate - arrival_rate)
        return {"stable": True, "utilization": rho, "p_wait": erlang_c,
                "avg_wait_in_queue": wq,
                "avg_wait_in_system": wq + 1.0 / service_rate,
                "reading": f"P(an arrival waits) = {erlang_c:.0%} (Erlang C)",
                "assumptions": ["M/M/c: Poisson arrivals, exponential service, c identical servers"]}


# ---------------------------------------------------------------- row 72 --
# Little's Law Application.

class LittlesLawAdvisor:
    """L = lambda * W with any two of WIP / throughput / cycle time, plus
    the lever Little's Law actually gives you: cycle time falls in
    proportion to WIP at fixed throughput."""

    def relate(self, *, wip: float | None = None, throughput: float | None = None,
               cycle_time: float | None = None) -> dict[str, Any]:
        computed = littles_law(wip=wip, throughput=throughput, cycle_time=cycle_time)
        solved = {"wip": wip, "throughput": throughput, "cycle_time": cycle_time}
        for k, v in solved.items():
            if v is None:
                solved[k] = computed
        levers = []
        if throughput and wip:
            levers.append(f"halving WIP from {wip:g} to {wip / 2:g} halves cycle time to "
                          f"{wip / 2 / throughput:g} at the same throughput")
            levers.append("raising throughput is the only other lever - WIP hides problems, "
                          "throughput removes them")
        return {"wip": solved["wip"], "throughput": solved["throughput"],
                "cycle_time": solved["cycle_time"], "levers": levers,
                "assumptions": ["Stable system: average arrival rate = average departure rate"]}


# ---------------------------------------------------------------- row 73 --
# Critical Path Analysis.

class CriticalPathAnalyzer:
    """Longest dependency chain sets the duration; slack = how long each
    other task can slip before it joins the critical path."""

    def analyze(self, *, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        if not tasks:
            raise ValueError("tasks required")
        cp = critical_path(tasks)
        by_id = {t["id"]: t for t in tasks}

        def longest_through(task_id: str) -> float:
            task = by_id[task_id]
            deps = task.get("depends_on", [])
            back = (max((longest_through(d) for d in deps), default=0.0)
                    + float(task["duration"]))
            dependents = [t["id"] for t in tasks if task_id in t.get("depends_on", [])]
            forward = max((float(by_id[d]["duration"]) + forward_from(d) for d in dependents),
                          default=0.0)
            return back + forward

        memo_forward: dict[str, float] = {}

        def forward_from(task_id: str) -> float:
            if task_id in memo_forward:
                return memo_forward[task_id]
            dependents = [t["id"] for t in tasks if task_id in t.get("depends_on", [])]
            value = max((float(by_id[d]["duration"]) + forward_from(d) for d in dependents),
                        default=0.0)
            memo_forward[task_id] = value
            return value

        def earliest_finish(task_id: str, seen: frozenset[str] = frozenset()) -> float:
            task = by_id[task_id]
            deps = task.get("depends_on", [])
            base = max((earliest_finish(d, seen | {task_id}) for d in deps if d not in seen),
                       default=0.0)
            return base + float(task["duration"])

        rows = []
        for t in tasks:
            ef = earliest_finish(t["id"])
            path_through = ef + forward_from(t["id"])
            slack = cp["duration"] - path_through
            rows.append({"task": t["id"], "duration": float(t["duration"]),
                         "slack": slack, "critical": t["id"] in cp["path"]})
        return {"duration": cp["duration"], "critical_path": cp["path"], "tasks": rows,
                "assumptions": ["Durations are point estimates; dependencies are as supplied",
                                 "Zero-slack tasks are exactly the critical path"]}


# ---------------------------------------------------------------- row 74 --
# Monte Carlo Simulation: project duration distributions.

class MonteCarloProjector:
    """Simulates total duration for tasks with triangular (min, mode, max)
    estimates, summing serial tasks. Seeded, so results are reproducible."""

    def simulate(self, *, tasks: list[dict[str, float]], trials: int = 1000,
                 seed: int | None = 42) -> dict[str, Any]:
        if not tasks:
            raise ValueError("tasks required")
        for t in tasks:
            if not (0 <= t["min"] <= t["mode"] <= t["max"]):
                raise ValueError("need 0 <= min <= mode <= max per task")
        import random as _random

        def sampler(rng: "_random.Random") -> float:
            return sum(rng.triangular(t["min"], t["max"], t["mode"]) for t in tasks)

        stats = monte_carlo_simulation(sampler, trials=trials, seed=seed)
        return {"task_count": len(tasks), **stats,
                "reading": f"P50 = {stats['median']:.4g}; plan to P95 = {stats['p95']:.4g} "
                           "if the deadline matters",
                "assumptions": ["Independent triangular task durations",
                                 f"{trials} trials, seed {seed}"]}


# ------------------------------------------------------------------ shared
# Safe arithmetic expression evaluation for rows 75/76 (no names beyond
# the supplied params, no calls, no attribute access).

_ALLOWED_AST = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
                ast.Name, ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div,
                ast.Pow, ast.USub, ast.UAdd, ast.Mod)


def _safe_evaluator(expression: str, params: dict[str, float]):
    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST):
            raise ValueError(f"disallowed expression element: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in params:
            raise ValueError(f"unknown parameter {node.id!r}")
    code = compile(tree, "<expr>", "eval")

    def evaluate(p: dict[str, float]) -> float:
        return float(eval(code, {"__builtins__": {}}, dict(p)))

    return evaluate


# ---------------------------------------------------------------- row 75 --
# Sensitivity Analysis.

class SensitivityExplorer:
    """Swings each parameter of a caller-supplied arithmetic model and
    ranks the impact on the output."""

    def analyze(self, *, expression: str, params: dict[str, float],
                swing: float = 0.2) -> dict[str, Any]:
        if not 0.0 < swing < 1.0:
            raise ValueError("swing must be in (0, 1)")
        evaluate = _safe_evaluator(expression, params)
        rows = sensitivity_analysis(evaluate, params, swing=swing)
        return {"expression": expression, "base_output": rows[0]["base"], "ranked": rows,
                "most_influential": rows[0]["parameter"],
                "assumptions": [f"Each parameter swung +/-{swing:.0%} one at a time",
                                 "Interactions between parameters not captured"]}


# ---------------------------------------------------------------- row 76 --
# Tornado Diagram Creation: ordered impact bars from the same swing data.

class TornadoBuilder:
    """Builds tornado data: one bar per parameter, low/high output around
    the base, widest first. Includes an ASCII rendering so the result is
    inspectable without a plotting dependency."""

    def build(self, *, expression: str, params: dict[str, float],
              swing: float = 0.2) -> dict[str, Any]:
        rows = SensitivityExplorer().analyze(expression=expression, params=params,
                                             swing=swing)["ranked"]
        base = rows[0]["base"]
        widest = rows[0]["impact"] or 1.0
        bars = []
        for r in rows:
            width = r["impact"] / widest
            low_w = abs(r["low_output"] - base) / widest
            high_w = abs(r["high_output"] - base) / widest
            bars.append({"parameter": r["parameter"], "low_output": r["low_output"],
                         "high_output": r["high_output"], "impact": r["impact"],
                         "bar": f"{'-' * int(low_w * 20):<20}|{'+' * int(high_w * 20)}"})
        return {"base_output": base, "bars": bars,
                "assumptions": ["Bar width proportional to +/-swing impact",
                                 "Same one-at-a-time caveat as sensitivity analysis"]}


# ---------------------------------------------------------------- row 77 --
# Decision Tree Construction.

class DecisionTreeBuilder:
    """Builds a decision tree from a nested spec and rolls it back: max at
    decision nodes, EV at chance nodes. Also reports the value of each
    first-level choice so the preferred decision is explicit."""

    def build(self, *, spec: dict[str, Any]) -> dict[str, Any]:
        node = self._parse(spec)
        value = evaluate_decision_tree(node)
        choices = None
        if node.kind == "decision" and node.children:
            choices = [{"label": child.label or f"option {i}",
                        "value": evaluate_decision_tree(child)}
                       for i, (_, child) in enumerate(node.children)]
        return {"value": value, "first_choices": choices,
                "best_first_choice": (max(choices, key=lambda c: c["value"])["label"]
                                      if choices else None),
                "assumptions": ["Chance-node probabilities must sum to 1 (validated)",
                                 "Rollback: max at decisions, expectation at chance nodes",
                                 DECISION_SUPPORT_CAVEAT]}

    def _parse(self, spec: dict[str, Any]) -> DecisionNode:
        kind = spec.get("kind", "leaf")
        if kind == "leaf":
            return DecisionNode(kind="leaf", value=float(spec.get("value", 0.0)),
                                label=spec.get("label", ""))
        children = []
        total_p = 0.0
        for child in spec.get("children", []):
            prob = float(child.get("prob", 1.0 if kind == "decision" else 0.0))
            children.append((prob, self._parse(child["node"])))
            total_p += prob
        if kind == "chance" and abs(total_p - 1.0) > 1e-6:
            raise ValueError(f"chance node probabilities sum to {total_p}, not 1")
        return DecisionNode(kind=kind, children=children, label=spec.get("label", ""))


# ---------------------------------------------------------------- row 78 --
# Real Options Valuation: binomial pricing of flexibility.

class RealOptionsValuer:
    """Multiplicative binomial tree for the option to expand (call) or
    abandon (put). Risk-neutral probabilities; no market claims."""

    def value(self, *, underlying: float, up: float, down: float,
              exercise_cost: float, kind: str = "expand",
              steps: int = 10, risk_free: float = 0.0) -> dict[str, Any]:
        if underlying <= 0 or exercise_cost < 0 or not 0 < down < 1 <= up:
            raise ValueError("need underlying>0, cost>=0, 0<down<1<=up")
        if steps < 1 or steps > 50:
            raise ValueError("steps must be in [1, 50]")
        if kind not in ("expand", "abandon"):
            raise ValueError("kind must be expand | abandon")
        growth = math.exp(risk_free)
        q = (growth - down) / (up - down)
        if not 0.0 <= q <= 1.0:
            raise ValueError("parameters imply an arbitrage: adjust up/down/risk_free")

        def payoff(v: float) -> float:
            return max(0.0, v - exercise_cost) if kind == "expand" \
                else max(0.0, exercise_cost - v)

        # terminal values
        level = [payoff(underlying * (up ** j) * (down ** (steps - j)))
                 for j in range(steps + 1)]
        for _ in range(steps):
            level = [(q * level[j + 1] + (1 - q) * level[j]) / growth
                     for j in range(len(level) - 1)]
        return {"option_value": level[0], "kind": kind, "risk_neutral_prob": q,
                "caveat": DECISION_SUPPORT_CAVEAT,
                "assumptions": [f"{steps}-step binomial tree, risk-neutral pricing",
                                 "Flexibility is only worth paying for when the decision can "
                                 "actually be deferred or reversed"]}


# ---------------------------------------------------------------- row 79 --
# Game Theory Application: normal-form analysis with dominance elimination.

class GameAnalyzer:
    """Analyzes a two-player normal-form game: strict-dominance
    elimination, best responses, and Pareto-optimal cells."""

    def analyze(self, *, row_payoffs: list[list[float]],
                col_payoffs: list[list[float]]) -> dict[str, Any]:
        n = len(row_payoffs)
        if n == 0 or any(len(r) != len(row_payoffs[0]) for r in row_payoffs):
            raise ValueError("row_payoffs must be rectangular")
        m = len(row_payoffs[0])
        if len(col_payoffs) != n or any(len(r) != m for r in col_payoffs):
            raise ValueError("col_payoffs must match row_payoffs shape")

        def dominates(payoffs: list[list[float]], i: int, j: int, *, row_player: bool) -> bool:
            if row_player:
                return all(payoffs[i][c] > payoffs[j][c] for c in range(m))
            return all(payoffs[r][i] > payoffs[r][j] for r in range(n))

        row_dominated = [j for j in range(n)
                         if any(dominates(row_payoffs, i, j, row_player=True)
                                for i in range(n) if i != j)]
        col_dominated = [j for j in range(m)
                         if any(dominates(col_payoffs, i, j, row_player=False)
                                for i in range(m) if i != j)]
        best_responses = {
            "row": {c: max(range(n), key=lambda r: row_payoffs[r][c]) for c in range(m)},
            "col": {r: max(range(m), key=lambda c: col_payoffs[r][c]) for r in range(n)},
        }
        pareto_cells = []
        for r in range(n):
            for c in range(m):
                dominated_cell = any(
                    (row_payoffs[r2][c2] >= row_payoffs[r][c]
                     and col_payoffs[r2][c2] >= col_payoffs[r][c]
                     and (row_payoffs[r2][c2] > row_payoffs[r][c]
                          or col_payoffs[r2][c2] > col_payoffs[r][c]))
                    for r2 in range(n) for c2 in range(m))
                if not dominated_cell:
                    pareto_cells.append((r, c))
        return {"shape": [n, m], "dominated_rows": row_dominated,
                "dominated_cols": col_dominated, "best_responses": best_responses,
                "pareto_optimal_cells": pareto_cells,
                "assumptions": ["Simultaneous moves, complete information, pure strategies",
                                 DECISION_SUPPORT_CAVEAT]}


# ---------------------------------------------------------------- row 80 --
# Nash Equilibrium Identification: pure (2x2 helper) + mixed for 2x2.

class NashFinder:
    def find(self, *, row_payoffs: list[list[float]],
             col_payoffs: list[list[float]]) -> dict[str, Any]:
        if len(row_payoffs) != 2 or any(len(r) != 2 for r in row_payoffs):
            raise ValueError("2x2 games only")
        pure = nash_equilibria_2x2(row_payoffs, col_payoffs)
        # Mixed equilibrium for 2x2, interior solutions only:
        # row player mixes to make col indifferent, and vice versa.
        mixed = None
        dc = col_payoffs[0][0] - col_payoffs[0][1] - col_payoffs[1][0] + col_payoffs[1][1]
        dr = row_payoffs[0][0] - row_payoffs[1][0] - row_payoffs[0][1] + row_payoffs[1][1]
        if dc != 0 and dr != 0:
            p = (col_payoffs[1][1] - col_payoffs[1][0]) / dc  # prob row plays row 0
            q = (row_payoffs[1][1] - row_payoffs[0][1]) / dr  # prob col plays col 0
            if 0.0 < p < 1.0 and 0.0 < q < 1.0:
                mixed = {"row_plays_first_with": p, "col_plays_first_with": q}
        return {"pure_equilibria": [{"row": r, "col": c} for r, c in pure],
                "mixed_equilibrium": mixed,
                "reading": ("multiple equilibria - coordination or focal points decide"
                            if len(pure) > 1 else
                            "unique stable outcome" if len(pure) == 1 else
                            "no pure equilibrium; play the mixed strategy" if mixed else
                            "no equilibrium found"),
                "assumptions": ["2x2 normal form, expected-payoff maximizing players",
                                 DECISION_SUPPORT_CAVEAT]}


# ---------------------------------------------------------------- row 81 --
# Mechanism Design: VCG allocation + incentive check on supplied deviations.

class MechanismDesigner:
    """Computes the Vickrey-Clarke-Groves allocation and payments for
    reported valuations, then checks incentive compatibility against
    caller-supplied misreports: truth-telling must beat every deviation."""

    def vcg(self, *, agents: dict[str, dict[str, float]]) -> dict[str, Any]:
        """agents: {agent: {item: value}}; one unit of each item, each agent
        gets at most one item (greedy matching by value)."""
        if not agents:
            raise ValueError("agents required")
        items = sorted({item for v in agents.values() for item in v})
        # exact optimal matching by exhaustive search when small
        from itertools import permutations
        names = sorted(agents)
        best_welfare, best_alloc = -math.inf, {}
        if len(items) <= 8:
            for perm in permutations(items, min(len(names), len(items))):
                alloc = dict(zip(names, perm))
                welfare = sum(agents[a].get(i, 0.0) for a, i in alloc.items())
                if welfare > best_welfare:
                    best_welfare, best_alloc = welfare, alloc
        else:
            remaining = set(items)
            best_alloc, best_welfare = {}, 0.0
            for a in names:
                pick = max(remaining, key=lambda i: agents[a].get(i, 0.0), default=None)
                if pick is not None:
                    best_alloc[a] = pick
                    best_welfare += agents[a].get(pick, 0.0)
                    remaining.discard(pick)

        def welfare_without(excluded: str) -> float:
            others = [a for a in names if a != excluded]
            if not others:
                return 0.0
            best = 0.0
            for perm in permutations(items, min(len(others), len(items))):
                w = sum(agents[a].get(i, 0.0) for a, i in zip(others, perm))
                best = max(best, w)
            return best

        payments = {}
        for a in names:
            if a not in best_alloc:
                payments[a] = 0.0
                continue
            others_welfare_with = sum(agents[o].get(i, 0.0)
                                      for o, i in best_alloc.items() if o != a)
            payments[a] = welfare_without(a) - others_welfare_with
        return {"allocation": best_alloc, "payments": payments,
                "total_welfare": best_welfare,
                "assumptions": ["Quasi-linear utility; payment = externality imposed on others",
                                 "Truthful reporting is dominant under VCG"]}

    def check_incentives(self, *, agent: str, true_values: dict[str, float],
                         others: dict[str, dict[str, float]],
                         deviations: list[dict[str, float]]) -> dict[str, Any]:
        """Replay VCG with the agent's report swapped for each deviation,
        holding others fixed; utility is always valued at TRUE values.
        Truth-telling must beat every supplied deviation."""
        results = []
        for label, report in [("truthful", true_values),
                              *[(f"deviation {i + 1}", d) for i, d in enumerate(deviations)]]:
            out = self.vcg(agents={**others, agent: report})
            won = out["allocation"].get(agent)
            utility = (true_values.get(won, 0.0) if won else 0.0) - out["payments"].get(agent, 0.0)
            results.append({"label": label, "report": report, "won": won,
                            "payment": out["payments"].get(agent, 0.0),
                            "utility_at_true_values": utility})
        truthful = results[0]["utility_at_true_values"]
        ic = all(r["utility_at_true_values"] <= truthful + 1e-9 for r in results[1:])
        return {"incentive_compatible": ic, "outcomes": results,
                "assumptions": ["Utility = true value of what is won - payment",
                                 "Only the supplied deviations were checked"]}


# ---------------------------------------------------------------- row 82 --
# Auction Theory Application.

class AuctionAdvisor:
    """Equilibrium bidding guidance by auction format: truthful in
    second-price, shaded in first-price (uniform values), with an explicit
    winner's-curse warning for common-value settings."""

    def recommend(self, *, auction_type: str, value: float,
                  n_bidders: int = 2, common_value: bool = False) -> dict[str, Any]:
        if value < 0 or n_bidders < 2:
            raise ValueError("need value >= 0 and n_bidders >= 2")
        if auction_type == "second_price":
            bid, rationale = value, "bidding your true value is a dominant strategy"
        elif auction_type == "first_price":
            bid = value * (n_bidders - 1) / n_bidders
            rationale = (f"shade to (n-1)/n of value with {n_bidders} bidders; "
                         "uniform-value equilibrium")
        elif auction_type in ("english", "dutch"):
            bid = value if auction_type == "english" else value * (n_bidders - 1) / n_bidders
            rationale = ("English: stay in until price passes your value"
                         if auction_type == "english" else
                         "Dutch: strategically equivalent to first-price sealed bid")
        else:
            raise ValueError("auction_type must be first_price | second_price | english | dutch")
        warnings = []
        if common_value:
            warnings.append("common-value setting: the winner likely overestimated - "
                            "discount your estimate before bidding (winner's curse)")
        return {"auction_type": auction_type, "recommended_bid": bid,
                "rationale": rationale, "warnings": warnings,
                "caveat": DECISION_SUPPORT_CAVEAT,
                "assumptions": ["Independent private values unless common_value=true",
                                 "Risk-neutral bidders"]}


# ---------------------------------------------------------------- row 83 --
# Signaling Theory.

class SignalingAssessor:
    """Separating vs pooling: a signal separates types only when it costs
    the low type more than the benefit while costing the high type less
    than the benefit (single crossing). Cheap talk separates nothing."""

    def assess(self, *, benefit: float, cost_high_type: float,
               cost_low_type: float) -> dict[str, Any]:
        for name, v in (("benefit", benefit), ("cost_high_type", cost_high_type),
                        ("cost_low_type", cost_low_type)):
            if v < 0:
                raise ValueError(f"{name} must be >= 0")
        separating = cost_low_type > benefit > cost_high_type >= 0 and cost_low_type > cost_high_type
        if cost_high_type >= benefit and cost_low_type >= benefit:
            regime = "no signaling: the signal costs more than it is worth to everyone"
        elif cost_low_type <= benefit and cost_high_type <= benefit:
            regime = "pooling: both types send the signal, so it certifies nothing"
        elif separating:
            regime = "separating: only the high type finds the signal worth sending"
        else:
            regime = "partial: costs do not cleanly order types"
        return {"regime": regime, "separating": separating,
                "credibility": ("costly signal - interpretable as quality evidence"
                                if separating else
                                "cheap or universal signal - treat as weak evidence"),
                "assumptions": ["Two types (high/low), known costs and benefit",
                                 "Single-crossing condition is the separating test"]}


# ---------------------------------------------------------------- row 84 --
# Principal-Agent Problem Solving.

class PrincipalAgentDesigner:
    """Linear-share contracts: for each candidate share, the agent picks
    the effort that maximizes share x expected output - effort cost. The
    cheapest share that makes the principal's target effort incentive
    compatible (and individually rational) is the recommendation."""

    def design(self, *, efforts: list[dict[str, float]], target_effort: str,
               shares: list[float] | None = None) -> dict[str, Any]:
        if not efforts:
            raise ValueError("efforts required")
        shares = shares or [round(0.1 * i, 2) for i in range(11)]
        by_level = {e["level"]: e for e in efforts}
        if target_effort not in by_level:
            raise ValueError(f"unknown target effort {target_effort!r}")
        rows = []
        for s in shares:
            if not 0.0 <= s <= 1.0:
                raise ValueError("shares must be in [0, 1]")
            best_effort, best_payoff = None, -math.inf
            for e in efforts:
                payoff = s * float(e["expected_output"]) - float(e["cost"])
                if payoff > best_payoff:
                    best_effort, best_payoff = e["level"], payoff
            target = by_level[target_effort]
            principal_net = (1 - s) * float(target["expected_output"])
            rows.append({"share": s, "agent_chooses": best_effort,
                         "agent_payoff": best_payoff,
                         "principal_net_if_target": principal_net,
                         "target_is_ic": best_effort == target_effort,
                         "participation_ok": best_payoff >= 0.0})
        valid = [r for r in rows if r["target_is_ic"] and r["participation_ok"]]
        recommendation = (min(valid, key=lambda r: r["share"]) if valid else None)
        return {"target_effort": target_effort, "contracts": rows,
                "recommended_share": recommendation["share"] if recommendation else None,
                "principal_net": recommendation["principal_net_if_target"] if recommendation else None,
                "reading": (f"a {recommendation['share']:.0%} share makes '{target_effort}' "
                            "the agent's own best choice"
                            if recommendation else
                            "no tested share makes the target effort self-enforcing - "
                            "fix monitoring or the effort menu instead of raising pay blindly"),
                "caveat": DECISION_SUPPORT_CAVEAT,
                "assumptions": ["Risk-neutral agent, linear share contract, no limited liability",
                                 "Effort menu and expected outputs are caller estimates"]}
