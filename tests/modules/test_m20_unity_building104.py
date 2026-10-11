"""Row 104 Unity Building: hermetic stdlib tests, N/N+1 pins, row-tagged refusals. Loads the module by path."""
import copy
import importlib.util
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/unity_building104.py"
_spec = importlib.util.spec_from_file_location("unity_building104", _SRC)
ub = importlib.util.module_from_spec(_spec)
sys.modules["unity_building104"] = ub
_spec.loader.exec_module(ub)


def go(a=None, b=None, conflicts=None, choice=True, disclosed=True):
    return ub.review({"goals_a": ["clean river", "fund school"] if a is None else a,
                      "goals_b": ["clean river", "save time"] if b is None else b,
                      "conflicts": [] if conflicts is None else conflicts,
                      "individual_choice_preserved": choice, "disclosed": disclosed})


def refused(fn, word):
    with pytest.raises(ub.UnityError) as e:
        fn()
    assert str(e.value).startswith("UNITYB104: ")
    assert word in str(e.value)


def test_shared_goal_without_conflict_is_full_and_allowed():
    r = go()
    assert r["row"] == 104 and r["shared"] == ["clean river"] and r["only_a"] == ["fund school"] and r["only_b"] == ["save time"]
    assert r["alignment"] == "1/3" and r["conflict_count"] == 0 and r["conflicts"] == []
    assert r["identity_claim"] == "shared_goal" and r["allowed"] is True


def test_conflicts_downgrade_claim_and_must_be_named():
    r = go(conflicts=[["fund school", "save time"]])
    assert r["conflicts"] == [["fund school", "save time"]] and r["conflict_count"] == 1
    assert r["identity_claim"] == "shared_goal_with_named_conflicts" and r["allowed"] is True


def test_no_shared_goal_means_no_claim():
    r = go(["a"], ["b"])
    assert r["shared"] == [] and r["identity_claim"] == "none" and r["allowed"] is False and r["alignment"] == "0/1"


def test_alignment_fraction_reduced_and_empty_union_is_none():
    r = go(["a", "b"], ["a", "b"])
    assert r["alignment"] == "1/1"
    r = go(["a", "b", "c", "d"], ["a", "b"])
    assert r["alignment"] == "1/2"
    r = go([], [])
    assert r["alignment"] is None and r["identity_claim"] == "none"


def test_not_disclosed_or_choice_not_preserved_blocks_allowed():
    assert go(disclosed=False)["allowed"] is False
    r = go(choice=False)
    assert r["allowed"] is False and r["identity_claim"] == "shared_goal"
    assert go(disclosed=False, choice=False)["allowed"] is False


def test_matching_trims_and_lowercases_and_sorts():
    r = go([" Zeta ", "alpha"], ["ALPHA", "zeta "])
    assert r["shared"] == ["alpha", "zeta"]


def test_conflict_pair_must_reference_each_sides_goals_in_order():
    refused(lambda: go(conflicts=[["clean river", "nope"]]), "conflict 0")
    refused(lambda: go(conflicts=[["save time", "fund school"]]), "conflict 0")
    assert go(conflicts=[[" Fund School", "SAVE time "]])["conflicts"] == [["fund school", "save time"]]


def test_conflicts_sorted_deduplicated_refused():
    r = go(["a", "b"], ["x", "y"], [["b", "y"], ["a", "x"]])
    assert r["conflicts"] == [["a", "x"], ["b", "y"]]
    refused(lambda: go(["a"], ["x"], [["a", "x"], [" A", "x"]]), "duplicate")


def test_caps_goals_50_ok_51_refused_conflicts_50_ok_51_refused():
    a = [f"a{i}" for i in range(50)]
    b = [f"b{i}" for i in range(50)]
    assert go(a, b)["alignment"] == "0/1"
    refused(lambda: go(a + ["a50"], b), "goals_a")
    refused(lambda: go(a, b + ["b50"]), "goals_b")
    pairs = [[a[i], b[j]] for i in range(8) for j in range(7)][:50]
    assert go(a, b, pairs)["conflict_count"] == 50
    refused(lambda: go(a, b, pairs + [[a[9], b[9]]]), "conflicts")


