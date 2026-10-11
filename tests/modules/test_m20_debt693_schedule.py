"""Row 693 scoped capability: exact bounded technical-debt scheduling.

Independent validators: brute-force subset oracle, hand-computed fixtures,
negative input validation, tie-order independence and a greedy-baseline floor.
"""
import hashlib
import itertools
import json
import math
import random

import pytest

from app.modules.m20_general_cognitive_worker.debt_scheduler693 import MAX_ITEMS, schedule_debt


def oracle(data):
    """Independent exhaustive oracle: max-benefit closed subset within budget."""
    items = data["items"]
    by_id = {x["id"]: x for x in items}
    budget = data["budget_hours"]

    def closure(seed):
        seen = set()
        stack = [seed]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(by_id[cur].get("depends_on", []))
        return seen

    best_benefit = None
    best_sets = []
    for r in range(len(items) + 1):
        for combo in itertools.combinations((x["id"] for x in items), r):
            selected = set(combo)
            if any(not closure(i) <= selected for i in selected):
                continue
            cost = sum(by_id[i]["cost"] for i in selected)
            if cost > budget:
                continue
            benefit = sum(by_id[i]["benefit"] for i in selected)
            if best_benefit is None or benefit > best_benefit:
                best_benefit, best_sets = benefit, [selected]
            elif benefit == best_benefit:
                best_sets.append(selected)
    expected = min(best_sets, key=lambda s: tuple(sorted(s)))
    return best_benefit, sorted(expected)


def fixture():
    # a alone is tempting but blocks the budget; the b-chain plus c wins, and b
    # depends on d (cheap prerequisite). a stays feasible yet a + c is over budget.
    return {
        "budget_hours": 10,
        "items": [
            {"id": "a", "benefit": 9, "cost": 7},
            {"id": "b", "benefit": 8, "cost": 4, "depends_on": ["d"]},
            {"id": "c", "benefit": 5, "cost": 4},
            {"id": "d", "benefit": 0, "cost": 1},
        ],
    }


def test_known_answer_prerequisite_closure_and_optimum():
    r = schedule_debt(fixture())
    assert r["selected_ids"] == ["b", "c", "d"]
    assert r["total_benefit"] == 13 and r["total_cost"] == 9
    assert r["status"] == "optimal_selection_certified"
    reasons = {x["id"]: x["reason"] for x in r["unselected"]}
    assert reasons == {"a": "not_selected_optimal_tradeoff"}
    cert = r["certificate"]
    assert cert["subsets_enumerated"] == 16 and cert["state_cap"] == 2**MAX_ITEMS
    assert cert["algorithm"] == "bounded_exhaustive_subset_search"


def test_bruteforce_oracle_agrees_on_generated_corpus():
    rng = random.Random(693)
    for case in range(150):
        n = rng.randrange(1, 9)
        ids = [f"i{k}" for k in range(n)]
        items = []
        for k, i in enumerate(ids):
            deps = [d for d in ids[:k] if rng.random() < 0.3]  # acyclic by construction
            items.append({
                "id": i,
                "benefit": rng.randrange(0, 20),
                "cost": rng.randrange(1, 10),
                "depends_on": deps,
            })
        data = {"items": items, "budget_hours": rng.randrange(0, 25)}
        r = schedule_debt(data)
        best, expected = oracle(data)
        assert r["total_benefit"] == best, case
        assert r["selected_ids"] == expected, case
        # Independent certificate re-verification.
        selected = set(r["selected_ids"])
        by_id = {x["id"]: x for x in items}
        assert all(set(by_id[i].get("depends_on", [])) <= selected for i in selected)
        assert r["total_cost"] <= data["budget_hours"]
        assert r["certificate"]["subsets_enumerated"] == 2**n


def test_exact_item_bounds_12_accepted_13_rejected():
    items = [{"id": f"i{k}", "benefit": 1, "cost": 1} for k in range(12)]
    r = schedule_debt({"items": items, "budget_hours": 12})
    assert len(r["selected_ids"]) == 12
    assert r["certificate"]["subsets_enumerated"] == 4096
    items13 = items + [{"id": "i12", "benefit": 1, "cost": 1}]
    with pytest.raises(ValueError, match="1..12"):
        schedule_debt({"items": items13, "budget_hours": 99})
    with pytest.raises(ValueError, match="1..12"):
        schedule_debt({"items": [], "budget_hours": 1})


