"""Row88 scoped screening-menu IR/IC checker tests."""
import copy
import itertools
from fractions import Fraction

import pytest

from app.modules.m20_general_cognitive_worker import screening_menu88 as mod
from app.modules.m20_general_cognitive_worker.screening_menu88 import check_screening_menu

SRC = "declared/table-1"


def U(rows):
    return [{"type_id": t, "option_id": o, "utility": v} for (t, o), v in rows.items()]


def base():
    return {
        "source_ref": SRC,
        "utility_basis": "declared_table",
        "tie_policy": {"weak_ic": False, "weak_ir": False},
        "types": [{"id": "high", "source_ref": "s/t1"}, {"id": "low", "source_ref": "s/t2"}],
        "options": [{"id": "basic", "source_ref": "s/o1"}, {"id": "premium", "source_ref": "s/o2"}],
        "outside_options": [{"type_id": "high", "utility": 0, "source_ref": "s/x1"},
                            {"type_id": "low", "utility": "0", "source_ref": "s/x2"}],
        "utilities": U({("high", "basic"): 5, ("high", "premium"): 7, ("low", "basic"): 4, ("low", "premium"): 1}),
        "menus": [{"id": "m1", "option_ids": ["basic", "premium"], "source_ref": "s/m1",
                   "mapping": [{"type_id": "high", "option_id": "premium"}, {"type_id": "low", "option_id": "basic"}]}],
        "select": True,
    }


def msg(d):
    with pytest.raises(ValueError) as e:
        check_screening_menu(d)
    return str(e.value)


def menu(r, mid="m1"):
    return next(m for m in r["menus"] if m["id"] == mid)


# ---------- known answers ----------
def test_feasible_separating_menu():
    r = check_screening_menu(base())
    m = menu(r)
    assert m["feasible"] is True and m["ir_violations"] == [] and m["ic_violations"] == [] and m["ties"] == []
    assert r["feasible_menu_ids"] == ["m1"] and r["selected_menu_id"] == "m1"
    assert r["no_feasible_menu"] is False


def test_ic_violation_exact_deviation():
    d = base(); d["utilities"] = U({("high", "basic"): 5, ("high", "premium"): 7, ("low", "basic"): 2, ("low", "premium"): 3})
    m = menu(check_screening_menu(d))
    assert m["feasible"] is False and m["ir_violations"] == []
    assert m["ic_violations"] == [{"type_id": "low", "chosen": "basic", "deviation": "premium",
                                   "chosen_utility": "2", "deviation_utility": "3", "gain": "1"}]


def test_ir_violation_exact_shortfall():
    d = base(); d["utilities"] = U({("high", "basic"): 5, ("high", "premium"): 7, ("low", "basic"): "-3/2", ("low", "premium"): -4})
    m = menu(check_screening_menu(d))
    assert m["ic_violations"] == [] and m["feasible"] is False
    assert m["ir_violations"] == [{"type_id": "low", "chosen": "basic", "chosen_utility": "-3/2",
                                   "outside_utility": "0", "shortfall": "3/2"}]


def test_ir_and_ic_are_independent_failures():
    # low: IR fails (basic < outside 0) AND IC fails (prefers premium, still negative)
    d = base(); d["utilities"] = U({("high", "basic"): 5, ("high", "premium"): 7, ("low", "basic"): -3, ("low", "premium"): -1})
    m = menu(check_screening_menu(d))
    assert len(m["ir_violations"]) == 1 and len(m["ic_violations"]) == 1
    # IC only: high prefers basic although mapped to premium, both above outside
    d = base(); d["utilities"] = U({("high", "basic"): 8, ("high", "premium"): 7, ("low", "basic"): 4, ("low", "premium"): 1})
    m = menu(check_screening_menu(d))
    assert m["ir_violations"] == [] and [v["type_id"] for v in m["ic_violations"]] == ["high"]
    # IR only
    d = base(); d["outside_options"][0]["utility"] = 9
    m = menu(check_screening_menu(d))
    assert m["ic_violations"] == [] and [v["type_id"] for v in m["ir_violations"]] == ["high"]


