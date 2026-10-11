"""Row 105 Pre-Suasion: hermetic stdlib tests, N/N+1 pins, row-tagged refusals. Loads the module by path."""
import importlib.util
import math
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/pre_suasion105.py"
_spec = importlib.util.spec_from_file_location("pre_suasion105", _SRC)
ps = importlib.util.module_from_spec(_spec)
sys.modules["pre_suasion105"] = ps
_spec.loader.exec_module(ps)


def base(**over):
    d = {"context": "agenda", "disclosed": True, "attention_weights": [1, 1]}
    d.update(over)
    return d


def go(**over):
    return ps.review(base(**over))


def refused(data, word, exact_type=True):
    with pytest.raises(ps.PreSuasionError) as e:
        ps.review(data)
    msg = str(e.value)
    assert msg.startswith("PRESUA105: ") and word in msg
    return msg


def test_equal_weights_balance_one():
    r = go()
    assert r["row"] == 105 and r["shares"] == ["1/2", "1/2"] and r["max_share"] == "1/2"
    assert r["max_share_index"] == [0, 1] and r["balance"] == 1.0 and r["concentration_check"] is True
    assert r["allowed"] is True and r["covert_influence_blocked"] is False
    assert "interval" not in " ".join(r)


def test_three_to_one_hand_computed():
    # H = -(3/4 ln 3/4 + 1/4 ln 1/4) / ln 2 = (0.2157616 + 0.3465736) / 0.6931472 = 0.811278
    r = go(attention_weights=[3, 1])
    assert r["shares"] == ["3/4", "1/4"] and r["max_share"] == "3/4" and r["max_share_index"] == [0]
    assert abs(r["balance"] - 0.811278) < 1e-6 and r["concentration_check"] is False
    assert r["balance"] == round(r["balance"], 6) and len(repr(r["balance"])) <= 8   # rounded to 6 places


def test_single_mass_balance_zero_not_negative_zero():
    r = go(attention_weights=[1, 0, 0])
    assert r["shares"] == ["1/1", "0/1", "0/1"] and r["balance"] == 0.0
    assert math.copysign(1.0, r["balance"]) == 1.0
    assert r["concentration_check"] is False and r["max_share_index"] == [0]


def test_concentration_check_boundary_exact_half():
    assert go(attention_weights=[1, 1])["concentration_check"] is True      # max share = 1/2 exactly
    assert go(attention_weights=[1, 1, 2])["concentration_check"] is True   # 2/4 = 1/2
    assert go(attention_weights=[2, 1, 2])["concentration_check"] is True
    assert go(attention_weights=[1000000001 - 1, 999999999])["concentration_check"] is False
    assert go(attention_weights=[3, 2])["concentration_check"] is False


def test_ties_all_listed_sorted():
    r = go(attention_weights=[2, 5, 5, 1, 5])
    assert r["max_share_index"] == [1, 2, 4] and r["max_share"] == "5/18"


def test_undisclosed_blocks():
    r = go(disclosed=False)
    assert r["allowed"] is False and r["covert_influence_blocked"] is True


def test_limits_three_strings():
    r = go()
    assert len(r["limits"]) == 3 and all(type(x) is str and x for x in r["limits"])


def test_disclosed_exact_bool_only():
    for bad in (1, 0, "true", "1", None, [], 1.0):
        refused(base(disclosed=bad), "disclosed")
    refused({"context": "a", "attention_weights": [1, 1]}, "disclosed")


def test_weights_types_and_values():
    for bad in ([1, -1], [0, 0], [True, 1], [1.0, 1], ["1", 1], [None, 1], [1, 10**9 + 1], [-1, 5], "11", (1, 1), None, {1: 1}):
        refused(base(attention_weights=bad), "attention_weights")
    refused(base(attention_weights=[1, -1]), "attention_weights")
    assert go(attention_weights=[0, 1])["shares"] == ["0/1", "1/1"]
    assert go(attention_weights=[10**9, 10**9])["balance"] == 1.0


