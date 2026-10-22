"""Exact-message, payload-key and default-value pins for rows 21 and 23-26 (metacognition.py).
Messages are compared with str(exc) == text (not match=, which is an unanchored re.search). Tests only."""
import math
from datetime import timedelta
import pytest
from app.modules.m20_general_cognitive_worker.metacognition import (
    DecisionFatigueGuard, RoutinePolicy, WorldModel, WorldModelRegistry,
    project_regret, quantify_sacrifice, sunk_cost_choice)


def _msg(fn, *a, **k):
    with pytest.raises(ValueError) as ei:
        fn(*a, **k)
    return str(ei.value)


# ---- row 21
def test_world_model_defaults():
    m = WorldModel(name="x", assumptions={})
    assert m.version == 1 and m.log_odds == 0.0 and m.history == [] and m.posterior is None


@pytest.mark.parametrize("w", [-1.0, math.nan, math.inf, -math.inf])
def test_apply_evidence_weight_message_is_exact(w):
    r = WorldModelRegistry(); r.register("m", {})
    assert _msg(r.apply_evidence, "m", supported=True, weight=w) == "finite nonnegative supplied weight required"


def test_revise_history_entry_has_exactly_the_four_keys_and_prior_values():
    r = WorldModelRegistry(); m = r.register("m", {"a": "1"})
    r.apply_evidence("m", supported=True, weight=2.5)
    before = m.updated_at.isoformat()
    r.revise("m", {"a": "2"})
    assert m.history == [{"version": 1, "assumptions": {"a": "1"}, "log_odds": 2.5, "at": before}]
    assert set(m.history[0]) == {"version", "assumptions", "log_odds", "at"}


# ---- row 23
def test_routine_policy_defaults():
    p = RoutinePolicy("t", "a")
    assert p.max_auto_per_day == 10 and p.used_today == 0


def test_default_cap_is_ten_automations_then_escalates():
    g = DecisionFatigueGuard(); g.add_policy(RoutinePolicy("t", "a"))
    out = [g.decide("t", options=["a", "b"])["automated"] for _ in range(12)]
    assert out == [True] * 10 + [False] * 2


def test_decide_payload_keys_and_reason_strings_are_exact():
    g = DecisionFatigueGuard(); g.add_policy(RoutinePolicy("t", "a"))
    ok = g.decide("t", options=["a", "b"])
    assert ok == {"automated": True, "chosen": "a", "reason": "routine policy for t", "capacity_preserved_estimate": 1}
    esc = g.decide("t", options=["b"])
    assert esc == {"automated": False, "chosen": None,
                   "reason": "no policy / non-routine / high stakes / daily cap reached", "escalated_options": ["b"]}
    assert g.decide("none", options=["a"]) == {"automated": False, "chosen": None,
        "reason": "no policy / non-routine / high stakes / daily cap reached", "escalated_options": ["a"]}


def test_default_stakes_is_low_and_other_stakes_escalate():
    g = DecisionFatigueGuard(); g.add_policy(RoutinePolicy("t", "a"))
    assert g.decide("t", options=["a"])["automated"] is True
    assert g.decide("t", options=["a"], stakes="low")["automated"] is True
    assert g.decide("t", options=["a"], stakes="high")["automated"] is False
    assert g.decide("t", options=["a"], routine=False)["automated"] is False


# ---- row 24
def test_regret_payload_keys_and_values():
    out = project_regret({"a": {"s": 1, "t": 5}, "b": {"s": 3, "t": 2}})
    assert out == {"regret_table": {"a": {"s": 2, "t": 0}, "b": {"s": 0, "t": 3}},
                   "max_regret": {"a": 2, "b": 3}, "minimax_choice": "a"}