def test_ties_weak_only_when_declared():
    d = base(); d["utilities"] = U({("high", "basic"): 5, ("high", "premium"): 7, ("low", "basic"): 4, ("low", "premium"): 4})
    m = menu(check_screening_menu(d))
    assert m["feasible"] is False
    assert m["ic_violations"] == [{"type_id": "low", "chosen": "basic", "deviation": "premium",
                                   "chosen_utility": "4", "deviation_utility": "4", "gain": "0"}]
    assert m["ties"] == [{"kind": "ic", "type_id": "low", "chosen": "basic", "alternative": "premium",
                          "utility": "4", "accepted_as_weak": False}]
    d["tie_policy"]["weak_ic"] = True
    m = menu(check_screening_menu(d))
    assert m["feasible"] is True and m["ic_violations"] == []
    assert m["ties"][0]["accepted_as_weak"] is True
    # IR tie follows weak_ir only
    d = base(); d["outside_options"][1]["utility"] = 4
    m = menu(check_screening_menu(d))
    assert m["ir_violations"][0]["shortfall"] == "0" and m["feasible"] is False
    d["tie_policy"]["weak_ic"] = True
    assert menu(check_screening_menu(d))["feasible"] is False  # weak_ic does not excuse an IR tie
    d["tie_policy"] = {"weak_ic": False, "weak_ir": True}
    m = menu(check_screening_menu(d))
    assert m["feasible"] is True and m["ties"] == [{"kind": "ir", "type_id": "low", "chosen": "basic", "alternative": "outside",
                                                    "utility": "4", "accepted_as_weak": True}]


def test_intended_outside_and_rational_equality():
    d = base()
    d["menus"][0]["mapping"][1] = {"type_id": "low", "option_id": "outside"}  # low opts out
    d["utilities"] = U({("high", "basic"): 5, ("high", "premium"): 7, ("low", "basic"): "-1/2", ("low", "premium"): -1})
    m = menu(check_screening_menu(d))
    assert m["feasible"] is True and m["ir_violations"] == []
    d["utilities"][2]["utility"] = "1/2"  # low would rather take basic than opt out
    m = menu(check_screening_menu(d))
    assert m["ic_violations"] == [{"type_id": "low", "chosen": "outside", "deviation": "basic",
                                   "chosen_utility": "0", "deviation_utility": "1/2", "gain": "1/2"}]
    d = base(); d["utilities"][2]["utility"] = "2/4"; d["utilities"][0]["utility"] = "1/2"; d["menus"][0]["option_ids"] = ["basic"]
    d["menus"][0]["mapping"] = [{"type_id": "high", "option_id": "basic"}, {"type_id": "low", "option_id": "basic"}]
    d["tie_policy"]["weak_ic"] = True
    assert check_screening_menu(d)["menus"][0]["feasible"] is True


def test_menu_restricts_deviations_to_offered_options():
    d = base(); d["utilities"] = U({("high", "basic"): 5, ("high", "premium"): 7, ("low", "basic"): 2, ("low", "premium"): 3})
    d["menus"][0]["option_ids"] = ["basic", "premium"]
    assert not menu(check_screening_menu(d))["feasible"]
    d["menus"].append({"id": "m2", "option_ids": ["basic"], "source_ref": "s",
                       "mapping": [{"type_id": "high", "option_id": "basic"}, {"type_id": "low", "option_id": "basic"}]})
    r = check_screening_menu(d)
    assert menu(r, "m2")["feasible"] is True  # premium not offered, so no deviation to it
    assert r["feasible_menu_ids"] == ["m2"] and r["selected_menu_id"] == "m2"


