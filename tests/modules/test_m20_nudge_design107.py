"""Row 107 Nudge Design: hermetic stdlib tests, N/N+1 pins, row-tagged refusals. Loads the module by path."""
import copy
import importlib.util
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/nudge_design107.py"
_spec = importlib.util.spec_from_file_location("nudge_design107", _SRC)
nd = importlib.util.module_from_spec(_spec)
sys.modules["nudge_design107"] = nd
_spec.loader.exec_module(nd)


def go(**over):
    d = {"options": ["enrol", "skip"], "default": "enrol", "easy_opt_out": True, "transparent": True,
         "alternatives_visible": True, "opt_out_steps": 1}
    d.update(over)
    return nd.review(d)


def refused(fn, word):
    with pytest.raises(nd.NudgeError) as e:
        fn()
    assert str(e.value).startswith("NUDGED107: ")
    assert word in str(e.value)


def test_clean_nudge_passes_all_four_checks():
    r = go()
    assert r["row"] == 107 and r["failures"] == [] and r["checks_passed"] == 4 and r["allowed"] is True
    assert r["default"] == "enrol" and r["options"] == ["enrol", "skip"] and r["supplied_uptake_difference"] is None


def test_each_failure_is_named_in_fixed_order():
    r = go(easy_opt_out=False, transparent=False, alternatives_visible=False, opt_out_steps=3)
    assert r["failures"] == ["opt_out_not_easy", "not_transparent", "alternatives_hidden", "opt_out_steps_over_2"]
    assert r["checks_passed"] == 0 and r["allowed"] is False
    assert go(easy_opt_out=False)["failures"] == ["opt_out_not_easy"]
    assert go(transparent=False)["failures"] == ["not_transparent"]
    assert go(alternatives_visible=False)["failures"] == ["alternatives_hidden"]


def test_opt_out_steps_2_ok_3_fails_0_ok_20_ok_21_refused():
    assert go(opt_out_steps=2)["failures"] == []
    assert go(opt_out_steps=3)["failures"] == ["opt_out_steps_over_2"]
    assert go(opt_out_steps=0)["allowed"] is True
    assert go(opt_out_steps=20)["failures"] == ["opt_out_steps_over_2"]
    refused(lambda: go(opt_out_steps=21), "opt_out_steps")
    refused(lambda: go(opt_out_steps=-1), "opt_out_steps")
    refused(lambda: go(opt_out_steps=True), "opt_out_steps")
    refused(lambda: go(opt_out_steps=1.0), "opt_out_steps")


def test_checks_passed_counts_partial():
    assert go(transparent=False, opt_out_steps=3)["checks_passed"] == 2


def test_uptake_difference_exact_fraction_when_supplied():
    r = go(baseline_uptake=[1, 4], default_uptake=[3, 4])
    assert r["supplied_uptake_difference"] == "1/2"
    r = go(baseline_uptake=[3, 4], default_uptake=[1, 4])
    assert r["supplied_uptake_difference"] == "-1/2"
    r = go(baseline_uptake=[1, 3], default_uptake=[1, 3])
    assert r["supplied_uptake_difference"] == "0/1"
    r = go(baseline_uptake=[1, 3], default_uptake=[1, 2])
    assert r["supplied_uptake_difference"] == "1/6"


def test_uptake_both_or_neither_and_valid_pairs():
    refused(lambda: go(baseline_uptake=[1, 2]), "both")
    refused(lambda: go(default_uptake=[1, 2]), "both")
    refused(lambda: go(baseline_uptake=[1], default_uptake=[1, 2]), "baseline_uptake")
    refused(lambda: go(baseline_uptake=[3, 2], default_uptake=[1, 2]), "baseline_uptake")
    refused(lambda: go(baseline_uptake=[1, 0], default_uptake=[1, 2]), "baseline_uptake")
    refused(lambda: go(baseline_uptake=[-1, 2], default_uptake=[1, 2]), "baseline_uptake")
    refused(lambda: go(baseline_uptake=[1, 2], default_uptake=[1, 10**9 + 1]), "default_uptake")
    assert go(baseline_uptake=[0, 1], default_uptake=[10**9, 10**9])["supplied_uptake_difference"] == "1/1"
    assert go(baseline_uptake=[2, 2], default_uptake=[2, 2])["supplied_uptake_difference"] == "0/1"
    refused(lambda: go(baseline_uptake=[True, 2], default_uptake=[1, 2]), "baseline_uptake")


