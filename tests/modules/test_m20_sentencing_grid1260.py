"""Row 1260 (title only: "Sentencing Guidelines") caller-declared grid lookup.

The grid in these tests is INVENTED for the tests. It is not any real guideline table, and
nothing here says what a real sentence would be.
"""
import copy

import pytest

from app.modules.m20_general_cognitive_worker.sentencing_grid1260 import (
    DISCLAIMER,
    SentencingGrid,
    SentencingGridError,
)

DECL = {
    "name": "Invented test grid",
    "edition": "test-edition-1",
    "source": "caller-supplied: invented for tests",
    "unit": "months",
    "levels": [1, 2, 3, 4],
    "categories": ["A", "B", "C"],
    "cells": {
        "1": {"A": [0, 6], "B": [0, 6], "C": [1, 7]},
        "2": {"A": [0, 6], "B": [1, 7], "C": [2, 8]},
        "3": {"A": [2, 8], "B": [3, 9], "C": [4, 10]},
        "4": {"A": [4, 10], "B": [6, 12]},
    },
    "offense_adjustments": {"weapon": 2, "minor_role": -1},
    "offender_adjustments": {"acceptance": -1},
}


def grid(**over):
    d = copy.deepcopy(DECL)
    d.update(over)
    return SentencingGrid(d)


def refusal(fn, *a, **kw):
    with pytest.raises(SentencingGridError) as ei:
        fn(*a, **kw)
    assert str(ei.value).startswith("SENT1260: ")
    return str(ei.value)


# --- lookup ----------------------------------------------------------------------------------
def test_plain_lookup_returns_the_declared_cell_range_and_the_inputs():
    r = grid().lookup(3, "B")
    assert r["range"] == {"min": 3, "max": 9, "unit": "months"}
    assert (r["base_level"], r["adjusted_level"], r["category"]) == (3, 3, "B")
    assert r["applied_adjustments"] == []
    assert r["grid"] == {"name": "Invented test grid", "edition": "test-edition-1",
                         "source": "caller-supplied: invented for tests"}
    assert r["disclaimer"] == DISCLAIMER


def test_every_declared_cell_round_trips():
    g = grid()
    for level, row in DECL["cells"].items():
        for cat, (lo, hi) in row.items():
            r = g.lookup(int(level), cat)
            assert (r["range"]["min"], r["range"]["max"]) == (lo, hi)


def test_adjustments_are_summed_arithmetically_and_recorded_in_order():
    r = grid().lookup(2, "A", offense=["weapon"], offender=["acceptance"])
    assert r["adjusted_level"] == 3
    assert r["range"]["min"] == 2 and r["range"]["max"] == 8
    assert r["applied_adjustments"] == [
        {"kind": "offense", "name": "weapon", "delta": 2},
        {"kind": "offender", "name": "acceptance", "delta": -1},
    ]


def test_negative_total_adjustment_lowers_the_level():
    assert grid().lookup(3, "C", offense=["minor_role"])["adjusted_level"] == 2


def test_lookup_does_not_change_the_declaration_or_prior_results():
    g = grid()
    first = g.lookup(2, "B")
    g.lookup(1, "B", offense=["weapon"])
    assert g.lookup(2, "B") == first


# --- refusals: exact row-prefixed messages ---------------------------------------------------------------
def test_adjusted_level_above_the_grid_is_refused_not_clamped():
    assert refusal(grid().lookup, 3, "A", offense=["weapon"]) == \
        "SENT1260: adjusted level 5 is outside the declared grid levels 1..4"


def test_adjusted_level_below_the_grid_is_refused_not_clamped():
    assert refusal(grid().lookup, 1, "A", offense=["minor_role"]) == \
        "SENT1260: adjusted level 0 is outside the declared grid levels 1..4"


def test_missing_cell_is_refused_and_not_inferred():
    assert refusal(grid().lookup, 4, "C") == "SENT1260: no declared cell for level 4, category 'C'"


def test_unknown_category_is_refused():
    assert refusal(grid().lookup, 2, "Z") == "SENT1260: unknown category 'Z'; declared: ['A', 'B', 'C']"