def test_no_feasible_menu_and_selection_rule():
    d = base(); d["utilities"] = U({("high", "basic"): 5, ("high", "premium"): 7, ("low", "basic"): 2, ("low", "premium"): 3})
    r = check_screening_menu(d)
    assert r["feasible_menu_ids"] == [] and r["selected_menu_id"] is None and r["no_feasible_menu"] is True
    d = base()
    d["menus"].append({**copy.deepcopy(d["menus"][0]), "id": "a0"})
    r = check_screening_menu(d)
    assert r["feasible_menu_ids"] == ["a0", "m1"] and r["selected_menu_id"] == "a0"
    d["select"] = False
    r = check_screening_menu(d)
    assert r["selected_menu_id"] is None and r["feasible_menu_ids"] == ["a0", "m1"]


def test_no_welfare_or_inference_claims():
    r = check_screening_menu(base())
    assert r["utility_interpretation"] == "declared table values only; not inferred from or claimed about real people"
    assert r["welfare_claim"] is False and r["counterpart_contacted"] is False
    assert any("welfare" in x for x in r["limits"])
    assert not any(k in r for k in ("optimal_menu", "expected_profit", "welfare"))


# ---------- completeness, ids, references ----------
def test_matrix_coverage_exact():
    d = base(); d["utilities"].pop()
    assert msg(d) == "missing utility for low/premium"
    d = base(); d["utilities"].append(dict(d["utilities"][0]))
    assert msg(d) == "duplicate utility for high/basic"
    d = base(); d["utilities"].append({"type_id": "ghost", "option_id": "basic", "utility": 1})
    assert msg(d) == "unknown type id 'ghost' in utilities"
    d = base(); d["utilities"][0]["option_id"] = "ghost"
    assert msg(d) == "unknown option id 'ghost' in utilities"
    d = base(); d["outside_options"].pop()
    assert msg(d) == "missing outside option for type low"
    d = base(); d["outside_options"].append(dict(d["outside_options"][0]))
    assert msg(d) == "duplicate outside option for type high"
    d = base(); d["outside_options"][0]["type_id"] = "ghost"
    assert msg(d) == "unknown type id 'ghost' in outside_options"


def test_ids_duplicates_reserved_and_protected_terms():
    d = base(); d["types"].append({"id": "high", "source_ref": "s"})
    assert msg(d) == "duplicate type id 'high'"
    d = base(); d["options"].append({"id": "basic", "source_ref": "s"})
    assert msg(d) == "duplicate option id 'basic'"
    d = base(); d["options"][0]["id"] = "outside"
    assert msg(d) == "reserved id 'outside' in options"
    for bad in ("bad id", "", "x" * 41, 5, None):
        d = base(); d["types"][0]["id"] = bad
        assert msg(d) == f"invalid id {bad!r} in types"
    for term in ("gender", "race", "religion", "age", "disability"):
        d = base(); d["types"][0]["id"] = f"{term}_group"
        assert msg(d) == f"id '{term}_group' contains protected-trait term '{term}'"
        d = base(); d["options"][0]["id"] = f"opt-{term.upper()}"
        assert msg(d) == f"id 'opt-{term.upper()}' contains protected-trait term '{term}'"
    d = base(); d["types"][0]["id"] = "stage"  # substring of 'age' is fine
    d["utilities"] = [dict(u, type_id="stage") if u["type_id"] == "high" else u for u in d["utilities"]]
    d["outside_options"][0]["type_id"] = "stage"
    d["menus"][0]["mapping"][0]["type_id"] = "stage"
    check_screening_menu(d)


def test_source_refs_required_everywhere():
    for path in (("types", 0), ("options", 1), ("outside_options", 0), ("menus", 0)):
        for bad in ("missing", "  ", 5):
            d = base()
            if bad == "missing":
                del d[path[0]][path[1]]["source_ref"]
            else:
                d[path[0]][path[1]]["source_ref"] = bad
            assert "source_ref must be a non-blank string" in msg(d)
    d = base(); del d["source_ref"]
    assert msg(d) == "source_ref must be a non-blank string"
    d = base(); d["types"][0]["source_ref"] = "x" * 201
    assert "source_ref" in msg(d)