def test_zero_budget_and_exact_cost_boundary():
    # Zero budget still admits a zero-cost chain and nothing else.
    data = {"items": [
        {"id": "free", "benefit": 3, "cost": 0},
        {"id": "paid", "benefit": 100, "cost": 1},
    ], "budget_hours": 0}
    r = schedule_debt(data)
    assert r["selected_ids"] == ["free"] and r["total_cost"] == 0
    # Budget exactly equal to closure cost selects; one cent less does not.
    exact = {"items": [
        {"id": "x", "benefit": 5, "cost": 4, "depends_on": ["y"]},
        {"id": "y", "benefit": 1, "cost": 6},
    ], "budget_hours": 10}
    assert schedule_debt(exact)["selected_ids"] == ["x", "y"]
    tight = {**exact, "budget_hours": 9}
    r = schedule_debt(tight)
    assert r["selected_ids"] == ["y"]
    reasons = {u["id"]: u["reason"] for u in r["unselected"]}
    assert reasons["x"] == "infeasible_within_budget"


def test_infeasible_costly_prerequisite_named_not_dropped_silently():
    data = {"items": [
        {"id": "big", "benefit": 50, "cost": 2, "depends_on": ["heavy"]},
        {"id": "heavy", "benefit": 0, "cost": 100},
        {"id": "small", "benefit": 4, "cost": 3},
    ], "budget_hours": 10}
    r = schedule_debt(data)
    assert r["selected_ids"] == ["small"]
    reasons = {u["id"]: u["reason"] for u in r["unselected"]}
    assert reasons["big"] == "infeasible_within_budget"
    assert reasons["heavy"] == "infeasible_within_budget"


def test_dependency_cycle_and_unknown_reference_rejected():
    cyc = {"items": [
        {"id": "a", "benefit": 1, "cost": 1, "depends_on": ["b"]},
        {"id": "b", "benefit": 1, "cost": 1, "depends_on": ["a"]},
    ], "budget_hours": 5}
    with pytest.raises(ValueError, match="cycle"):
        schedule_debt(cyc)
    selfdep = {"items": [{"id": "a", "benefit": 1, "cost": 1, "depends_on": ["a"]}], "budget_hours": 5}
    with pytest.raises(ValueError, match="cycle"):
        schedule_debt(selfdep)
    unknown = {"items": [{"id": "a", "benefit": 1, "cost": 1, "depends_on": ["ghost"]}], "budget_hours": 5}
    with pytest.raises(ValueError, match="unknown"):
        schedule_debt(unknown)


def test_duplicate_ids_rejected():
    data = {"items": [
        {"id": "a", "benefit": 1, "cost": 1},
        {"id": "a", "benefit": 2, "cost": 1},
    ], "budget_hours": 5}
    with pytest.raises(ValueError, match="duplicate"):
        schedule_debt(data)


@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), float("-inf"), "5", None, [1]])
def test_nonboolean_finite_numerics_enforced(bad):
    base = {"items": [{"id": "a", "benefit": 1, "cost": 1}], "budget_hours": 5}
    for field_path in (("items", 0, "benefit"), ("items", 0, "cost"), ("budget_hours",)):
        data = json.loads(json.dumps(base))
        target = data
        for key in field_path[:-1]:
            target = target[key]
        target[field_path[-1]] = bad
        with pytest.raises(ValueError):
            schedule_debt(data)


@pytest.mark.parametrize("bad", [
    {"benefit": -1, "cost": 1},
    {"benefit": 1, "cost": -1},
])
def test_negative_declarations_rejected(bad):
    item = {"id": "a", **bad}
    with pytest.raises(ValueError):
        schedule_debt({"items": [item], "budget_hours": 5})