@pytest.mark.parametrize("arg,text", [
    ([1], "options must be a dict of option -> scenario payoffs"),
    ({}, "options required"),
    ({"a": {}}, "payoffs for 'a' must be a non-empty scenario dict"),
    ({"a": 3}, "payoffs for 'a' must be a non-empty scenario dict"),
    ({"a": {"s": True}}, "payoff 'a'/'s' must be a finite number"),
    ({"a": {"s": "1"}}, "payoff 'a'/'s' must be a finite number"),
    ({"a": {"s": math.nan}}, "payoff 'a'/'s' must be a finite number"),
    ({"a": {"s": math.inf}}, "payoff 'a'/'s' must be a finite number"),
    ({"a": {"s": 10 ** 400}}, "payoff 'a'/'s' must be a finite number"),
    ({"a": {"s": 1}, "b": {"t": 1}}, "all options must declare the same scenario set"),
    ({"a": {"s": 1.7e308}, "b": {"s": -1.7e308}}, "derived regret exceeds finite representation"),
])
def test_regret_messages_are_exact(arg, text):
    assert _msg(project_regret, arg) == text


# ---- row 25
def test_sacrifice_payload_keys_and_empty_alternatives():
    out = quantify_sacrifice({"value": 3, "label": "c"}, [{"value": 5, "label": "x"}, {"value": 9, "label": "y"}])
    assert out == {"chosen": {"value": 3, "label": "c"}, "best_foregone": {"value": 9, "label": "y"},
                   "opportunity_cost": 6, "ranked_alternatives": [{"value": 9, "label": "y"}, {"value": 5, "label": "x"}]}
    out = quantify_sacrifice({"value": 3}, [])
    assert out == {"chosen": {"value": 3}, "best_foregone": None, "opportunity_cost": 0.0, "ranked_alternatives": []}


@pytest.mark.parametrize("chosen,alts,text", [
    ([1], [], "chosen must be a dict and alternatives a list"),
    ({"value": 1}, (), "chosen must be a dict and alternatives a list"),
    ({}, [], "chosen requires a finite numeric 'value'"),
    ({"value": True}, [], "chosen requires a finite numeric 'value'"),
    ({"value": math.nan}, [], "chosen requires a finite numeric 'value'"),
    ({"value": 10 ** 400}, [], "chosen requires a finite numeric 'value'"),
    ({"value": 1}, [{"value": 1}, {}], "alternatives[1] requires a finite numeric 'value'"),
    ({"value": 1}, [3], "alternatives[0] requires a finite numeric 'value'"),
    ({"value": 1}, [{"value": math.inf}], "alternatives[0] requires a finite numeric 'value'"),
    ({"value": -1.7e308}, [{"value": 1.7e308}], "derived opportunity cost exceeds finite representation"),
])
def test_sacrifice_messages_are_exact(chosen, alts, text):
    assert _msg(quantify_sacrifice, chosen, alts) == text


# ---- row 26
def test_sunk_cost_payload_and_explanations_are_exact():
    inf = sunk_cost_choice([{"name": "A", "forward_value": 10, "past_investment": 0},
                            {"name": "B", "forward_value": 5, "past_investment": 100}])
    assert inf == {"recommended": "A", "sunk_cost_influenced": True,
                   "explanation": "including past investment would have picked 'B'; forward-looking value alone picks 'A'"}
    plain = sunk_cost_choice([{"name": "A", "forward_value": 10}, {"name": "B", "forward_value": 5}])
    assert plain == {"recommended": "A", "sunk_cost_influenced": False,
                     "explanation": "forward-looking value picks 'A'; past investment is irrelevant"}


@pytest.mark.parametrize("arg,text", [
    ([], "options required"),
    ([3], "options[0] requires 'name' and 'forward_value' keys"),
    ([{"name": "A", "forward_value": 1}, {"forward_value": 1}], "options[1] requires 'name' and 'forward_value' keys"),
    ([{"name": "A"}], "options[0] requires 'name' and 'forward_value' keys"),
    ([{"name": "A", "forward_value": math.nan}], "options[0]['forward_value'] must be a finite number"),
    ([{"name": "A", "forward_value": True}], "options[0]['forward_value'] must be a finite number"),
    ([{"name": "A", "forward_value": 1}, {"name": "B", "forward_value": 1, "past_investment": math.inf}],
     "options[1]['past_investment'] must be a finite number"),
    ([{"name": "A", "forward_value": 1, "past_investment": "x"}], "options[0]['past_investment'] must be a finite number"),
    ([{"name": "A", "forward_value": 10 ** 400}], "options[0]['forward_value'] must be a finite number"),
])
def test_sunk_cost_messages_are_exact(arg, text):
    assert _msg(sunk_cost_choice, arg) == text