def test_weights_length_2_ok_1_refused_20_ok_21_refused():
    refused(base(attention_weights=[1]), "attention_weights")
    refused(base(attention_weights=[]), "attention_weights")
    assert len(go(attention_weights=[1] * 20)["shares"]) == 20
    refused(base(attention_weights=[1] * 21), "attention_weights")


def test_length_checked_before_iteration():
    m = refused(base(attention_weights=["bad"] + [1] * 20), "list of 2 to 20")
    assert "integers" not in m


def test_key_count_before_iteration():
    d = base()
    for i in range(50):
        d["k%d" % i] = 1
    m = refused(d, "too many keys")
    assert "unknown" not in m
    refused({k: v for k, v in dict(base(), extra=1).items() if k != "context"}, "unknown key")
    d = base(); del d["context"]
    refused(d, "context required")
    d = base(); del d["attention_weights"]
    refused(d, "attention_weights required")


def test_non_str_key_and_non_dict():
    refused({1: 1, "context": "a", "disclosed": True}, "unknown key")
    for bad in (None, [], "x", 5, ()):
        refused(bad, "mapping")

    class D(dict):
        touched = 0

        def __len__(self):
            D.touched += 1
            return 1
    refused(D(base()), "mapping")
    assert D.touched == 0


def test_list_subclass_refused_untouched():
    class L(list):
        touched = 0

        def __len__(self):
            L.touched += 1
            return 3

        def __iter__(self):
            L.touched += 1
            return list.__iter__(self)
    refused(base(attention_weights=L([1, 1, 1])), "attention_weights")
    assert L.touched == 0


def test_int_subclass_weight_refused():
    class I(int):
        pass
    refused(base(attention_weights=[I(1), 1]), "attention_weights")


def test_context_rules():
    assert go(context="a" * 200)["context"] == "a" * 200
    refused(base(context="a" * 201), "context")
    for bad in ("", "   ", "\t", None, 5, b"x", ["a"]):
        refused(base(context=bad), "context")
    for ch in ("\x00", "\x1f", "\x7f", "\x85", "\n", "\r", "\t", "\u200b", "\u202e", "\ufeff", "\u2028", "\u2029"):
        refused(base(context="a" + ch + "b"), "context")
    assert go(context="a\u00a0b\u3000c")["context"] == "a\u00a0b\u3000c"   # Zs is allowed
    assert go(context="caf\u00e9 \u4e2d")["context"] == "caf\u00e9 \u4e2d"


def test_oversize_text_beats_content_check():
    m = refused(base(context="\x00" * 201), "longer than 200")
    assert "control" not in m


def test_text_subclass_refused():
    class S(str):
        pass
    refused(base(context=S("agenda")), "context")


def test_no_value_in_any_refusal_message():
    secret = "ZZSECRET9"
    cases = [base(context=secret + "\x00"), base(context=secret * 40), dict(base(), **{secret: 1}),
             base(disclosed=secret), base(attention_weights=[secret, 1]), base(attention_weights=[secret] * 30),
             {secret: 1}, secret]
    for c in cases:
        try:
            ps.review(c)
        except ps.PreSuasionError as e:
            assert secret not in str(e)
        else:
            raise AssertionError("not refused")


def test_input_not_mutated_and_deterministic():
    d = base(attention_weights=[3, 1, 2])
    before = repr(d)
    a, b = ps.review(d), ps.review(d)
    assert repr(d) == before and a == b
    a["limits"].append("x")
    assert len(ps.review(d)["limits"]) == 3


def test_module_only_declares_review():
    pub = [n for n in dir(ps) if not n.startswith("_") and callable(getattr(ps, n)) and getattr(getattr(ps, n), "__module__", "") == "pre_suasion105"]
    assert sorted(pub) == ["PreSuasionError", "review"]