def test_source_trace_sorted_complete_and_override():
    d = base(); d["utilities"][0]["source_ref"] = "own/ref"
    r = check_screening_menu(d)
    tr = r["source_trace"]
    assert tr == sorted(tr, key=lambda t: (t["kind"], t["id"]))
    assert {t["kind"] for t in tr} == {"type", "option", "outside_option", "utility", "menu"}
    assert {"kind": "utility", "id": "high/basic", "source_ref": "own/ref"} in tr
    assert {"kind": "utility", "id": "low/basic", "source_ref": SRC} in tr
    assert len(tr) == 2 + 2 + 2 + 4 + 1


def test_utility_basis_and_tie_policy_explicit():
    d = base(); d["utility_basis"] = "inferred_from_behavior"
    assert msg(d) == "utility_basis must be 'declared_table'"
    d = base(); del d["utility_basis"]
    assert msg(d) == "utility_basis must be 'declared_table'"
    d = base(); del d["tie_policy"]
    assert msg(d) == "tie_policy must be an object"
    d = base(); del d["tie_policy"]["weak_ic"]
    assert msg(d) == "tie_policy.weak_ic must be boolean"
    d = base(); d["tie_policy"]["weak_ir"] = 1
    assert msg(d) == "tie_policy.weak_ir must be boolean"
    d = base(); d["tie_policy"]["extra"] = True
    assert msg(d) == "unknown key 'extra' in tie_policy"
    d = base(); d["select"] = "yes"
    assert msg(d) == "select must be boolean"


def test_menu_and_mapping_validation():
    d = base(); d["menus"] = []
    assert msg(d) == "menus must be a non-empty list"
    d = base(); d["menus"].append(copy.deepcopy(d["menus"][0]))
    assert msg(d) == "duplicate menu id 'm1'"
    d = base(); d["menus"][0]["option_ids"] = []
    assert msg(d) == "menu 'm1' option_ids must be a non-empty list"
    d = base(); d["menus"][0]["option_ids"] = ["basic", "basic"]
    assert msg(d) == "menu 'm1' has duplicate option 'basic'"
    d = base(); d["menus"][0]["option_ids"] = ["ghost"]
    assert msg(d) == "menu 'm1' has unknown option 'ghost'"
    d = base(); d["menus"][0]["mapping"].pop()
    assert msg(d) == "menu 'm1' missing mapping for type low"
    d = base(); d["menus"][0]["mapping"].append({"type_id": "low", "option_id": "basic"})
    assert msg(d) == "menu 'm1' has duplicate mapping for type low"
    d = base(); d["menus"][0]["mapping"][0]["type_id"] = "ghost"
    assert msg(d) == "menu 'm1' maps unknown type 'ghost'"
    d = base(); d["menus"][0]["option_ids"] = ["basic"]
    assert msg(d) == "menu 'm1' maps type high to 'premium', which is not in the menu"
    d = base(); d["menus"][0]["mapping"][0]["option_id"] = "ghost"
    assert msg(d) == "menu 'm1' maps type high to 'ghost', which is not in the menu"


def test_unknown_keys_and_types_refuse():
    for bad in (None, [], "x", 3):
        assert msg(bad) == "request must be an object"
    d = base(); d["target_group"] = "x"
    assert msg(d) == "unknown key 'target_group' in request"
    d = base(); d["types"][0]["trait"] = "x"
    assert msg(d) == "unknown key 'trait' in types"
    d = base(); d["utilities"][0]["weight"] = 1
    assert msg(d) == "unknown key 'weight' in utilities"
    d = base(); d["menus"][0]["mapping"][0]["x"] = 1
    assert msg(d) == "unknown key 'x' in menu 'm1' mapping"
    d = base(); d["types"] = []
    assert msg(d) == "types must be a non-empty list"
    d = base(); d["utilities"] = "x"
    assert msg(d) == "utilities must be a list"
    d = base(); d["types"][0] = "high"
    assert msg(d) == "types entries must be objects"


