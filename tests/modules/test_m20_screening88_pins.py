"""Row88 screening-menu pins (test-only; runtime frozen).

Loads the module by file path so no package import (and no app dependencies) is needed.
Pins: string '7' is rational 7, MAX_MENUS 64/65, MAX_SOURCE_REF 200/201, omitted
`select` gives selected_menu_id None, exact options[] message, exact (later)
outside_options[] refusal message and its position in the validation order.
The int-branch `den = 1` in _rat is a dead assignment (equivalent), so it is not pinned.
"""
import copy
import importlib.util
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/screening_menu88.py"
_spec = importlib.util.spec_from_file_location("screening_menu88_pins_under_test", _SRC)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)
check = mod.check_screening_menu


def base():
    return {
        "source_ref": "declared/table-1",
        "utility_basis": "declared_table",
        "tie_policy": {"weak_ic": False, "weak_ir": False},
        "types": [{"id": "low", "source_ref": "s/t2"}, {"id": "high", "source_ref": "s/t1"}],
        "options": [{"id": "basic", "source_ref": "s/o1"}, {"id": "premium", "source_ref": "s/o2"}],
        "outside_options": [{"type_id": "high", "utility": 0, "source_ref": "s/x1"},
                            {"type_id": "low", "utility": 0, "source_ref": "s/x2"}],
        "utilities": [
            {"type_id": "high", "option_id": "basic", "utility": 5},
            {"type_id": "high", "option_id": "premium", "utility": 7},
            {"type_id": "low", "option_id": "basic", "utility": 4},
            {"type_id": "low", "option_id": "premium", "utility": 1},
        ],
        "menus": [{"id": "m1", "option_ids": ["basic", "premium"], "source_ref": "s/m1",
                   "mapping": [{"type_id": "high", "option_id": "premium"},
                               {"type_id": "low", "option_id": "basic"}]}],
        "select": True,
    }


def err(d):
    with pytest.raises(ValueError) as e:
        check(d)
    return str(e.value)


def util(d, t, o, v):
    for r in d["utilities"]:
        if r["type_id"] == t and r["option_id"] == o:
            r["utility"] = v
            return
    raise AssertionError("no such utility row")


# ---- group 1: the string '7' is rational 7 (denominator defaults to 1) ----

def test_string_seven_is_exactly_seven():
    d = base()
    d["outside_options"][0]["utility"] = "7"
    util(d, "high", "premium", "-7")
    r = check(d)["menus"][0]
    v = [x for x in r["ir_violations"] if x["type_id"] == "high"]
    assert v == [{"type_id": "high", "chosen": "premium", "chosen_utility": "-7",
                  "outside_utility": "7", "shortfall": "14"}]


def test_string_seven_equals_other_spellings_of_seven():
    d = base()
    d["tie_policy"]["weak_ir"] = True
    d["outside_options"][0]["utility"] = "14/2"
    util(d, "high", "premium", "7")
    r = check(d)["menus"][0]
    ties = [t for t in r["ties"] if t["kind"] == "ir" and t["type_id"] == "high"]
    assert ties == [{"kind": "ir", "type_id": "high", "chosen": "premium", "alternative": "outside",
                     "utility": "7", "accepted_as_weak": True}]
    d2 = base()
    d2["outside_options"][0]["utility"] = "7/1"
    util(d2, "high", "premium", "7")
    t2 = [t for t in check(d2)["menus"][0]["ties"] if t["kind"] == "ir"]
    assert [t["utility"] for t in t2] == ["7"]


def test_string_seven_is_not_seven_halves():
    d = base()
    d["outside_options"][0]["utility"] = "7"
    util(d, "high", "premium", "7/2")
    r = check(d)["menus"][0]
    v = [x for x in r["ir_violations"] if x["type_id"] == "high"]
    assert v[0]["chosen_utility"] == "7/2" and v[0]["outside_utility"] == "7" and v[0]["shortfall"] == "7/2"


# ---- group 2: MAX_MENUS 64 accepted, 65 refused ----