def test_unknown_adjustment_names_are_refused():
    assert refusal(grid().lookup, 2, "A", offense=["nope"]) == "SENT1260: unknown offense adjustment 'nope'"
    assert refusal(grid().lookup, 2, "A", offender=["nope"]) == "SENT1260: unknown offender adjustment 'nope'"
    assert refusal(grid().lookup, 2, "A", offense=["acceptance"]) == "SENT1260: unknown offense adjustment 'acceptance'"


def test_same_adjustment_twice_is_refused():
    assert refusal(grid().lookup, 3, "A", offense=["weapon", "weapon"]) == \
        "SENT1260: offense adjustment 'weapon' listed more than once"


@pytest.mark.parametrize("level", [True, False, 2.0, "2", None, [2]])
def test_base_level_must_be_a_real_integer(level):
    assert refusal(grid().lookup, level, "A") == "SENT1260: base_level must be an integer"


def test_adjustment_arguments_must_be_lists_of_strings():
    assert refusal(grid().lookup, 2, "A", offense="weapon") == "SENT1260: offense must be a list of names"
    assert refusal(grid().lookup, 2, "A", offender=[1]) == "SENT1260: offender must be a list of names"


def test_category_must_be_a_string():
    assert refusal(grid().lookup, 2, 5) == "SENT1260: category must be a string"


# --- declaration validation --------------------------------------------------------------------------------
def bad(**over):
    d = copy.deepcopy(DECL)
    for k, v in over.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    with pytest.raises(SentencingGridError) as ei:
        SentencingGrid(d)
    assert str(ei.value).startswith("SENT1260: ")
    return str(ei.value)


def test_declaration_must_be_an_object_with_exactly_the_known_keys():
    with pytest.raises(SentencingGridError) as ei:
        SentencingGrid([])
    assert str(ei.value) == "SENT1260: declaration must be an object"
    assert bad(extra=1) == "SENT1260: unknown declaration key(s) ['extra']"


@pytest.mark.parametrize("key", ["name", "edition", "source", "unit", "levels", "categories", "cells"])
def test_each_required_key_is_required(key):
    assert bad(**{key: None}) == f"SENT1260: declaration key '{key}' is required"


@pytest.mark.parametrize("key", ["name", "edition", "source", "unit"])
def test_text_keys_must_be_non_blank_strings(key):
    assert bad(**{key: "  "}) == f"SENT1260: '{key}' must be a non-blank string"


def test_levels_must_be_strictly_ascending_unique_integers():
    msg = "SENT1260: levels must be a non-empty strictly ascending list of integers"
    assert bad(levels=[]) == msg
    assert bad(levels=[2, 1]) == msg
    assert bad(levels=[1, 1]) == msg
    assert bad(levels=[1, True]) == msg
    assert bad(levels=[1.0, 2]) == msg


def test_levels_must_be_contiguous():
    assert bad(levels=[1, 2, 4]) == "SENT1260: levels must be contiguous (no gaps)"


def test_categories_must_be_unique_non_blank_strings():
    msg = "SENT1260: categories must be a non-empty list of unique non-blank strings"
    assert bad(categories=[]) == msg
    assert bad(categories=["A", "A"]) == msg
    assert bad(categories=["A", ""]) == msg


def test_cells_must_not_reference_undeclared_levels_or_categories():
    c = copy.deepcopy(DECL["cells"])
    c["9"] = {"A": [0, 1]}
    assert bad(cells=c) == "SENT1260: cell level '9' is not a declared level"
    c = copy.deepcopy(DECL["cells"])
    c["1"]["Q"] = [0, 1]
    assert bad(cells=c) == "SENT1260: cell category 'Q' at level '1' is not a declared category"


@pytest.mark.parametrize("cell", [[1], [1, 2, 3], "1-2", [True, 2], [1, 2.5], [-1, 2], [5, 4]])
def test_each_cell_must_be_a_non_negative_min_max_pair_with_min_not_above_max(cell):
    c = copy.deepcopy(DECL["cells"])
    c["1"]["A"] = cell
    assert bad(cells=c) == "SENT1260: cell level 1, category 'A' must be [min, max] non-negative integers with min <= max"