# ---------- rational bounds ----------
@pytest.mark.parametrize("v,ok", [(10 ** 12, True), (-10 ** 12, True), ("1000000000000", True), ("-1000000000000/1", True),
                                  ("1/1000000", True), (10 ** 12 + 1, False), ("1000000000001", False),
                                  ("1/1000001", False), ("1/0", False), ("0/0", False), ("-1/-2", False), ("1/-2", False)])
def test_rational_bounds_N_and_N_plus_1(v, ok):
    d = base(); d["utilities"][0]["utility"] = v
    if ok:
        check_screening_menu(d)
    else:
        assert "rational" in msg(d)


@pytest.mark.parametrize("v", [1.5, float("nan"), float("inf"), True, False, "0.5", "1e3", " 1", "1 ", "", "a", "1/2/3", None, [1], {"n": 1}, "٣", "+1", "01/2x"])
def test_non_exact_rationals_refuse(v):
    d = base(); d["utilities"][0]["utility"] = v
    assert msg(d) == f"invalid rational {v!r} in utilities"
    d = base(); d["outside_options"][0]["utility"] = v
    assert msg(d) == f"invalid rational {v!r} in outside_options"


def test_rational_exceeding_message_and_normalization():
    d = base(); d["utilities"][0]["utility"] = 10 ** 12 + 1
    assert msg(d) == f"rational {10 ** 12 + 1!r} in utilities exceeds bounds"
    d = base(); d["utilities"][0]["utility"] = "1/1000001"
    assert msg(d) == "rational '1/1000001' in utilities exceeds bounds"
    d = base(); d["utilities"][0]["utility"] = "6/4"; d["menus"][0]["mapping"][0] = {"type_id": "high", "option_id": "basic"}
    d["utilities"][1]["utility"] = "3/2"; d["tie_policy"]["weak_ic"] = True
    m = menu(check_screening_menu(d))
    assert m["ties"][0]["utility"] == "3/2"


# ---------- count bounds ----------
def _wide(nt, no, nm=1):
    d = {"source_ref": SRC, "utility_basis": "declared_table", "tie_policy": {"weak_ic": True, "weak_ir": True},
         "types": [{"id": f"t{i}", "source_ref": "s"} for i in range(nt)],
         "options": [{"id": f"o{j}", "source_ref": "s"} for j in range(no)],
         "outside_options": [{"type_id": f"t{i}", "utility": 0, "source_ref": "s"} for i in range(nt)],
         "utilities": [{"type_id": f"t{i}", "option_id": f"o{j}", "utility": 1} for i in range(nt) for j in range(no)],
         "menus": [{"id": f"m{k}", "option_ids": ["o0"], "source_ref": "s",
                    "mapping": [{"type_id": f"t{i}", "option_id": "o0"} for i in range(nt)]} for k in range(nm)]}
    return d


def test_count_bounds():
    check_screening_menu(_wide(mod.MAX_TYPES, mod.MAX_OPTIONS))
    assert msg(_wide(mod.MAX_TYPES + 1, 2)) == f"types exceed {mod.MAX_TYPES}"
    assert msg(_wide(2, mod.MAX_OPTIONS + 1)) == f"options exceed {mod.MAX_OPTIONS}"
    check_screening_menu(_wide(2, 2, mod.MAX_MENUS))
    assert msg(_wide(2, 2, mod.MAX_MENUS + 1)) == f"menus exceed {mod.MAX_MENUS}"
    assert (mod.MAX_TYPES, mod.MAX_OPTIONS) == (16, 16)


def test_full_size_all_types_all_options_correct():
    r = check_screening_menu(_wide(16, 16))
    m = r["menus"][0]
    assert m["feasible"] is True and m["ties"] == []  # menu offers only o0, so no alternatives to tie with


