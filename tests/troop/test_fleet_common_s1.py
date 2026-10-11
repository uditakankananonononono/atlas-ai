"""Shared S1 checks: exact bounds of the type/control-character walk."""
import pytest

from app.troop import fleet_common as F


def nest(k):
    v = 1
    for _ in range(k):
        v = [v]
    return v


def refusal(fn):
    with pytest.raises(ValueError) as cm:
        fn()
    return str(cm.value)


def test_depth_exact_bounds_with_defaults():
    F.scan(nest(8), "U", "f")
    assert refusal(lambda: F.scan(nest(9), "U", "f")) == "U:too_deep"
    d = {}
    cur = d
    for _ in range(8):
        cur["k"] = {}
        cur = cur["k"]
    F.scan(d, "U", "f")


def test_node_budget_exact_bounds():
    F.scan([0] * (F.MAX_NODES - 1), "U", "f")
    assert refusal(lambda: F.scan([0] * F.MAX_NODES, "U", "f")) == "U:too_deep"
    F.scan(1, "U", "f", 0, [F.MAX_NODES - 1])
    assert refusal(lambda: F.scan(1, "U", "f", 0, [F.MAX_NODES])) == "U:too_deep"
    b = [0]
    F.scan({"a": [1, "x"]}, "U", "f", 0, b)
    assert b[0] == 5


def test_non_str_keys_and_foreign_types():
    assert refusal(lambda: F.scan({1: 2}, "U", "f")) == "U:bad_type:f"
    assert refusal(lambda: F.scan([object()], "U", "f")) == "U:bad_type:f"
    assert refusal(lambda: F.scan(["a\x00"], "U", "f")) == "U:control_chars:f"


def test_text_ok_only_for_named_keys_and_only_whitespace():
    F.scan({"text": "a\nb\r\t"}, "U", "f", text_ok=("text",))
    assert refusal(lambda: F.scan({"text": "a\x00"}, "U", "f", text_ok=("text",))) == "U:control_chars:f"
    assert refusal(lambda: F.scan({"text": "a\u2028"}, "U", "f", text_ok=("text",))) == "U:control_chars:f"
    assert refusal(lambda: F.scan({"other": "a\n"}, "U", "f", text_ok=("text",))) == "U:control_chars:f"
    assert refusal(lambda: F.scan({"o": {"text": "a\x1b"}}, "U", "f", text_ok=("text",))) == "U:control_chars:f"
    F.scan({"o": {"text": "a\n"}}, "U", "f", text_ok=("text",))


def test_exact_keys_and_codes():
    assert F.NOSOURCE == "FLEET_REFUSED_NOSOURCE" and F.UNLICENSED == "FLEET_REFUSED_UNLICENSED"
    assert F.SPEND == "FLEET_REFUSED_SPEND"
    assert refusal(lambda: F.exact_keys([], "U", "f", ("a",), ())) == "U:bad_type:f"
    assert refusal(lambda: F.exact_keys({"b": 1}, "U", "f", ("a",), ())) == "U:unknown_field:f"
    assert refusal(lambda: F.exact_keys({}, "U", "f", ("a",), ("a",))) == "U:missing_field:f"
    assert F.FleetRefusal("X").code == "X" and str(F.FleetRefusal("X")) == "X"


def test_limits_pinned_and_key_depth():
    assert F.MAX_NODES == 200000 and F.MAX_DEPTH == 8
    d = {}
    cur = d
    for _ in range(8):
        cur["k"] = {}
        cur = cur["k"]
    cur["k"] = 1
    assert refusal(lambda: F.scan(d, "U", "f")) == "U:too_deep"
