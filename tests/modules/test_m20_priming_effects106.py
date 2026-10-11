"""Row 106 Priming Effects: hermetic stdlib tests, N/N+1 pins, row-tagged refusals. Loads the module by path."""
import importlib.util
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/priming_effects106.py"
_spec = importlib.util.spec_from_file_location("priming_effects106", _SRC)
pe = importlib.util.module_from_spec(_spec)
sys.modules["priming_effects106"] = pe
_spec.loader.exec_module(pe)

C = ("exposed_successes", "exposed_total", "control_successes", "control_total")


def counts(es=30, en=100, cs=20, cn=100):
    return dict(zip(C, (es, en, cs, cn)))


def base(**over):
    d = {"context": "agenda", "disclosed": True}
    d.update(counts())
    d.update(over)
    return d


def go(**over):
    return pe.review(base(**over))


def refused(data, word):
    with pytest.raises(pe.PrimingError) as e:
        pe.review(data)
    msg = str(e.value)
    assert msg.startswith("PRIME106: ") and word in msg
    return msg


def test_hand_computed_30_100_vs_20_100():
    # effect = 3/10 - 1/5 = 1/10; var = .3*.7/100 + .2*.8/100 = .0037; se = .0608276; 1.96*se = .1192221
    r = go()
    assert r["row"] == 106 and r["effect"] == "1/10" and r["effect_decimal"] == "0.100000"
    assert abs(r["interval_95"][0] - (-0.019222)) < 1e-6 and abs(r["interval_95"][1] - 0.219222) < 1e-6
    assert r["interval_95"] == [-0.019222, 0.219222]
    assert (r["degenerate_rate"], r["small_sample"], r["interval_unreliable"]) == (False, False, False)
    assert r["causal_estimate_available"] is False and r["descriptive_difference_available"] is True
    assert r["allowed"] is True and r["covert_influence_blocked"] is False


def test_negative_effect_sign_and_reduction():
    r = go(exposed_successes=20, control_successes=30)
    assert r["effect"] == "-1/10" and r["effect_decimal"] == "-0.100000"
    r = go(exposed_successes=25, exposed_total=50, control_successes=2, control_total=4)
    assert r["effect"] == "0/1" and r["effect_decimal"] == "0.000000"


def test_decimal_rounding_half_even_exact():
    # 1/7 = 0.142857142857..., 1/3 = 0.333333, 2/3 = 0.666667
    r = go(exposed_successes=1, exposed_total=3, control_successes=0, control_total=1)
    assert r["effect"] == "1/3" and r["effect_decimal"] == "0.333333"
    r = go(exposed_successes=2, exposed_total=3, control_successes=0, control_total=1)
    assert r["effect_decimal"] == "0.666667"
    # exact half at the 7th decimal: 1/2000000 = 0.0000005 -> 0.000000 (even); 3/2000000 = 0.0000015 -> 0.000002
    r = go(exposed_successes=1, exposed_total=2000000, control_successes=0, control_total=1)
    assert r["effect_decimal"] == "0.000000"
    r = go(exposed_successes=3, exposed_total=2000000, control_successes=0, control_total=1)
    assert r["effect_decimal"] == "0.000002"
    r = go(exposed_successes=0, exposed_total=1, control_successes=1, control_total=2000000)
    assert r["effect_decimal"] == "0.000000"   # tiny negative rounds to zero without a minus sign


def test_degenerate_rates_have_no_interval():
    r = go(exposed_successes=0, exposed_total=10, control_successes=0, control_total=10)
    assert r["interval_95"] is None and r["degenerate_rate"] is True and r["interval_unreliable"] is True
    assert r["effect"] == "0/1"
    r = go(exposed_successes=10, exposed_total=10, control_successes=5, control_total=10)
    assert r["interval_95"] is None and r["degenerate_rate"] is True
    r = go(exposed_successes=5, exposed_total=10, control_successes=0, control_total=10)
    assert r["interval_95"] is None and r["degenerate_rate"] is True
    r = go(exposed_successes=5, exposed_total=10, control_successes=10, control_total=10)
    assert r["interval_95"] is None


def test_effect_of_exactly_one_and_minus_one():
    r = go(exposed_successes=10, exposed_total=10, control_successes=0, control_total=10)
    assert r["effect"] == "1/1" and r["effect_decimal"] == "1.000000" and r["interval_95"] is None
    r = go(exposed_successes=0, exposed_total=10, control_successes=10, control_total=10)
    assert r["effect"] == "-1/1" and r["effect_decimal"] == "-1.000000"
    assert go(exposed_successes=3, exposed_total=4, control_successes=1, control_total=2)["effect_decimal"] == "0.250000"


def test_each_rate_at_zero_or_one_alone_is_degenerate():
    for es, cs in ((0, 5), (10, 5), (5, 0), (5, 10)):
        r = go(exposed_successes=es, exposed_total=10, control_successes=cs, control_total=10)
        assert r["interval_95"] is None and r["degenerate_rate"] is True, (es, cs)
    r = go(exposed_successes=1, exposed_total=10, control_successes=9, control_total=10)
    assert r["interval_95"] is not None and r["degenerate_rate"] is False