# ---------- determinism and hygiene ----------
def test_unsorted_input_sorted_output_and_non_mutation():
    d = base(); d["utilities"] = U({("low", "premium"): 3, ("low", "basic"): 2, ("high", "premium"): 7, ("high", "basic"): 8})
    d["types"].reverse(); d["options"].reverse(); d["outside_options"].reverse()
    d["menus"][0]["option_ids"] = ["premium", "basic"]; d["menus"][0]["mapping"].reverse()
    d["menus"].append({**copy.deepcopy(d["menus"][0]), "id": "a1"})
    snap = copy.deepcopy(d)
    r = check_screening_menu(d)
    assert d == snap
    assert [m["id"] for m in r["menus"]] == ["a1", "m1"]
    ics = menu(r)["ic_violations"]
    assert [v["type_id"] for v in ics] == ["high", "low"]
    e = copy.deepcopy(d)
    e["utilities"].reverse(); e["menus"].reverse()
    assert check_screening_menu(e) == r
    r["menus"][0]["id"] = "zz"
    assert d == snap


def test_output_sensitive_to_table():
    a = menu(check_screening_menu(base()))
    d = base(); d["utilities"][3]["utility"] = 9
    b = menu(check_screening_menu(d))
    assert a["feasible"] and not b["feasible"]


# ---------- exhaustive small-table oracle ----------
def _oracle(u, out, menu_opts, mapping, weak_ic, weak_ir):
    """Independent best-response formulation using plain ints."""
    ir, ic = set(), set()
    for t, c in mapping.items():
        uc = out[t] if c == "outside" else u[(t, c)]
        if c != "outside" and not (uc >= out[t] if weak_ir else uc > out[t]):
            ir.add(t)
        for a in menu_opts:
            if a == c:
                continue
            if not (uc >= u[(t, a)] if weak_ic else uc > u[(t, a)]):
                ic.add((t, a))
    return ir, ic


def test_exhaustive_small_table_oracle():
    cases = 0
    types, opts = ["a", "b"], ["x", "y"]
    cells = [(t, o) for t in types for o in opts]
    for uv in itertools.product(range(3), repeat=4):
        u = dict(zip(cells, uv))
        for ov in itertools.product(range(3), repeat=2):
            out = dict(zip(types, ov))
            for menu_opts in (["x"], ["y"], ["x", "y"]):
                for choice in itertools.product(menu_opts + ["outside"], repeat=2):
                    mapping = dict(zip(types, choice))
                    for weak_ic, weak_ir in itertools.product((False, True), repeat=2):
                        d = {"source_ref": "s", "utility_basis": "declared_table",
                             "tie_policy": {"weak_ic": weak_ic, "weak_ir": weak_ir},
                             "types": [{"id": t, "source_ref": "s"} for t in types],
                             "options": [{"id": o, "source_ref": "s"} for o in opts],
                             "outside_options": [{"type_id": t, "utility": out[t], "source_ref": "s"} for t in types],
                             "utilities": [{"type_id": t, "option_id": o, "utility": u[(t, o)]} for (t, o) in cells],
                             "menus": [{"id": "m", "option_ids": menu_opts, "source_ref": "s",
                                        "mapping": [{"type_id": t, "option_id": mapping[t]} for t in types]}]}
                        m = check_screening_menu(d)["menus"][0]
                        ir, ic = _oracle(u, out, menu_opts, mapping, weak_ic, weak_ir)
                        assert {v["type_id"] for v in m["ir_violations"]} == ir, (u, out, menu_opts, mapping, weak_ic, weak_ir)
                        assert {(v["type_id"], v["deviation"]) for v in m["ic_violations"]} == ic, (u, out, menu_opts, mapping, weak_ic, weak_ir)
                        assert m["feasible"] == (not ir and not ic)
                        cases += 1
    assert cases > 30000


def test_exhaustive_ties_listed_regardless_of_policy():
    for weak_ic in (False, True):
        d = base(); d["tie_policy"]["weak_ic"] = weak_ic
        d["utilities"] = U({("high", "basic"): 7, ("high", "premium"): 7, ("low", "basic"): 4, ("low", "premium"): 1})
        m = menu(check_screening_menu(d))
        assert [(t["kind"], t["type_id"], t["alternative"]) for t in m["ties"]] == [("ic", "high", "basic")]
