"""Row 109 Libertarian Paternalism: hermetic stdlib tests, N/N+1 pins, row-tagged refusals. Loads the module by path."""
import importlib.util
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/libertarian_paternalism109.py"
_spec = importlib.util.spec_from_file_location("libertarian_paternalism109", _SRC)
lp = importlib.util.module_from_spec(_spec)
sys.modules["libertarian_paternalism109"] = lp
_spec.loader.exec_module(lp)


def base(**over):
    d = {"options": ["a", "b", "c"], "default": "a", "easy_opt_out": True, "transparent": True,
         "alternatives_visible": True, "expected_utilities": {"a": "1.5", "b": 3, "c": 3},
         "population_shares": {"a": "0.5", "b": "0.25", "c": "0.25"}}
    d.update(over)
    return d


def go(**over):
    return lp.review(base(**over))


def refused(data, word):
    with pytest.raises(lp.LibertarianError) as e:
        lp.review(data)
    msg = str(e.value)
    assert msg.startswith("LIBPAT109: ") and word in msg
    return msg


def two(u=None, s=None, **over):
    d = base(options=["x", "y"], default="x", expected_utilities=u or {"x": 1, "y": 1},
             population_shares=s or {"x": "0.5", "y": "0.5"})
    d.update(over)
    return d


def test_hand_computed_three_options_with_tie():
    # welfare = .5*1.5 + .25*3 + .25*3 = 2.25 = 9/4; best = 3 (b and c tie); regret of default a = 3 - 1.5 = 3/2
    r = go()
    assert r["row"] == 109 and r["expected_population_welfare"] == "9/4"
    assert r["expected_population_welfare_decimal"] == "2.250000"
    assert r["default_regret"] == "3/2" and r["default_regret_decimal"] == "1.500000"
    assert r["utility_maximizing_options"] == ["b", "c"]
    assert r["autonomy_preserved"] is True and r["deployment_allowed"] is False
    assert "interval" not in " ".join(r)


def test_default_is_tie_member_regret_zero():
    r = go(default="c")
    assert r["default_regret"] == "0/1" and r["default_regret_decimal"] == "0.000000"
    assert r["deployment_allowed"] is True and r["utility_maximizing_options"] == ["b", "c"]
    assert go(default="b")["deployment_allowed"] is True


def test_ties_sorted_regardless_of_option_order():
    r = go(options=["c", "b", "a"], default="c")
    assert r["utility_maximizing_options"] == ["b", "c"] and r["options"] == ["c", "b", "a"]


def test_each_autonomy_flag_blocks_deployment():
    for k in ("easy_opt_out", "transparent", "alternatives_visible"):
        r = go(default="c", **{k: False})
        assert r["autonomy_preserved"] is False and r["deployment_allowed"] is False
    r = go(default="c", easy_opt_out=False, transparent=False, alternatives_visible=False)
    assert r["autonomy_preserved"] is False


def test_regret_positive_blocks_even_with_autonomy():
    r = go()
    assert r["autonomy_preserved"] is True and r["deployment_allowed"] is False


def test_shares_sum_exactly_one():
    assert lp.review(two(s={"x": "0.5", "y": "0.5"}))["expected_population_welfare"] == "1/1"
    refused(two(s={"x": "0.3", "y": "0.3"}), "population_shares")
    refused(two(s={"x": "0.5", "y": "0.500001"}), "population_shares")
    refused(two(s={"x": "0.499999", "y": "0.5"}), "population_shares")
    assert lp.review(two(s={"x": "0.500001", "y": "0.499999"}))
    assert lp.review(two(s={"x": 1, "y": 0}))["expected_population_welfare"] == "1/1"
    assert lp.review(two(s={"x": 0, "y": "1"}))
    assert lp.review(two(s={"x": "1.0", "y": "0.000000"}))


def test_thirds_six_decimals_sum_refused():
    d = base(population_shares={"a": "0.333333", "b": "0.333333", "c": "0.333333"})
    refused(d, "population_shares")
    d = base(population_shares={"a": "0.333333", "b": "0.333333", "c": "0.333334"})
    assert lp.review(d)["row"] == 109