def test_option_count_2_to_20_unique_default_listed():
    ok = [f"o{i}" for i in range(20)]
    assert go(options=ok, default="o3")["default"] == "o3"
    refused(lambda: go(options=ok + ["o20"], default="o3"), "options")
    refused(lambda: go(options=["a"], default="a"), "options")
    refused(lambda: go(options=["a", "a"], default="a"), "duplicate")
    refused(lambda: go(options=["a", "b"], default="c"), "default")
    refused(lambda: go(options="ab", default="a"), "options")


def test_option_text_length_100_ok_101_refused_blank_refused():
    assert go(options=["x" * 100, "y"], default="y")["options"][0] == "x" * 100
    refused(lambda: go(options=["x" * 101, "y"], default="y"), "option")
    refused(lambda: go(options=[" ", "y"], default="y"), "option")
    refused(lambda: go(options=[1, "y"], default="y"), "option")


def test_flags_must_be_bool_exact_messages_and_shape():
    for k in ("easy_opt_out", "transparent", "alternatives_visible"):
        with pytest.raises(nd.NudgeError) as e:
            go(**{k: 1})
        assert str(e.value) == f"NUDGED107: {k} must be true or false"
    with pytest.raises(nd.NudgeError) as e:
        nd.review([])
    assert str(e.value) == "NUDGED107: input must be a mapping"
    base = {"options": ["a", "b"], "default": "a", "easy_opt_out": True, "transparent": True, "alternatives_visible": True, "opt_out_steps": 1}
    for k in base:
        d = dict(base); del d[k]
        with pytest.raises(nd.NudgeError) as e:
            nd.review(d)
        assert str(e.value) == f"NUDGED107: {k} required"
    refused(lambda: nd.review(dict(base, extra=1)), "unknown key")


def test_limits_exact_deterministic_and_input_not_mutated():
    d = {"options": ["a", "b"], "default": "a", "easy_opt_out": True, "transparent": True, "alternatives_visible": True,
         "opt_out_steps": 1, "baseline_uptake": [1, 2], "default_uptake": [1, 2]}
    before = copy.deepcopy(d)
    r = nd.review(d)
    assert d == before and r == nd.review(d)
    assert r["limits"] == [
        "Supplied declarations only; nothing here measures what people will choose.",
        "A default must not hide costs, obstruct exit or remove alternatives; all four checks must pass.",
        "Not a prediction of behaviour change and not advice; the uptake difference is the caller's supplied figures.",
    ]


def test_uptake_zero_total_and_bool_total_refused():
    refused(lambda: go(baseline_uptake=[0, 0], default_uptake=[1, 2]), "baseline_uptake")
    refused(lambda: go(baseline_uptake=[0, True], default_uptake=[1, 2]), "baseline_uptake")
    refused(lambda: go(baseline_uptake=[1, 2], default_uptake=[0, True]), "default_uptake")


def test_exact_messages_for_options_default_and_uptake():
    with pytest.raises(nd.NudgeError) as e:
        go(options=["a", "a"], default="a")
    assert str(e.value) == "NUDGED107: duplicate option"
    with pytest.raises(nd.NudgeError) as e:
        go(options=["a", "b"], default="c")
    assert str(e.value) == "NUDGED107: default must be one of the options"
    with pytest.raises(nd.NudgeError) as e:
        go(baseline_uptake=[1, 2])
    assert str(e.value) == "NUDGED107: baseline_uptake and default_uptake must be supplied together (both or neither)"
    with pytest.raises(nd.NudgeError) as e:
        go(baseline_uptake=[3, 2], default_uptake=[1, 2])
    assert str(e.value) == "NUDGED107: baseline_uptake must be [successes, total] with 0 <= successes <= total <= 1000000000"
    with pytest.raises(nd.NudgeError) as e:
        go(baseline_uptake=[1, 2], default_uptake=[3, 2])
    assert str(e.value) == "NUDGED107: default_uptake must be [successes, total] with 0 <= successes <= total <= 1000000000"
