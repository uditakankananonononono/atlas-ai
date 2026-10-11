import importlib.util, pathlib, sys
from decimal import Decimal
from fractions import Fraction
import pytest

P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/batna92.py"
spec = importlib.util.spec_from_file_location("batna92", P)
m = importlib.util.module_from_spec(spec)
sys.modules["batna92"] = m
spec.loader.exec_module(m)


def o(n, u):
    return {"name": n, "utility": u}


def refuse(opts, code):
    with pytest.raises(m.Batna92Error) as e:
        m.identify_batna(opts)
    assert e.value.code == code
    assert str(e.value).startswith(code + ": ")
    assert code.startswith("BATNA92:")
    return e.value


def test_single_best():
    r = m.identify_batna([o("a", 3), o("b", 5), o("c", 1)])
    assert r.best_names == ("b",) and r.best_utility == 5 and not r.is_tie
    assert [(x.name, x.rank) for x in r.ranking] == [("b", 1), ("a", 2), ("c", 3)]
    assert r.margin_to_next == 2 and r.options_count == 3 and r.version == "1"


def test_exact_tie_input_order_and_competition_rank():
    r = m.identify_batna([o("x", 1), o("a", 7), o("b", 7), o("c", 4), o("d", 4)])
    assert r.best_names == ("a", "b") and r.is_tie
    assert [(x.name, x.rank) for x in r.ranking] == [("a", 1), ("b", 1), ("c", 3), ("d", 3), ("x", 5)]
    assert r.margin_to_next == 3


def test_all_tied_margin_none():
    r = m.identify_batna([o("a", 2), o("b", 2)])
    assert r.is_tie and r.margin_to_next is None and [x.rank for x in r.ranking] == [1, 1]


def test_single_option():
    r = m.identify_batna([o("only", 0)])
    assert r.best_names == ("only",) and r.margin_to_next is None and not r.is_tie


def test_exact_arithmetic_not_float_rounding():
    r = m.identify_batna([o("a", 0.1 + 0.2), o("b", 0.3)])
    assert not r.is_tie and r.best_names == ("a",)
    r2 = m.identify_batna([o("a", Fraction(1, 3)), o("b", Fraction(2, 6))])
    assert r2.is_tie
    r3 = m.identify_batna([o("a", Decimal("0.5")), o("b", 0.5), o("c", 1)])
    assert r3.best_names == ("c",) and r3.ranking[1].rank == 2 and r3.ranking[2].rank == 2


def test_negative_and_zero():
    r = m.identify_batna([o("a", -5), o("b", -1), o("c", 0)])
    assert r.best_names == ("c",) and r.margin_to_next == 1


def test_input_not_mutated_and_tuple_ok():
    opts = (o("a", 1), o("b", 2))
    snap = [dict(x) for x in opts]
    m.identify_batna(opts)
    assert [dict(x) for x in opts] == snap


def test_limits_and_frozen():
    r = m.identify_batna([o("a", 1)])
    assert r.limits == m.LIMITS and len(m.LIMITS) == 5
    with pytest.raises(Exception):
        r.version = "2"
    with pytest.raises(Exception):
        r.ranking[0].rank = 9


def test_to_dict():
    d = m.identify_batna([o("a", Fraction(1, 2)), o("b", 2)]).to_dict()
    assert d["best_names"] == ["b"] and d["best_utility"] == "2"
    assert d["ranking"][1] == {"name": "a", "utility": "1/2", "rank": 2}
    assert d["margin_to_next"] == "3/2" and d["is_tie"] is False
    assert d["limits"] == list(m.LIMITS) and d["options_count"] == 2
    import json; json.dumps(d)
    assert m.identify_batna([o("a", 1)]).to_dict()["margin_to_next"] is None


def test_field_order():
    import dataclasses
    assert [f.name for f in dataclasses.fields(m.BatnaRecord)] == [
        "version", "options_count", "best_names", "best_utility", "is_tie", "ranking", "margin_to_next", "limits"]
    assert [f.name for f in dataclasses.fields(m.RankEntry)] == ["name", "utility", "rank"]


@pytest.mark.parametrize("bad", [None, {}, "ab", 5, {"name": "a", "utility": 1}, iter([o("a", 1)])])
def test_bad_shape(bad):
    refuse(bad, "BATNA92:BAD_SHAPE")


def test_no_options():
    refuse([], "BATNA92:NO_OPTIONS")
    refuse((), "BATNA92:NO_OPTIONS")


@pytest.mark.parametrize("bad", ["a", 1, None, ["name", "a"], {"name": "a", "utility": 1, "extra": 1},
                                 {"utility": 1}, {"name": "", "utility": 1}, {"name": 5, "utility": 1},
                                 {"name": None, "utility": 1}])
def test_bad_option(bad):
    refuse([bad], "BATNA92:BAD_OPTION")


def test_missing_utility():
    refuse([{"name": "a"}], "BATNA92:MISSING_UTILITY")
    refuse([{"name": "a", "utility": None}], "BATNA92:MISSING_UTILITY")
    refuse([o("b", 1), {"name": "a"}], "BATNA92:MISSING_UTILITY")


@pytest.mark.parametrize("u", [True, False, "5", b"5", [1], float("nan"), float("inf"), float("-inf"),
                               Decimal("NaN"), Decimal("Infinity"), 1j, object()])
def test_uncomparable(u):
    refuse([o("a", u)], "BATNA92:UNCOMPARABLE")


def test_duplicate_name_exact_only():
    refuse([o("a", 1), o("a", 2)], "BATNA92:DUPLICATE_NAME")
    m.identify_batna([o("a", 1), o("A", 2), o("a ", 3)])


def test_check_order():
    refuse([o("a", 1), o("a", 2), {"name": "z"}], "BATNA92:MISSING_UTILITY")
    refuse([o("a", float("nan")), {"name": "z"}], "BATNA92:UNCOMPARABLE")
    refuse([{"name": "", "utility": None}], "BATNA92:BAD_OPTION")
    refuse([{"name": "a", "utility": True}, {"name": "b"}], "BATNA92:UNCOMPARABLE")


def test_error_attrs():
    e = refuse([{"name": "a"}], "BATNA92:MISSING_UTILITY")
    assert isinstance(e, ValueError) and e.detail and str(e) == e.code + ": " + e.detail


def test_version_constant():
    assert m.BATNA92_VERSION == "1"


def test_module_stdlib_only_and_no_io():
    src = P.read_text()
    import re
    mods = set(re.findall(r"^(?:from|import)\s+([A-Za-z_][\w]*)", src, re.M))
    assert mods <= {"__future__", "dataclasses", "decimal", "fractions", "math", "numbers", "typing", "collections"}
    for bad in ("open(", "socket", "subprocess", "requests", "os.environ"):
        assert bad not in src
