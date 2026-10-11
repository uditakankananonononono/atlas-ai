"""Row 108 Choice Architecture: hermetic stdlib tests, N/N+1 pins, row-tagged refusals. Loads the module by path."""
import copy
import importlib.util
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/choice_architecture108.py"
_spec = importlib.util.spec_from_file_location("choice_architecture108", _SRC)
ca = importlib.util.module_from_spec(_spec)
sys.modules["choice_architecture108"] = ca
_spec.loader.exec_module(ca)


def go(**over):
    d = {"options": ["a", "b", "c"], "default": "a", "attributes": {"a": [3, 3], "b": [2, 2], "c": [1, 4]},
         "easy_opt_out": True, "transparent": True, "alternatives_visible": True}
    d.update(over)
    return ca.review(d)


def refused(fn, word):
    with pytest.raises(ca.ChoiceError) as e:
        fn()
    assert str(e.value).startswith("CHOICE108: ")
    assert word in str(e.value)


def test_pareto_dominance_exact_with_first_dominator_in_input_order():
    r = go()
    assert r["row"] == 108 and r["dominated"] == [{"option": "b", "by": "a"}]
    assert r["pareto_front"] == ["a", "c"] and r["burden_units"] == 6 and r["failures"] == [] and r["allowed"] is True


def test_equal_attributes_do_not_dominate_each_other():
    r = go(options=["a", "b"], default="a", attributes={"a": [1, 1], "b": [1, 1]})
    assert r["dominated"] == [] and r["pareto_front"] == ["a", "b"]


def test_one_better_one_equal_dominates_and_one_worse_does_not():
    r = go(options=["a", "b"], default="a", attributes={"a": [2, 1], "b": [1, 1]})
    assert r["dominated"] == [{"option": "b", "by": "a"}]
    r = go(options=["a", "b"], default="a", attributes={"a": [2, 0], "b": [1, 1]})
    assert r["dominated"] == []


def test_first_dominator_is_earliest_in_options_order():
    r = go(options=["x", "a", "b"], default="x", attributes={"x": [1, 1], "a": [5, 5], "b": [9, 9]})
    assert r["dominated"] == [{"option": "x", "by": "a"}, {"option": "a", "by": "b"}]
    assert r["pareto_front"] == ["b"]


def test_dominated_default_fails_and_blocks():
    r = go(default="b")
    assert r["failures"] == ["default_dominated"] and r["allowed"] is False


def test_each_flag_failure_named_in_fixed_order():
    r = go(default="b", easy_opt_out=False, transparent=False, alternatives_visible=False)
    assert r["failures"] == ["default_dominated", "opt_out_not_easy", "not_transparent", "alternatives_hidden"]
    assert go(easy_opt_out=False)["failures"] == ["opt_out_not_easy"]
    assert go(transparent=False)["failures"] == ["not_transparent"]
    assert go(alternatives_visible=False)["failures"] == ["alternatives_hidden"]


def test_over_choice_flag_at_7_vs_8_options():
    opts7 = [f"o{i}" for i in range(7)]
    attrs7 = {o: [i, 7 - i] for i, o in enumerate(opts7)}
    assert go(options=opts7, default="o0", attributes=attrs7)["over_choice_limit"] is False
    opts8 = [f"o{i}" for i in range(8)]
    attrs8 = {o: [i, 8 - i] for i, o in enumerate(opts8)}
    r = go(options=opts8, default="o0", attributes=attrs8)
    assert r["over_choice_limit"] is True and r["allowed"] is True


def test_option_count_2_to_20_and_attribute_count_1_to_10():
    ok = [f"o{i}" for i in range(20)]
    assert go(options=ok, default="o0", attributes={o: [i, 20 - i] for i, o in enumerate(ok)})["burden_units"] == 40
    over = ok + ["o20"]
    refused(lambda: go(options=over, default="o0", attributes={o: [1, 1] for o in over}), "options")
    refused(lambda: go(options=["a"], default="a", attributes={"a": [1]}), "options")
    ten = {o: list(range(10)) for o in "abc"}
    assert go(attributes=ten)["burden_units"] == 30
    eleven = {o: list(range(11)) for o in "abc"}
    refused(lambda: go(attributes=eleven), "attributes")
    refused(lambda: go(attributes={o: [] for o in "abc"}), "attributes")


def test_attribute_value_bounds_pm_1e6():
    assert go(attributes={"a": [10**6, -10**6], "b": [0, 0], "c": [1, 1]})["burden_units"] == 6
    refused(lambda: go(attributes={"a": [10**6 + 1, 0], "b": [0, 0], "c": [1, 1]}), "attribute value")
    refused(lambda: go(attributes={"a": [-10**6 - 1, 0], "b": [0, 0], "c": [1, 1]}), "attribute value")
    refused(lambda: go(attributes={"a": [True, 0], "b": [0, 0], "c": [1, 1]}), "attribute value")
    refused(lambda: go(attributes={"a": [1.5, 0], "b": [0, 0], "c": [1, 1]}), "attribute value")