def test_share_values_grammar():
    # each bad value is paired with a partner that would make the sum exactly 1 if the value were accepted
    cases = [("1/3", "0"), ("-0.5", "1.5"), ("1.5", "-0.5"), ("2", "-1"), ("0.1234567", "0.8765433"), (".5", "0.5"),
             ("1.", "0"), ("0.5 ", "0.5"), (" 0.5", "0.5"), ("0.5\n", "0.5"), ("nan", "0"), ("inf", "0"), ("1e-1", "0.9"),
             ("", "1"), (0.5, "0.5"), (1.0, "0"), (True, "0"), (False, "1"), (None, "1"), (2, -1), (-1, 2), ([0.5], "0.5"),
             ("\uff10.5", "0.5"), ("0.5", ".5"), ("1", 0.0), ("0.5", True)]
    for bad, partner in cases:
        refused(two(s={"x": bad, "y": partner}), "population_shares")
        refused(two(s={"x": partner, "y": bad}), "population_shares")
    assert lp.review(two(s={"x": "0", "y": "1"}))


def test_single_option_refused_even_when_otherwise_valid():
    d = base(options=["x"], default="x", expected_utilities={"x": 1}, population_shares={"x": 1})
    m = refused(d, "list of 2 to 20")
    assert "default" not in m


def test_utility_grammar():
    for bad in (1.0, 0.5, True, False, None, "nan", "inf", "-inf", "1e3", "1/2", ".5", "5.", "1.1234567", "1234567890123",
               "+1", " 1", "1\n", "", "-", "--1", 10**12 + 1, -10**12 - 1, [1], "１"):
        refused(two(u={"x": bad, "y": 1}), "expected_utilities")
    assert lp.review(two(u={"x": 10**12, "y": -10**12}))["default_regret"] == "0/1"
    assert lp.review(two(u={"x": "999999999999.999999", "y": "-999999999999.999999"}))
    assert lp.review(two(u={"x": "-0", "y": "0.0"}))["default_regret"] == "0/1"
    assert lp.review(two(u={"x": "-1.5", "y": "2"}))["default_regret"] == "7/2"


def test_decimal_rounding_half_even():
    # welfare = 1/3*... build exact halves: shares .5/.5, utilities 0.000001 and 0 -> welfare 0.0000005 -> 0.000000
    r = lp.review(two(u={"x": "0.000001", "y": "0"}))
    assert r["expected_population_welfare"] == "1/2000000" and r["expected_population_welfare_decimal"] == "0.000000"
    r = lp.review(two(u={"x": "0.000003", "y": "0"}))
    assert r["expected_population_welfare_decimal"] == "0.000002"      # 0.0000015 -> even
    r = lp.review(two(u={"x": "-0.000003", "y": "0"}))
    assert r["expected_population_welfare_decimal"] == "-0.000002"
    r = lp.review(two(u={"x": "-0.000001", "y": "0"}))
    assert r["expected_population_welfare_decimal"] == "0.000000"      # no minus sign on zero
    r = lp.review(two(u={"x": "0", "y": "0.333333"}))
    assert r["default_regret"] == "333333/1000000" and r["default_regret_decimal"] == "0.333333"


def test_option_rules():
    for bad in (["a"], [], ["a"] * 21, None, "ab", ("a", "b"), {"a": 1, "b": 2}):
        refused(two(options=bad), "options")
    opts = ["o%d" % i for i in range(20)]
    d = base(options=opts, default="o0", expected_utilities={o: 1 for o in opts}, population_shares={**{o: 0 for o in opts[1:]}, "o0": 1})
    assert len(lp.review(d)["options"]) == 20
    refused(dict(d, options=opts + ["o20"]), "options")


def test_unhashable_option_refused_not_raised():
    for bad in ([["a"], "b"], [{"a": 1}, "b"], ["a", ["b"]], [{"a"}, "b"] if False else [["x"], ["x"]]):
        refused(two(options=bad), "options")