def _menus(n):
    d = base()
    d["menus"] = [{"id": f"m{i:03d}", "option_ids": ["basic", "premium"], "source_ref": "s/m",
                   "mapping": [{"type_id": "high", "option_id": "premium"},
                               {"type_id": "low", "option_id": "basic"}]} for i in range(n)]
    return d


def test_max_menus_literal_64_accept_65_refuse():
    assert mod.MAX_MENUS == 64
    r = check(_menus(64))
    assert len(r["menus"]) == 64 and r["selected_menu_id"] == "m000"
    assert err(_menus(65)) == "menus exceed 64"


# ---- group 3: MAX_SOURCE_REF 200 accepted, 201 refused ----

def test_max_source_ref_literal_200_accept_201_refuse():
    assert mod.MAX_SOURCE_REF == 200
    d = base()
    d["source_ref"] = "a" * 200
    assert check(d)["selected_menu_id"] == "m1"
    d["source_ref"] = "a" * 201
    assert err(d) == "source_ref exceeds 200 characters"


def test_max_source_ref_labelled_records():
    d = base()
    d["types"][1]["source_ref"] = "a" * 200
    d["menus"][0]["source_ref"] = "b" * 200
    check(d)
    d["types"][1]["source_ref"] = "a" * 201
    assert err(d) == "type 'high' source_ref exceeds 200 characters"
    d = base()
    d["menus"][0]["source_ref"] = "b" * 201
    assert err(d) == "menu 'm1' source_ref exceeds 200 characters"


# ---- group 4: omitted select gives selected_menu_id None ----

def test_select_omitted_gives_none_but_lists_feasible():
    d = base()
    del d["select"]
    r = check(d)
    assert r["selected_menu_id"] is None
    assert r["feasible_menu_ids"] == ["m1"] and r["no_feasible_menu"] is False
    d["select"] = False
    assert check(d)["selected_menu_id"] is None
    d["select"] = True
    assert check(d)["selected_menu_id"] == "m1"
    d["select"] = 1
    assert err(d) == "select must be boolean"


# ---- group 5: options[] exact message ----

@pytest.mark.parametrize("bad", ["missing", [], None, "x", {"id": "a"}])
def test_options_must_be_non_empty_list_exact(bad):
    d = base()
    if bad == "missing":
        del d["options"]
    else:
        d["options"] = bad
    assert err(d) == "options must be a non-empty list"


# ---- group 6: outside_options[] 'missing outside option' (a later refusal) ----

def test_missing_outside_option_exact_and_sorted_first():
    d = base()
    d["outside_options"] = []
    assert err(d) == "missing outside option for type high"  # types are given low,high; sorted -> high
    d = base()
    del d["outside_options"][0]
    assert err(d) == "missing outside option for type high"
    d = base()
    del d["outside_options"][1]
    assert err(d) == "missing outside option for type low"


def test_missing_outside_option_precedes_utilities_and_menus_checks():
    d = base()
    del d["outside_options"][0]
    d["utilities"] = "garbage"
    d["menus"] = "garbage"
    assert err(d) == "missing outside option for type high"
    d = base()
    del d["outside_options"][0]
    del d["utilities"]
    del d["menus"]
    assert err(d) == "missing outside option for type high"


def test_missing_outside_option_follows_earlier_validation():
    d = base()
    del d["outside_options"][0]
    d["options"][0]["id"] = "bad id"
    assert err(d) == "invalid id 'bad id' in options"
    d = base()
    del d["outside_options"][0]
    d["outside_options"][0]["type_id"] = "nope"
    assert err(d) == "unknown type id 'nope' in outside_options"
    d = base()
    del d["outside_options"][0]
    d["outside_options"][0]["utility"] = 1.5
    assert err(d) == "invalid rational 1.5 in outside_options"


def test_outside_options_must_be_a_list_but_may_be_empty_until_checked():
    d = base()
    d["outside_options"] = "x"
    assert err(d) == "outside_options must be a list"
    d = base()
    del d["outside_options"]
    assert err(d) == "outside_options must be a list"


def test_pins_do_not_mutate_input():
    d = base()
    before = copy.deepcopy(d)
    check(d)
    assert d == before