def test_equal_min_and_max_is_allowed():
    c = copy.deepcopy(DECL["cells"])
    c["1"]["A"] = [5, 5]
    assert SentencingGrid({**DECL, "cells": c}).lookup(1, "A")["range"] == {"min": 5, "max": 5, "unit": "months"}


def test_adjustment_tables_are_validated():
    assert bad(offense_adjustments={"x": 1.5}) == "SENT1260: offense adjustment 'x' must be an integer delta"
    assert bad(offender_adjustments={"x": True}) == "SENT1260: offender adjustment 'x' must be an integer delta"
    assert bad(offense_adjustments={"": 1}) == "SENT1260: offense adjustment names must be non-blank strings"
    assert bad(offense_adjustments=[]) == "SENT1260: offense_adjustments must be an object"


def test_adjustment_tables_are_optional_and_default_to_empty():
    d = copy.deepcopy(DECL)
    d.pop("offense_adjustments"); d.pop("offender_adjustments")
    assert SentencingGrid(d).lookup(2, "A")["applied_adjustments"] == []
    assert refusal(SentencingGrid(d).lookup, 2, "A", offense=["weapon"]) == "SENT1260: unknown offense adjustment 'weapon'"


def test_the_declaration_is_never_copied_and_later_caller_edits_do_not_change_the_grid():
    d = copy.deepcopy(DECL)
    g = SentencingGrid(d)
    d["cells"]["1"]["A"] = [99, 99]
    d["offense_adjustments"]["weapon"] = 50
    d["levels"].append(5)
    d["categories"].append("ZZ")
    assert g.lookup(1, "A")["range"]["max"] == 6
    assert g.lookup(1, "A", offense=["weapon"])["adjusted_level"] == 3
    assert refusal(g.lookup, 1, "ZZ").startswith("SENT1260: unknown category 'ZZ'")
    # the appended level 5 must not enter the grid's bounds (levels alias mutant)
    assert refusal(g.lookup, 3, "A", offense=["weapon"]) == \
        "SENT1260: adjusted level 5 is outside the declared grid levels 1..4"


# --- boundary wording ---------------------------------------------------------------------------------------
def test_disclaimer_states_the_limits():
    assert DISCLAIMER == ("SENT1260: arithmetic lookup in a caller-declared table for counsel review; "
                          "not legal advice, not a sentence, not a prediction, and not verified against any real guideline.")


def test_module_is_hermetic_standard_library_only():
    import ast, inspect
    import app.modules.m20_general_cognitive_worker.sentencing_grid1260 as m
    tree = ast.parse(inspect.getsource(m))
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            names.add((n.module or "").split(".")[0])
    assert names <= {"__future__", "typing", "unicodedata"}


@pytest.mark.parametrize("key", ["01", "+1", " 1", "1.0", "x"])
def test_cell_level_keys_must_be_the_canonical_decimal_string_of_a_declared_level(key):
    c = copy.deepcopy(DECL["cells"])
    c[key] = c.pop("1")
    assert bad(cells=c) == f"SENT1260: cell level '{key}' is not a declared level"


# --- size-cap pins (auditor-2 repair 1) ------------------------------------------------------------------
def test_levels_cap_64_accepted_65_refused():
    assert SentencingGrid({**DECL, "levels": list(range(1, 65))})
    assert bad(levels=list(range(1, 66))) == "SENT1260: levels must have at most 64 entries"


def test_categories_cap_64_accepted_65_refused():
    assert SentencingGrid({**DECL, "categories": [f"c{i}" for i in range(64)], "cells": {}})
    assert bad(categories=[f"c{i}" for i in range(65)]) == "SENT1260: categories must have at most 64 entries"


def test_cells_row_cap_64_accepted_65_refused():
    cells = {str(i): {} for i in range(1, 65)}
    assert SentencingGrid({**DECL, "levels": list(range(1, 65)), "cells": cells})
    cells65 = {str(i): {} for i in range(1, 66)}
    assert bad(levels=list(range(1, 65)), cells=cells65) == "SENT1260: cells must have at most 64 rows"