def test_duplicate_and_bad_option_text():
    refused(two(options=["a", "a"]), "unique")
    assert lp.review(two(options=["a", "A"], default="a", expected_utilities={"a": 1, "A": 1},
                         population_shares={"a": "0.5", "A": "0.5"}))
    for bad in ("", "  ", 5, None, True, b"a", "a\x00", "a\n", "a\u200b", "a\u2028", "a\u202e", "a" * 101):
        refused(two(options=["x", bad]), "options")
    assert lp.review(base(options=["a" * 100, "b"], default="b", expected_utilities={"a" * 100: 1, "b": 1},
                          population_shares={"a" * 100: "0.5", "b": "0.5"}))
    m = refused(two(options=["x", "\x00" * 101]), "longer than 100")
    assert "control" not in m

    class S(str):
        pass
    refused(two(options=[S("x"), "y"]), "options")


def test_default_rules():
    for bad in ("z", None, 5, ["a"], True, "A"):
        refused(base(default=bad), "default")


def test_per_option_dict_shapes():
    for k in ("expected_utilities", "population_shares"):
        good = base()[k]
        missing = dict(good)
        del missing["c"]
        refused(base(**{k: missing}), k)
        refused(base(**{k: dict(good, d=1)}), k)
        swapped = dict(good)
        del swapped["c"]
        swapped["z"] = good["c"]
        refused(base(**{k: swapped}), k)
        refused(base(**{k: {1: 1, 2: 2, 3: 3}}), k)
        refused(base(**{k: list(good.items())}), k)
        refused(base(**{k: None}), k)
        big = {("k%d" % i): 1 for i in range(1000)}
        m = refused(base(**{k: big}), "exactly one entry per option")


def test_dict_size_checked_before_iteration():
    class D(dict):
        touched = 0

        def __iter__(self):
            D.touched += 1
            return dict.__iter__(self)

        def __len__(self):
            D.touched += 1
            return 3
    refused(base(expected_utilities=D({"a": 1, "b": 1, "c": 1})), "expected_utilities")
    assert D.touched == 0
    m = refused(base(expected_utilities={("k%d" % i): "bad" for i in range(100)}), "exactly one entry")
    assert "plain decimal" not in m


def test_flags_exact_bool():
    for k in ("easy_opt_out", "transparent", "alternatives_visible"):
        for bad in (1, 0, "true", None, [], 1.0):
            refused(base(**{k: bad}), k)
        d = base()
        del d[k]
        refused(d, k + " required")


def test_keys():
    d = base()
    for i in range(50):
        d["k%d" % i] = 1
    m = refused(d, "too many keys")
    assert "unknown" not in m
    refused({k: v for k, v in dict(base(), extra=1).items() if k != "default"}, "unknown key")
    refused({k: v for k, v in dict(base(), **{"": 1}).items() if k != "default"}, "unknown key")
    for bad in (None, [], "x", 5):
        refused(bad, "mapping")
    for k in ("options", "default", "expected_utilities", "population_shares"):
        d = base()
        del d[k]
        refused(d, k + " required")

    class D(dict):
        touched = 0

        def __len__(self):
            D.touched += 1
            return 1
    refused(D(base()), "mapping")
    assert D.touched == 0


def test_no_value_in_refusal():
    secret = "ZZSECRET9"
    cases = [two(options=["x", secret * 30]), two(options=[["x", secret], "y"]), base(default=secret),
             base(expected_utilities={"a": secret, "b": 1, "c": 1}), base(population_shares={"a": secret, "b": "0.5", "c": "0.5"}),
             base(expected_utilities={secret: 1, "b": 1, "c": 1}), dict(base(), **{secret: 1}), {secret: 1}, secret,
             base(population_shares={"a": "0.9", "b": "0.9", "c": "0.9"})]
    for c in cases:
        try:
            lp.review(c)
        except lp.LibertarianError as e:
            assert secret not in str(e) and "0.9" not in str(e)
        else:
            raise AssertionError("not refused")


def test_purity_and_surface():
    d = base()
    before = repr(d)
    a = lp.review(d)
    assert repr(d) == before and a == lp.review(d) and len(a["limits"]) == 3
    pub = [n for n in dir(lp) if not n.startswith("_") and callable(getattr(lp, n)) and getattr(getattr(lp, n), "__module__", "") == "libertarian_paternalism109"]
    assert sorted(pub) == ["LibertarianError", "review"]
