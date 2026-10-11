"""Row 103 Liking Enhancement: hermetic stdlib tests, N/N+1 pins, row-tagged refusals. Loads the module by path."""
import copy
import importlib.util
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/liking_enhancement103.py"
_spec = importlib.util.spec_from_file_location("liking_enhancement103", _SRC)
lk = importlib.util.module_from_spec(_spec)
sys.modules["liking_enhancement103"] = lk
_spec.loader.exec_module(lk)


def com(topic, both=True):
    return {"topic": topic, "confirmed_by_both": both}


def go(common=None, claimed=None, disclosed=True):
    return lk.review({"commonalities": [com("hiking"), com("jazz")] if common is None else common,
                      "claimed": ["hiking"] if claimed is None else claimed, "disclosed": disclosed})


def refused(fn, word):
    with pytest.raises(lk.LikingError) as e:
        fn()
    assert str(e.value).startswith("LIKING103: ")
    assert word in str(e.value)


def test_supported_claim_is_usable_with_exact_fractions():
    r = go()
    assert r["row"] == 103 and r["supported"] == ["hiking"] and r["unsupported"] == [] and r["unconfirmed"] == []
    assert r["precision"] == "1/1" and r["coverage"] == "1/2"
    assert r["usable"] is True and r["allowed"] is True


def test_claim_of_unlisted_topic_is_unsupported_and_blocks():
    r = go(claimed=["hiking", "chess"])
    assert r["unsupported"] == ["chess"] and r["supported"] == ["hiking"]
    assert r["precision"] == "1/2" and r["usable"] is False and r["allowed"] is False


def test_unconfirmed_commonality_does_not_support_a_claim():
    r = go([com("hiking", both=False), com("jazz")], ["hiking"])
    assert r["unconfirmed"] == ["hiking"] and r["supported"] == [] and r["unsupported"] == ["hiking"]
    assert r["coverage"] == "0/1" and r["precision"] == "0/1"


def test_matching_is_case_and_space_insensitive_and_output_normalised():
    r = go([com("  Hiking ")], ["hIKING"])
    assert r["supported"] == ["hiking"] and r["coverage"] == "1/1"


def test_empty_claims_gives_none_precision_and_not_usable():
    r = go(claimed=[])
    assert r["precision"] is None and r["usable"] is False and r["allowed"] is False and r["coverage"] == "0/1"


def test_no_confirmed_commonalities_gives_none_coverage():
    r = go([com("hiking", both=False)], [])
    assert r["coverage"] is None and r["unconfirmed"] == ["hiking"]


def test_fractions_are_reduced():
    r = go([com("a"), com("b"), com("c"), com("d")], ["a", "b"])
    assert r["coverage"] == "1/2" and r["precision"] == "1/1"
    r = go([com("a"), com("b"), com("c"), com("d")], ["a", "b", "x", "y"])
    assert r["precision"] == "1/2"


def test_not_disclosed_is_usable_but_not_allowed():
    r = go(disclosed=False)
    assert r["usable"] is True and r["allowed"] is False
    refused(lambda: go(disclosed="yes"), "disclosed")


def test_outputs_sorted_and_deduplicated_claims_refused():
    r = go([com("b"), com("a")], ["b", "a"])
    assert r["supported"] == ["a", "b"]
    refused(lambda: go(claimed=["a", " A"]), "duplicate")
    refused(lambda: go([com("a"), com("A ")], ["a"]), "duplicate")


def test_list_caps_50_ok_51_refused():
    ok = [com(f"t{i}") for i in range(50)]
    assert go(ok, [f"t{i}" for i in range(50)])["coverage"] == "1/1"
    refused(lambda: go(ok + [com("extra")], ["t0"]), "commonalities")
    refused(lambda: go(ok, [f"t{i}" for i in range(50)] + ["extra"]), "claimed")


def test_topic_length_100_ok_101_refused_blank_refused():
    assert go([com("x" * 100)], ["x" * 100])["supported"] == ["x" * 100]
    refused(lambda: go([com("x" * 101)], []), "topic")
    refused(lambda: go([com(" ")], []), "topic")
    refused(lambda: go(claimed=["x" * 101]), "claim")
    refused(lambda: go(claimed=[""]), "claim")


def test_shape_refusals_exact():
    with pytest.raises(lk.LikingError) as e:
        lk.review([])
    assert str(e.value) == "LIKING103: input must be a mapping"
    with pytest.raises(lk.LikingError) as e:
        lk.review({"commonalities": [], "claimed": []})
    assert str(e.value) == "LIKING103: disclosed required"
    with pytest.raises(lk.LikingError) as e:
        go(disclosed=0)
    assert str(e.value) == "LIKING103: disclosed must be true or false"
    refused(lambda: lk.review({"commonalities": [], "claimed": [], "disclosed": True, "x": 1}), "unknown key")
    refused(lambda: lk.review({"commonalities": "a", "claimed": [], "disclosed": True}), "commonalities")
    refused(lambda: lk.review({"commonalities": [], "claimed": "a", "disclosed": True}), "claimed")
    refused(lambda: lk.review({"claimed": [], "disclosed": True}), "commonalities")
    refused(lambda: lk.review({"commonalities": [], "disclosed": True}), "claimed")
    refused(lambda: go(["a"], []), "commonality 0")
    refused(lambda: go([dict(com("a"), x=1)], []), "unknown key")
    refused(lambda: go([{"topic": "a"}], []), "confirmed_by_both")
    refused(lambda: go([com("a", both="yes")], []), "confirmed_by_both")
    refused(lambda: go([{"confirmed_by_both": True}], []), "topic")
    refused(lambda: go(claimed=[3]), "claim")


def test_limits_exact_deterministic_and_input_not_mutated():
    common, claimed = [com("a")], ["a"]
    before = copy.deepcopy((common, claimed))
    r = go(common, claimed)
    assert (common, claimed) == before and r == go(common, claimed)
    assert r["limits"] == [
        "Supplied declarations only; whether a commonality is real is the caller's statement, not checked here.",
        "Only commonalities confirmed by both people may be cited; an invented similarity is blocked, never suggested.",
        "Not a prediction that anyone will like anyone and not advice; say nothing you cannot stand behind.",
    ]


def test_residual_no_unicode_normalization_or_casefold():
    r = go(common=[com("\u00e9")], claimed=["e\u0301"])
    assert r["supported"] == [] and r["unsupported"] == ["e\u0301"]
    r = go(common=[com("Stra\u00dfe")], claimed=["STRASSE"])
    assert r["supported"] == [] and r["unsupported"] == ["strasse"]
    assert go(common=[com("  Ab ")], claimed=["aB"])["supported"] == ["ab"]


def test_residual_control_and_format_characters_accepted_and_echoed():
    for t in ("a\u202eb", "a\x00b", "a\u200bb"):
        r = go(common=[com(t)], claimed=[t])
        assert r["supported"] == [t] and r["unsupported"] == []


def test_residual_unknown_key_echo_uncapped():
    for n in (4000, 5000, 100000):
        key = "k" * n
        with pytest.raises(lk.LikingError) as e:
            lk.review({key: 1})
        assert key in str(e.value)
        with pytest.raises(lk.LikingError) as e:
            lk.review({"commonalities": [{key: 1}], "claimed": [], "disclosed": True})
        assert key in str(e.value)