def test_goal_length_100_ok_101_refused_blank_and_duplicates_refused():
    assert go(["x" * 100], ["x" * 100])["shared"] == ["x" * 100]
    refused(lambda: go(["x" * 101], []), "goal")
    refused(lambda: go([" "], []), "goal")
    refused(lambda: go([3], []), "goal")
    refused(lambda: go(["a", "A "], []), "duplicate")


def test_shape_refusals_exact_messages():
    with pytest.raises(ub.UnityError) as e:
        ub.review([])
    assert str(e.value) == "UNITYB104: input must be a mapping"
    base = {"goals_a": [], "goals_b": [], "conflicts": [], "individual_choice_preserved": True, "disclosed": True}
    for k in ("goals_a", "goals_b", "conflicts", "individual_choice_preserved", "disclosed"):
        d = dict(base); del d[k]
        with pytest.raises(ub.UnityError) as e:
            ub.review(d)
        assert str(e.value) == f"UNITYB104: {k} required"
    for k in ("individual_choice_preserved", "disclosed"):
        with pytest.raises(ub.UnityError) as e:
            ub.review(dict(base, **{k: 1}))
        assert str(e.value) == f"UNITYB104: {k} must be true or false"
    refused(lambda: ub.review(dict(base, extra=1)), "unknown key")
    refused(lambda: ub.review(dict(base, goals_a="x")), "goals_a")
    refused(lambda: ub.review(dict(base, conflicts="x")), "conflicts")
    refused(lambda: ub.review(dict(base, conflicts=["ab"])), "conflict 0")
    refused(lambda: ub.review(dict(base, conflicts=[["a"]])), "conflict 0")


def test_limits_exact_deterministic_and_input_not_mutated():
    a, b, c = ["a"], ["a"], []
    before = copy.deepcopy((a, b, c))
    r = go(a, b, c)
    assert (a, b, c) == before and r == go(a, b, c)
    assert r["limits"] == [
        "Supplied declarations only; goals are the callers' statements and are not checked here.",
        "Shared identity may not erase a conflict or a person's own choice; named conflicts stay named.",
        "Not a prediction of cohesion and not advice; invented common ground is never suggested.",
    ]


def test_goal_messages_name_the_side():
    with pytest.raises(ub.UnityError) as e:
        go(["x" * 101], [])
    assert str(e.value) == "UNITYB104: goals_a goal 0 must be a non-empty string of at most 100 characters"
    with pytest.raises(ub.UnityError) as e:
        go([], ["ok", " "])
    assert str(e.value) == "UNITYB104: goals_b goal 1 must be a non-empty string of at most 100 characters"
    with pytest.raises(ub.UnityError) as e:
        go([], ["a", "A"])
    assert str(e.value) == "UNITYB104: duplicate goal 'a' in goals_b"


def test_residual_self_conflict_pair_accepted_and_counted():
    r = go(a=["x"], b=["x"], conflicts=[["x", "x"]])
    assert r["identity_claim"] == "shared_goal_with_named_conflicts" and r["conflict_count"] == 1
    assert r["conflicts"] == [["x", "x"]] and r["allowed"] is True


def test_residual_u202e_goal_accepted_and_echoed():
    g = "a\u202eb"
    r = go(a=[g], b=[g])
    assert r["shared"] == [g]


def test_residual_unknown_key_echo_uncapped():
    for n in (4000, 5000, 100000):
        key = "k" * n
        with pytest.raises(ub.UnityError) as e:
            ub.review({key: 1})
        assert key in str(e.value)


def test_residual_matching_is_strip_lower_only():
    assert go(a=["  Ab "], b=["aB"])["shared"] == ["ab"]
    assert go(a=["\u00e9"], b=["e\u0301"])["identity_claim"] == "none"
    assert go(a=["Stra\u00dfe"], b=["STRASSE"])["identity_claim"] == "none"
