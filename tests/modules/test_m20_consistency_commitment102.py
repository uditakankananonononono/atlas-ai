"""Row 102 Consistency Commitment: hermetic stdlib tests, N/N+1 pins, row-tagged refusals. Loads the module by path."""
import importlib.util
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/consistency_commitment102.py"
_spec = importlib.util.spec_from_file_location("consistency_commitment102", _SRC)
cc = importlib.util.module_from_spec(_spec)
sys.modules["consistency_commitment102"] = cc
_spec.loader.exec_module(cc)


def step(sid="s1", size=1, freely=True, accepted=True, exit_ok=True):
    return {"id": sid, "size": size, "freely_chosen": freely, "accepted": accepted, "exit_available": exit_ok}


def go(steps=None, ladder_disclosed=True):
    return cc.review({"steps": [step()] if steps is None else steps, "ladder_disclosed": ladder_disclosed})


def refused(fn, word):
    with pytest.raises(cc.ConsistencyError) as e:
        fn()
    assert str(e.value).startswith("CONSIS102: ")
    assert word in str(e.value)


def test_single_free_disclosed_step_is_allowed():
    r = go()
    assert r["row"] == 102 and r["allowed"] is True and r["first_violation"] is None
    assert r["steps"] == [{"id": "s1", "size": 1, "ratio_to_prior_accepted": None, "violations": []}]


def test_escalation_exactly_double_is_ok_triple_flags():
    ok = go([step("a", 2), step("b", 4)])
    assert ok["allowed"] is True and ok["steps"][1]["ratio_to_prior_accepted"] == "2/1"
    bad = go([step("a", 2), step("b", 5)])
    assert bad["allowed"] is False and bad["steps"][1]["violations"] == ["escalation_over_2x"]
    assert bad["first_violation"] == {"index": 1, "id": "b", "code": "escalation_over_2x"}


def test_ratio_is_exact_fraction_reduced():
    r = go([step("a", 4), step("b", 6)])
    assert r["steps"][1]["ratio_to_prior_accepted"] == "3/2"


def test_ratio_uses_most_recent_accepted_step_only():
    r = go([step("a", 10), step("b", 30, accepted=False)])
    assert r["steps"][1]["ratio_to_prior_accepted"] == "3/1" and "escalation_over_2x" in r["steps"][1]["violations"]
    r = go([step("a", 2), step("b", 3, accepted=False), step("c", 3)])
    assert "continued_after_decline" in r["steps"][2]["violations"]


def test_decline_ends_the_ladder_any_later_step_is_violation():
    r = go([step("a", 1, accepted=False), step("b", 1)])
    assert r["allowed"] is False and r["steps"][1]["violations"] == ["continued_after_decline"]
    assert r["first_violation"]["code"] == "continued_after_decline"


def test_decline_as_last_step_is_fine():
    r = go([step("a", 1), step("b", 2, accepted=False)])
    assert r["allowed"] is True


def test_not_freely_chosen_and_no_exit_flagged_in_order():
    r = go([step("a", 1, freely=False, exit_ok=False)])
    assert r["steps"][0]["violations"] == ["not_freely_chosen", "no_exit_available"]
    assert r["allowed"] is False


def test_undisclosed_ladder_is_not_allowed_even_if_steps_clean():
    r = go(ladder_disclosed=False)
    assert r["allowed"] is False and r["first_violation"] == {"index": None, "id": None, "code": "ladder_not_disclosed"}


def test_first_violation_is_earliest_step_violation():
    r = go([step("a", 1, freely=False), step("b", 9)])
    assert r["first_violation"] == {"index": 0, "id": "a", "code": "not_freely_chosen"}


def test_step_count_cap_50_ok_51_refused():
    ok = [step(f"s{i}", 1) for i in range(50)]
    assert go(ok)["allowed"] is True
    refused(lambda: go(ok + [step("x")]), "steps")
    refused(lambda: go([]), "steps")


def test_size_bounds_1_to_1e6():
    assert go([step(size=1)])["allowed"] is True
    assert go([step(size=10**6)])["allowed"] is True
    refused(lambda: go([step(size=0)]), "size")
    refused(lambda: go([step(size=10**6 + 1)]), "size")
    refused(lambda: go([step(size=True)]), "size")
    refused(lambda: go([step(size=1.5)]), "size")


def test_id_length_100_ok_101_refused():
    assert go([step("x" * 100)])["steps"][0]["id"] == "x" * 100
    refused(lambda: go([step("x" * 101)]), "id")
    refused(lambda: go([step(" ")]), "id")


def test_shape_refusals_exact():
    refused(lambda: cc.review([]), "mapping")
    refused(lambda: cc.review({"steps": [step()]}), "ladder_disclosed")
    refused(lambda: cc.review({"steps": [step()], "ladder_disclosed": 1}), "ladder_disclosed")
    refused(lambda: cc.review({"steps": "x", "ladder_disclosed": True}), "steps")
    refused(lambda: cc.review({"steps": [step()], "ladder_disclosed": True, "extra": 1}), "unknown key")
    refused(lambda: go(["x"]), "step 0")
    refused(lambda: go([dict(step(), extra=1)]), "unknown key")
    refused(lambda: go([step("a"), step("a")]), "duplicate")
    refused(lambda: go([step(freely="yes")]), "freely_chosen")
    refused(lambda: go([step(accepted=None)]), "accepted")
    refused(lambda: go([step(exit_ok=0)]), "exit_available")
    d = step(); del d["size"]
    refused(lambda: go([d]), "size")


def test_exact_messages():
    with pytest.raises(cc.ConsistencyError) as e:
        cc.review([])
    assert str(e.value) == "CONSIS102: input must be a mapping"
    with pytest.raises(cc.ConsistencyError) as e:
        go([])
    assert str(e.value) == "CONSIS102: steps must be a list of 1 to 50 records"


def test_limits_text_exact_and_input_not_mutated():
    import copy
    steps = [step("a", 2), step("b", 4)]
    before = copy.deepcopy(steps)
    r = go(steps)
    assert steps == before and r == go(steps)
    assert r["limits"] == [
        "Supplied declarations only; nothing here measures what a person actually feels or will do.",
        "A declined step ends the ladder. Earlier agreement is never a reason to continue.",
        "Not a prediction of compliance and not advice; disclose the whole ladder to the person before the first step.",
    ]


def test_violation_order_and_first_violation_code_is_first_listed():
    r = go([step("z", 1), step("a", 1, accepted=False), step("b", 9, freely=False, exit_ok=False)])
    assert r["steps"][2]["violations"] == ["continued_after_decline", "escalation_over_2x", "not_freely_chosen", "no_exit_available"]
    assert r["first_violation"] == {"index": 2, "id": "b", "code": "continued_after_decline"}


def test_exact_messages_for_ladder_disclosed():
    with pytest.raises(cc.ConsistencyError) as e:
        cc.review({"steps": [step()]})
    assert str(e.value) == "CONSIS102: ladder_disclosed required"
    with pytest.raises(cc.ConsistencyError) as e:
        cc.review({"steps": [step()], "ladder_disclosed": 1})
    assert str(e.value) == "CONSIS102: ladder_disclosed must be true or false"