def test_small_sample_cell_4_flagged_5_not():
    r = go(exposed_successes=4, exposed_total=100, control_successes=50, control_total=100)
    assert r["small_sample"] is True and r["interval_unreliable"] is True and r["degenerate_rate"] is False
    r = go(exposed_successes=5, exposed_total=100, control_successes=50, control_total=100)
    assert r["small_sample"] is False and r["interval_unreliable"] is False
    # each of the four cells matters
    assert go(exposed_successes=96, exposed_total=100, control_successes=50, control_total=100)["small_sample"] is True
    assert go(exposed_successes=95, exposed_total=100, control_successes=50, control_total=100)["small_sample"] is False
    assert go(exposed_successes=50, exposed_total=100, control_successes=4, control_total=100)["small_sample"] is True
    assert go(exposed_successes=50, exposed_total=100, control_successes=5, control_total=100)["small_sample"] is False
    assert go(exposed_successes=50, exposed_total=100, control_successes=96, control_total=100)["small_sample"] is True
    assert go(exposed_successes=50, exposed_total=100, control_successes=95, control_total=100)["small_sample"] is False


def test_no_counts():
    r = pe.review({"context": "a", "disclosed": True})
    assert r["effect"] is None and r["effect_decimal"] is None and r["interval_95"] is None
    assert r["descriptive_difference_available"] is False and r["allowed"] is False
    assert (r["degenerate_rate"], r["small_sample"], r["interval_unreliable"]) == (False, False, False)
    assert r["causal_estimate_available"] is False


def test_undisclosed_blocks_even_with_counts():
    r = go(disclosed=False)
    assert r["allowed"] is False and r["covert_influence_blocked"] is True and r["effect"] == "1/10"
    r = pe.review({"context": "a", "disclosed": False})
    assert r["allowed"] is False and r["covert_influence_blocked"] is True


def test_count_types():
    for k in C:
        for bad in ("5", 5.0, True, None, [5], -1, 10**9 + 1):
            refused(base(**{k: bad}), k)
    refused(base(exposed_successes=False), "exposed_successes")


def test_count_bounds_10_9():
    r = go(exposed_successes=10**9, exposed_total=10**9, control_successes=1, control_total=10**9)
    assert r["effect"] == "999999999/1000000000"
    refused(base(exposed_total=10**9 + 1), "exposed_total")
    refused(base(control_total=10**9 + 1), "control_total")


def test_partial_set_refused_each_missing_key():
    for k in C:
        d = base()
        del d[k]
        refused(d, "all four or none")
    d = {"context": "a", "disclosed": True, "exposed_successes": 1}
    refused(d, "all four or none")


def test_relations():
    refused(base(exposed_total=0, exposed_successes=0), "exposed_total")
    refused(base(control_total=0, control_successes=0), "control_total")
    refused(base(exposed_successes=101), "exposed_successes")
    refused(base(control_successes=101), "control_successes")
    assert go(exposed_successes=100)["effect"] == "4/5"
    assert go(control_successes=100)["effect"] == "-7/10"


def test_type_checked_before_relation():
    m = refused(base(exposed_successes="x", exposed_total=0), "exposed_successes")
    assert "at least 1" not in m


def test_disclosed_and_context():
    for bad in (1, 0, "true", None):
        refused(base(disclosed=bad), "disclosed")
    refused({"context": "a"}, "disclosed")
    refused({"disclosed": True}, "context")
    assert go(context="a" * 200)["context"] == "a" * 200
    refused(base(context="a" * 201), "context")
    for bad in ("", "  ", None, 5):
        refused(base(context=bad), "context")
    for ch in ("\x00", "\x7f", "\x85", "\n", "\t", "\u200b", "\u202e", "\u2028", "\u2029"):
        refused(base(context="a" + ch), "context")
    assert go(context="a\u00a0b")["context"] == "a\u00a0b"
    m = refused(base(context="\x00" * 201), "longer than 200")
    assert "control" not in m


def test_keys_and_types():
    d = base()
    for i in range(50):
        d["k%d" % i] = 1
    m = refused(d, "too many keys")
    assert "unknown" not in m
    refused({k: v for k, v in dict(base(), extra=1).items() if k != "context"}, "unknown key")
    refused({1: 1, "context": "a", "disclosed": True}, "unknown key")
    for bad in (None, [], "x", 5):
        refused(bad, "mapping")

    class D(dict):
        touched = 0

        def __len__(self):
            D.touched += 1
            return 1
    refused(D(base()), "mapping")
    assert D.touched == 0

    class S(str):
        pass
    refused(base(context=S("a")), "context")


def test_no_value_in_refusal():
    secret = "ZZSECRET9"
    for c in (base(context=secret * 40), base(context=secret + "\x00"), dict(base(), **{secret: 1}),
              base(exposed_total=secret), base(disclosed=secret), {secret: 1}, secret):
        try:
            pe.review(c)
        except pe.PrimingError as e:
            assert secret not in str(e)
        else:
            raise AssertionError("not refused")


def test_limits_scope_and_purity():
    r = go()
    assert len(r["limits"]) == 3 and "no causal claim" in r["limits"][1]
    d = base()
    before = repr(d)
    pe.review(d)
    assert repr(d) == before and pe.review(d) == pe.review(d)
    pub = [n for n in dir(pe) if not n.startswith("_") and callable(getattr(pe, n)) and getattr(getattr(pe, n), "__module__", "") == "priming_effects106"]
    assert sorted(pub) == ["PrimingError", "review"]
