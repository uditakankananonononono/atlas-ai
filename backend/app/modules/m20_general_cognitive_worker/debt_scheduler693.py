"""Row 693 scoped capability: exact bounded technical-debt scheduling.

Given a finite caller-supplied debt dependency graph and a declared
engineering-hour budget, compute the exact feasible subset that maximizes
caller-declared benefit subject to prerequisite closure and the budget, via
bounded exhaustive search (at most 2**12 = 4096 subsets). Benefits and costs
are caller declarations, not predicted savings. No repository edits, no
learned prioritization, no scheduled external task.
"""
from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from typing import Any

MAX_ITEMS = 12  # exact bound: 2**12 = 4096 enumerated subsets is the state cap


def _finite_number(value: Any, field: str, *, minimum: float) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} requires a finite non-boolean number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field} requires a finite number")
    number = Fraction(value)
    if number < minimum:
        raise ValueError(f"{field} requires a value >= {minimum:g}")
    return number


def _plain(number: Fraction) -> int | float:
    return int(number) if number.denominator == 1 else float(number)


def _validate(data: Any) -> tuple[list[dict[str, Any]], Fraction]:
    if not isinstance(data, dict):
        raise ValueError("input must be an object with items and budget_hours")
    items = data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise ValueError(f"items require a list of 1..{MAX_ITEMS} debt items")
    if "budget_hours" not in data:
        raise ValueError("budget_hours is required")
    budget = _finite_number(data["budget_hours"], "budget_hours", minimum=0)
    seen: set[str] = set()
    parsed: list[dict[str, Any]] = []
    for index, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValueError(f"items[{index}] must be an object")
        ident = raw.get("id")
        if not isinstance(ident, str) or not ident:
            raise ValueError(f"items[{index}].id requires a non-empty string")
        if ident in seen:
            raise ValueError(f"duplicate item id: {ident}")
        seen.add(ident)
        if "benefit" not in raw or "cost" not in raw:
            raise ValueError(f"items[{index}] requires declared benefit and cost")
        benefit = _finite_number(raw["benefit"], f"items[{index}].benefit", minimum=0)
        cost = _finite_number(raw["cost"], f"items[{index}].cost", minimum=0)
        depends_on = raw.get("depends_on", [])
        if not isinstance(depends_on, list) or any(not isinstance(d, str) for d in depends_on):
            raise ValueError(f"items[{index}].depends_on requires a list of item ids")
        parsed.append({"id": ident, "benefit": benefit, "cost": cost,
                       "depends_on": list(dict.fromkeys(depends_on)), "input_index": index})
    by_id = {x["id"]: x for x in parsed}
    for item in parsed:
        for dep in item["depends_on"]:
            if dep not in by_id:
                raise ValueError(f"unknown dependency reference: {dep}")
    # Cycle rejection via iterative topological removal.
    remaining = {x["id"]: set(x["depends_on"]) for x in parsed}
    progressed = True
    while remaining and progressed:
        progressed = False
        for ident in [i for i, deps in remaining.items() if not deps]:
            del remaining[ident]
            for deps in remaining.values():
                deps.discard(ident)
            progressed = True
    if remaining:
        raise ValueError("dependency cycle detected involving: " + ", ".join(sorted(remaining)))
    return parsed, budget


def _closure_costs(items: list[dict[str, Any]]) -> dict[str, Fraction]:
    by_id = {x["id"]: x for x in items}
    memo: dict[str, Fraction] = {}

    def total(ident: str) -> Fraction:
        if ident not in memo:
            item = by_id[ident]
            memo[ident] = item["cost"] + sum((total(d) for d in item["depends_on"]), Fraction(0))
        return memo[ident]

    return {x["id"]: total(x["id"]) for x in items}


def schedule_debt(data: Any) -> dict[str, Any]:
    """Return the exact optimal debt-repair subset with an exhaustive-search certificate."""
    items, budget = _validate(data)
    n = len(items)
    closure_cost = _closure_costs(items)
    # Bit i of a mask selects items[i]; closure uses dependency bitmasks.
    dep_mask = []
    for item in items:
        mask = 1 << item["input_index"]
        stack = list(item["depends_on"])
        by_id = {x["id"]: x for x in items}
        seen = set()
        while stack:
            dep = stack.pop()
            if dep in seen:
                continue
            seen.add(dep)
            mask |= 1 << by_id[dep]["input_index"]
            stack.extend(by_id[dep]["depends_on"])
        dep_mask.append(mask)
    best_benefit: Fraction | None = None
    best_masks: list[int] = []
    best_cost: Fraction = Fraction(0)
    subsets = 1 << n  # bounded by the 4096 state cap
    for mask in range(subsets):
        if any((mask >> i) & 1 and dep_mask[i] & ~mask for i in range(n)):
            continue  # prerequisite closure violated
        cost = sum((items[i]["cost"] for i in range(n) if (mask >> i) & 1), Fraction(0))
        if cost > budget:
            continue
        benefit = sum((items[i]["benefit"] for i in range(n) if (mask >> i) & 1), Fraction(0))
        if best_benefit is None or benefit > best_benefit:
            best_benefit, best_masks, best_cost = benefit, [mask], cost
        elif benefit == best_benefit:
            best_masks.append(mask)
            if cost < best_cost:
                best_cost = cost  # report the cheapest cost among tied optima

    def sorted_ids(mask: int) -> tuple[str, ...]:
        return tuple(sorted(items[i]["id"] for i in range(n) if (mask >> i) & 1))

    winner = min(best_masks, key=sorted_ids)  # deterministic tie-break, input-order independent
    selected_ids = list(sorted_ids(winner))
    selected_cost = sum((items[i]["cost"] for i in range(n) if (winner >> i) & 1), Fraction(0))
    unselected = [
        {"id": item["id"],
         "reason": "infeasible_within_budget" if closure_cost[item["id"]] > budget
                   else "not_selected_optimal_tradeoff",
         "closure_cost_hours": _plain(closure_cost[item["id"]])}
        for item in sorted(items, key=lambda x: x["id"]) if item["id"] not in set(selected_ids)
    ]
    canonical = json.dumps({"items": data["items"], "budget_hours": data["budget_hours"]},
                           sort_keys=True, separators=(",", ":"))
    return {
        "row": 693,
        "capability": "Technical Debt Management",
        "scope": "bounded_exact_scheduling_over_supplied_graph",
        "status": "optimal_selection_certified",
        "selected_ids": selected_ids,
        "unselected": unselected,
        "total_benefit": _plain(best_benefit),
        "total_cost": _plain(selected_cost),
        "budget_hours": _plain(budget),
        "certificate": {
            "algorithm": "bounded_exhaustive_subset_search",
            "items": n,
            "subsets_enumerated": subsets,
            "state_cap": 2 ** MAX_ITEMS,
            "optimal_benefit": _plain(best_benefit),
            "optimal_cost": _plain(selected_cost),
            "prerequisite_closure_required": True,
            "tie_break": "lexicographically smallest sorted selected-id tuple among benefit-maximal feasible subsets",
            "independently_reproducible": True,
        },
        "item_trace": [
            {"id": x["id"], "input_index": x["input_index"],
             "benefit": _plain(x["benefit"]), "cost": _plain(x["cost"]),
             "depends_on": x["depends_on"]}
            for x in items
        ],  # source order kept unsorted for provenance; selection never depends on it
        "provenance": {
            "input_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "benefit_source": "caller_declared",
            "cost_source": "caller_declared",
            "benefits_are_predicted_savings": False,
            "repository_edits": False,
            "learned_prioritization": False,
            "external_task_scheduled": False,
        },
        "human_review_required": True,
    }