def test_tie_order_independence_under_all_permutations():
    data = {"items": [
        {"id": "p", "benefit": 4, "cost": 4},
        {"id": "q", "benefit": 4, "cost": 4},
        {"id": "r", "benefit": 3, "cost": 2},
        {"id": "s", "benefit": 1, "cost": 1, "depends_on": ["r"]},
    ], "budget_hours": 4}
    base = schedule_debt(data)
    # p and q tie on benefit/cost; s drags r in. Deterministic winner: ["p"]? No:
    # r+s gives 4 benefit at cost 3, same benefit as p or q alone, lower cost but
    # benefit ties; lexicographically smallest sorted tuple among benefit-maximal
    # subsets wins: ["p"] beats ["q"] and ["r", "s"].
    assert base["selected_ids"] == ["p"]
    for perm in itertools.permutations(data["items"]):
        out = schedule_debt({"items": list(perm), "budget_hours": 4})
        assert out["selected_ids"] == base["selected_ids"]
        assert out["total_benefit"] == base["total_benefit"]
        assert out["total_cost"] == base["total_cost"]
        assert out["certificate"] == base["certificate"]
        assert [x["id"] for x in out["unselected"]] == [x["id"] for x in base["unselected"]]


def test_receipt_determinism_and_unsorted_source_trace():
    data = fixture()
    r1 = schedule_debt(data)
    r2 = schedule_debt(json.loads(json.dumps(data)))
    assert r1 == r2
    assert [t["id"] for t in r1["item_trace"]] == ["a", "b", "c", "d"]  # source order, unsorted
    assert [t["input_index"] for t in r1["item_trace"]] == [0, 1, 2, 3]
    canonical = json.dumps({"items": data["items"], "budget_hours": data["budget_hours"]},
                           sort_keys=True, separators=(",", ":"))
    assert r1["provenance"]["input_sha256"] == hashlib.sha256(canonical.encode()).hexdigest()


def test_provenance_and_no_external_side_effects_declared():
    prov = schedule_debt(fixture())["provenance"]
    assert prov["benefit_source"] == "caller_declared" and prov["cost_source"] == "caller_declared"
    assert prov["benefits_are_predicted_savings"] is False
    assert prov["repository_edits"] is False
    assert prov["learned_prioritization"] is False
    assert prov["external_task_scheduled"] is False


def greedy_baseline(data):
    by_id = {x["id"]: x for x in data["items"]}

    def closure(seed):
        seen, stack = set(), [seed]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(by_id[cur].get("depends_on", []))
        return seen

    ranked = sorted(data["items"],
                    key=lambda x: (x["benefit"] / x["cost"] if x["cost"] else math.inf),
                    reverse=True)
    selected, spent = set(), 0
    for x in ranked:
        add = closure(x["id"]) - selected
        cost = sum(by_id[i]["cost"] for i in add)
        if spent + cost <= data["budget_hours"]:
            selected |= add
            spent += cost
    return sum(by_id[i]["benefit"] for i in selected)


def test_domain_floor_exhaustive_never_loses_to_greedy_baseline():
    rng = random.Random(6930)
    strict_wins = 0
    for case in range(120):
        n = rng.randrange(2, 10)
        ids = [f"i{k}" for k in range(n)]
        items = [{
            "id": i,
            "benefit": rng.randrange(0, 30),
            "cost": rng.randrange(1, 12),
            "depends_on": [d for d in ids[:k] if rng.random() < 0.25],
        } for k, i in enumerate(ids)]
        data = {"items": items, "budget_hours": rng.randrange(1, 30)}
        optimal = schedule_debt(data)["total_benefit"]
        greedy = greedy_baseline(data)
        assert optimal >= greedy, case
        strict_wins += optimal > greedy
    assert strict_wins > 0  # the scoped capability adds measurable value over the baseline


def test_budget_and_item_shape_validation():
    with pytest.raises(ValueError):
        schedule_debt({"items": [{"id": "a", "benefit": 1, "cost": 1}]})  # missing budget
    with pytest.raises(ValueError):
        schedule_debt({"items": [{"id": "a", "benefit": 1, "cost": 1}], "budget_hours": -1})
    with pytest.raises(ValueError):
        schedule_debt({"items": [{"id": "", "benefit": 1, "cost": 1}], "budget_hours": 1})
    with pytest.raises(ValueError):
        schedule_debt({"items": [{"id": "a", "benefit": 1}], "budget_hours": 1})  # missing cost
    with pytest.raises(ValueError):
        schedule_debt({"items": "nope", "budget_hours": 1})
    with pytest.raises(ValueError):
        schedule_debt("nope")