def test_cell_row_entry_cap_64_accepted_65_refused():
    cats = [f"c{i}" for i in range(64)]
    row64 = {c: [0, 1] for c in cats}
    assert SentencingGrid({**DECL, "categories": cats, "cells": {"1": row64}})
    assert bad(categories=cats, cells={"1": dict(row64, extra=[0, 1])}) == \
        "SENT1260: cell row for level '1' must have at most 64 entries"


def test_adjustments_cap_64_accepted_65_refused_per_kind():
    adj = {f"a{i}": 1 for i in range(64)}
    assert SentencingGrid({**DECL, "offense_adjustments": adj, "offender_adjustments": adj})
    assert bad(offense_adjustments={f"a{i}": 1 for i in range(65)}) == \
        "SENT1260: offense_adjustments must have at most 64 entries"
    assert bad(offender_adjustments={f"a{i}": 1 for i in range(65)}) == \
        "SENT1260: offender_adjustments must have at most 64 entries"


@pytest.mark.parametrize("key", ["name", "edition", "source", "unit"])
def test_text_fields_cap_256_accepted_257_refused(key):
    assert SentencingGrid({**DECL, key: "x" * 256})
    assert bad(**{key: "x" * 257}) == f"SENT1260: '{key}' must be at most 256 characters"


def test_category_names_cap_64_accepted_65_refused():
    assert SentencingGrid({**DECL, "categories": ["A" * 64], "cells": {}})
    assert bad(categories=["A" * 65]) == "SENT1260: category names must be at most 64 characters"


def test_adjustment_names_cap_64_accepted_65_refused():
    assert SentencingGrid({**DECL, "offense_adjustments": {"a" * 64: 1}})
    assert bad(offense_adjustments={"a" * 65: 1}) == "SENT1260: offense adjustment names must be at most 64 characters"
    assert bad(offender_adjustments={"b" * 65: 1}) == "SENT1260: offender adjustment names must be at most 64 characters"


# --- type-policy pins (auditor-2 repair 2) ---------------------------------------------------------------
def test_dict_subclasses_are_refused():
    class D(dict):
        pass
    with pytest.raises(SentencingGridError) as ei:
        SentencingGrid(D(DECL))
    assert str(ei.value) == "SENT1260: declaration must be an object"
    assert bad(cells=D(DECL["cells"])) == "SENT1260: cells must be an object"
    assert bad(cells={"1": D({"A": [0, 6]})}) == "SENT1260: cell row for level '1' must be an object"
    assert bad(offense_adjustments=D({"weapon": 2})) == "SENT1260: offense_adjustments must be an object"
    assert bad(offender_adjustments=D({"acceptance": -1})) == "SENT1260: offender_adjustments must be an object"


def test_unicode_control_format_and_separator_characters_are_refused():
    zw, line, para, bell = "\u200b", "\u2028", "\u2029", "\u0007"
    msg = "contains a disallowed character (Cc, Cf, Zl or Zp)"
    assert bad(name="grid" + zw) == f"SENT1260: 'name' {msg}"
    assert bad(edition="e" + line) == f"SENT1260: 'edition' {msg}"
    assert bad(source="s" + para) == f"SENT1260: 'source' {msg}"
    assert bad(unit="mo" + bell) == f"SENT1260: 'unit' {msg}"
    assert bad(categories=["A" + zw], cells={}) == "SENT1260: category names contain a disallowed character (Cc, Cf, Zl or Zp)"
    assert bad(offense_adjustments={"x" + zw: 1}) == "SENT1260: offense adjustment names contain a disallowed character (Cc, Cf, Zl or Zp)"
    assert bad(offender_adjustments={"y" + para: 1}) == "SENT1260: offender adjustment names contain a disallowed character (Cc, Cf, Zl or Zp)"
    assert SentencingGrid({**DECL, "name": "plain grid name"})   # ordinary spaces (Zs) are accepted