def test_attribute_matrix_must_match_options_and_be_rectangular():
    refused(lambda: go(attributes={"a": [1, 1], "b": [1, 1]}), "attributes")
    refused(lambda: go(attributes={"a": [1, 1], "b": [1, 1], "c": [1, 1], "d": [1, 1]}), "attributes")
    refused(lambda: go(attributes={"a": [1, 1], "b": [1], "c": [1, 1]}), "same number")
    refused(lambda: go(attributes=[1]), "attributes")
    refused(lambda: go(attributes={"a": "xy", "b": [1], "c": [1]}), "attributes")


def test_option_text_and_default_rules():
    assert go(options=["x" * 100, "b", "c"], default="b", attributes={"x" * 100: [1, 1], "b": [1, 1], "c": [1, 1]})["pareto_front"][0] == "x" * 100
    refused(lambda: go(options=["x" * 101, "b", "c"], default="b", attributes={"x" * 101: [1], "b": [1], "c": [1]}), "option")
    refused(lambda: go(options=["a", "a", "c"]), "duplicate")
    refused(lambda: go(default="z"), "default")
    refused(lambda: go(options="abc"), "options")
    refused(lambda: go(options=[" ", "b", "c"], default="b"), "option")


def test_shape_and_exact_messages():
    with pytest.raises(ca.ChoiceError) as e:
        ca.review([])
    assert str(e.value) == "CHOICE108: input must be a mapping"
    base = {"options": ["a", "b"], "default": "a", "attributes": {"a": [1], "b": [1]}, "easy_opt_out": True,
            "transparent": True, "alternatives_visible": True}
    for k in base:
        d = dict(base); del d[k]
        with pytest.raises(ca.ChoiceError) as e:
            ca.review(d)
        assert str(e.value) == f"CHOICE108: {k} required"
    for k in ("easy_opt_out", "transparent", "alternatives_visible"):
        with pytest.raises(ca.ChoiceError) as e:
            ca.review(dict(base, **{k: 1}))
        assert str(e.value) == f"CHOICE108: {k} must be true or false"
    refused(lambda: ca.review(dict(base, extra=1)), "unknown key")
    with pytest.raises(ca.ChoiceError) as e:
        go(options=["a", "a", "c"])
    assert str(e.value) == "CHOICE108: duplicate option"
    with pytest.raises(ca.ChoiceError) as e:
        go(default="z")
    assert str(e.value) == "CHOICE108: default must be one of the options"


def test_limits_exact_deterministic_and_input_not_mutated():
    d = {"options": ["a", "b"], "default": "a", "attributes": {"a": [2], "b": [1]}, "easy_opt_out": True,
         "transparent": True, "alternatives_visible": True}
    before = copy.deepcopy(d)
    r = ca.review(d)
    assert d == before and r == ca.review(d)
    assert r["limits"] == [
        "Supplied declarations only; higher attribute values are treated as better for every attribute.",
        "Dominated options and all material attributes must stay visible to the person choosing.",
        "Not a prediction of any choice and not advice; this checks the structure of a choice, not what people should pick.",
    ]


def _msg(fn):
    with pytest.raises(ca.ChoiceError) as e:
        fn()
    return str(e.value)


def test_exact_refusal_messages_for_remaining_codes():
    base = {"options": ["a", "b"], "default": "a", "attributes": {"a": [1], "b": [1]}, "easy_opt_out": True,
            "transparent": True, "alternatives_visible": True}
    assert _msg(lambda: ca.review(dict(base, extra=1))) == "CHOICE108: unknown key extra"
    assert _msg(lambda: ca.review(dict(base, options=["a"]))) == "CHOICE108: options must be a list of 2 to 20 items"
    opt = "CHOICE108: each option must be non-empty text of at most 100 characters"
    for bad in ([" ", "b"], [5, "b"], ["x" * 101, "b"]):
        assert _msg(lambda: ca.review(dict(base, options=bad))) == opt
    assert _msg(lambda: ca.review(dict(base, attributes={"a": [1]}))) == "CHOICE108: attributes must be a mapping with exactly the option names as keys"
    assert _msg(lambda: ca.review(dict(base, attributes={"a": [], "b": []}))) == "CHOICE108: attributes per option must be a list of 1 to 10 values"
    assert _msg(lambda: ca.review(dict(base, attributes={"a": [1], "b": [1, 2]}))) == "CHOICE108: every option needs the same number of attributes"
    assert _msg(lambda: ca.review(dict(base, attributes={"a": [1], "b": [10**6 + 1]}))) == "CHOICE108: attribute value must be an integer within 1000000 of zero"
