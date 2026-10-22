"""Behavior pins for rows 21-26 added after mutation testing showed 18 of 32 mutants survived."""
import math
from datetime import timedelta
import pytest
from app.modules.m20_general_cognitive_worker.metacognition import (
    DecisionFatigueGuard, RoutinePolicy, WorldModelRegistry, _now,
    project_regret, quantify_sacrifice, sunk_cost_choice)


# ---- row 21
def test_evidence_weight_validation_and_sign():
    r = WorldModelRegistry(); r.register("m", {"a": "1"})
    for bad in (-0.1, math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="finite nonnegative"):
            r.apply_evidence("m", supported=True, weight=bad)
    assert r.models["m"].log_odds == 0.0
    r.apply_evidence("m", supported=True, weight=0.0)
    r.apply_evidence("m", supported=False, weight=2.0)
    r.apply_evidence("m", supported=True, weight=0.5)
    assert r.models["m"].log_odds == -1.5


def test_revise_snapshots_old_state_and_replaces_assumptions():
    r = WorldModelRegistry(); m = r.register("m", {"a": "1"})
    r.apply_evidence("m", supported=True, weight=2.0)
    r.revise("m", {"a": "2"})
    r.revise("m", {"a": "3"})
    assert m.version == 3 and m.assumptions == {"a": "3"}
    assert [h["version"] for h in m.history] == [1, 2]
    assert m.history[0]["assumptions"] == {"a": "1"} and m.history[1]["assumptions"] == {"a": "2"}
    assert m.history[0]["log_odds"] == 2.0


def test_registry_copies_assumptions_and_empty_best_is_none():
    r = WorldModelRegistry(); assert r.current_best() is None
    src = {"a": "1"}; m = r.register("m", src); src["a"] = "changed"
    assert m.assumptions == {"a": "1"}
    new = {"a": "2"}; r.revise("m", new); new["a"] = "x"
    assert m.assumptions == {"a": "2"}


# ---- row 23
def guard(max_auto=2, choice="blue"):
    g = DecisionFatigueGuard(); p = g.add_policy(RoutinePolicy("c", choice, max_auto_per_day=max_auto)); return g, p


def test_cap_is_exact_and_counters_advance():
    g, p = guard(2)
    assert [g.decide("c", options=["blue"])["automated"] for _ in range(3)] == [True, True, False]
    assert p.used_today == 2 and g.automated_total == 2
    assert g.decide("c", options=["blue"], routine=True, stakes="low")["automated"] is False


def test_capacity_estimate_counts_automated_decisions_across_policies():
    g, _ = guard(5); g.add_policy(RoutinePolicy("d", "x"))
    assert g.decide("c", options=["blue"])["capacity_preserved_estimate"] == 1
    assert g.decide("d", options=["x"])["capacity_preserved_estimate"] == 2


def test_daily_reset_only_after_more_than_a_day():
    g, p = guard(1)
    assert g.decide("c", options=["blue"])["automated"] is True
    p.last_reset = _now() - timedelta(hours=12)
    assert g.decide("c", options=["blue"])["automated"] is False and p.used_today == 1
    p.last_reset = _now() - timedelta(days=2)
    assert g.decide("c", options=["blue"])["automated"] is True
    assert p.used_today == 1 and _now() - p.last_reset < timedelta(minutes=1)


@pytest.mark.parametrize("kw,opts,typ", [
    ({"routine": False}, ["blue"], "c"), ({"stakes": "high"}, ["blue"], "c"),
    ({}, ["red"], "c"), ({}, ["blue"], "unknown")])
def test_escalation_cases_return_options_and_do_not_consume(kw, opts, typ):
    g, p = guard(1)
    r = g.decide(typ, options=opts, **kw)
    assert r["automated"] is False and r["chosen"] is None and r["escalated_options"] == opts
    assert p.used_today == 0 and g.automated_total == 0


# ---- row 24
def test_regret_math_is_nonnegative_against_scenario_best():
    r = project_regret({"a": {"s1": 10, "s2": 0}, "b": {"s1": 4, "s2": 7}, "c": {"s1": 0, "s2": 9}})
    assert r["regret_table"] == {"a": {"s1": 0, "s2": 9}, "b": {"s1": 6, "s2": 2}, "c": {"s1": 10, "s2": 0}}
    assert r["max_regret"] == {"a": 9, "b": 6, "c": 10} and r["minimax_choice"] == "b"


@pytest.mark.parametrize("opts,msg", [
    ({}, "options required"), ([], "must be a dict"),
    ({"a": {}}, "non-empty scenario dict"), ({"a": 1}, "non-empty scenario dict"),
    ({"a": {"s": True}}, "finite number"), ({"a": {"s": "1"}}, "finite number"),
    ({"a": {"s": math.nan}}, "finite number"), ({"a": {"s": math.inf}}, "finite number"),
    ({"a": {"s": 1}, "b": {"t": 1}}, "same scenario set"),
])
def test_regret_input_validation(opts, msg):
    with pytest.raises(ValueError, match=msg):
        project_regret(opts)


# ---- row 25
def test_sacrifice_ranks_descending_and_cost_is_best_minus_chosen():
    r = quantify_sacrifice({"value": 80}, [{"name": "c", "value": 60}, {"name": "b", "value": 120}, {"name": "d", "value": 90}])
    assert [a["name"] for a in r["ranked_alternatives"]] == ["b", "d", "c"]
    assert r["best_foregone"]["name"] == "b" and r["opportunity_cost"] == 40
    assert quantify_sacrifice({"value": 50}, [{"value": 10}])["opportunity_cost"] == -40
    e = quantify_sacrifice({"value": 5}, [])
    assert e["best_foregone"] is None and e["opportunity_cost"] == 0.0


@pytest.mark.parametrize("chosen,alts", [
    ({}, []), ({"value": True}, []), ({"value": math.nan}, []), ("x", []), ({"value": 1}, "x"),
    ({"value": 1}, [{"name": "a"}]), ({"value": 1}, [{"value": math.inf}]), ({"value": 1}, ["x"]),
])
def test_sacrifice_input_validation(chosen, alts):
    with pytest.raises(ValueError):
        quantify_sacrifice(chosen, alts)


# ---- row 26
def test_sunk_cost_validation_and_ties():
    with pytest.raises(ValueError, match="options required"):
        sunk_cost_choice([])
    for bad in ([{"name": "a"}], [{"forward_value": 1}], ["x"],
                [{"name": "a", "forward_value": 1, "past_investment": math.nan}],
                [{"name": "a", "forward_value": 1, "past_investment": True}],
                [{"name": "a", "forward_value": math.inf}]):
        with pytest.raises(ValueError):
            sunk_cost_choice(bad)
    with pytest.raises(ValueError, match="must be a finite number"):
        sunk_cost_choice([{"name": "a", "forward_value": 1, "past_investment": math.nan}])
    t = sunk_cost_choice([{"name": "a", "forward_value": 5}, {"name": "b", "forward_value": 5}])
    assert t["recommended"] == "a" and t["sunk_cost_influenced"] is False


def test_sunk_cost_uses_past_investment_only_for_the_naive_comparison():
    r = sunk_cost_choice([{"name": "x", "forward_value": 10, "past_investment": 900},
                          {"name": "y", "forward_value": 50}])
    assert r["recommended"] == "y" and r["sunk_cost_influenced"] is True and "'x'" in r["explanation"]
    same = sunk_cost_choice([{"name": "x", "forward_value": 50, "past_investment": 900},
                             {"name": "y", "forward_value": 10}])
    assert same["recommended"] == "x" and same["sunk_cost_influenced"] is False and "irrelevant" in same["explanation"]


def test_daily_reset_boundary_is_exactly_one_day_exclusive(monkeypatch):
    from datetime import datetime, timezone
    from app.modules.m20_general_cognitive_worker import metacognition as m
    fixed = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(m, "_now", lambda: fixed)
    g, p = guard(1)
    assert g.decide("c", options=["blue"])["automated"] is True
    p.last_reset = fixed - timedelta(days=1)  # exactly one day: no reset
    assert g.decide("c", options=["blue"])["automated"] is False
    assert p.used_today == 1 and p.last_reset == fixed - timedelta(days=1)
    p.last_reset = fixed - timedelta(days=1, microseconds=1)  # just over: reset
    assert g.decide("c", options=["blue"])["automated"] is True
    assert p.used_today == 1 and p.last_reset == fixed


def test_sunk_cost_exact_comparison_with_huge_finite_values():
    big = 1.5e308
    r = sunk_cost_choice([{"name": "x", "forward_value": big, "past_investment": big},
                          {"name": "y", "forward_value": 1.6e308, "past_investment": 1.6e308}])
    assert r["recommended"] == "y" and r["sunk_cost_influenced"] is False
    assert "irrelevant" in r["explanation"]


# ================= v3 additions: coverage for registry reads, full-input validation and overflow paths =========
from datetime import datetime, timezone
from app.modules.m20_general_cognitive_worker import metacognition as _meta
from app.modules.m20_general_cognitive_worker.metacognition import WorldModel

T0 = datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc)
T1 = datetime(2026, 3, 5, 6, 7, 8, tzinfo=timezone.utc)


def test_registry_register_returns_stored_model_with_initial_state():
    r = WorldModelRegistry()
    m = r.register("m", {"a": "1"})
    assert r.models["m"] is m and isinstance(m, WorldModel)
    assert (m.name, m.version, m.log_odds, m.history) == ("m", 1, 0.0, [])
    assert m.posterior is None
    m2 = r.register("m", {"b": "2"})                 # re-registering replaces
    assert r.models["m"] is m2 and m2 is not m and m2.assumptions == {"b": "2"}


def test_apply_evidence_default_weight_and_return_value_and_timestamp(monkeypatch):
    r = WorldModelRegistry(); m = r.register("m", {})
    monkeypatch.setattr(_meta, "_now", lambda: T1)
    assert r.apply_evidence("m", supported=True) is m and m.log_odds == 1.0      # default weight 1.0
    assert r.apply_evidence("m", supported=False) is m and m.log_odds == 0.0
    r.apply_evidence("m", supported=False)
    assert m.log_odds == -1.0 and m.updated_at == T1
    with pytest.raises(KeyError):
        r.apply_evidence("missing", supported=True)


def test_revise_returns_model_records_iso_timestamp_and_updates_time(monkeypatch):
    r = WorldModelRegistry(); m = r.register("m", {"a": "1"})
    m.updated_at = T0
    monkeypatch.setattr(_meta, "_now", lambda: T1)
    out = r.revise("m", {"a": "2"})
    assert out is m and m.updated_at == T1 and m.version == 2
    assert m.history == [{"version": 1, "assumptions": {"a": "1"}, "log_odds": 0.0, "at": T0.isoformat()}]
    assert isinstance(m.history[0]["at"], str)
    m.history[0]["assumptions"]["a"] = "mutated"       # snapshot is a copy of the old assumptions
    r.revise("m", {"a": "3"})
    assert m.history[1]["assumptions"] == {"a": "2"} and m.history[1]["at"] == T1.isoformat()
    with pytest.raises(KeyError):
        r.revise("missing", {})


def test_current_best_is_highest_log_odds_first_on_ties_and_tracks_updates():
    r = WorldModelRegistry()
    a = r.register("a", {}); b = r.register("b", {}); c = r.register("c", {})
    assert r.current_best() is a                      # all tied at 0: first registered
    r.apply_evidence("b", supported=True, weight=2.0)
    assert r.current_best() is b
    r.apply_evidence("c", supported=True, weight=2.0)
    assert r.current_best() is b                      # tie b/c: first registered wins
    r.apply_evidence("a", supported=True, weight=3.0)
    assert r.current_best() is a
    r.apply_evidence("a", supported=False, weight=10.0)
    assert r.current_best() is b
    only = WorldModelRegistry(); x = only.register("x", {}); only.apply_evidence("x", supported=False, weight=5.0)
    assert only.current_best() is x                   # a lone negative model is still the best


# ---- row 24 v3
HUGE = 10 ** 400


@pytest.mark.parametrize("opts", [
    {"a": {"s1": 1, "s2": 2}, "b": {"s1": True, "s2": 2}},          # second option, first scenario
    {"a": {"s1": 1, "s2": 2}, "b": {"s1": 1, "s2": "2"}},           # second option, second scenario
    {"a": {"s1": 1, "s2": math.nan}, "b": {"s1": 1, "s2": 2}},      # first option, second scenario
    {"a": {"s1": 1, "s2": 2}, "b": {"s1": 1, "s2": math.inf}},
    {"a": {"s1": 1, "s2": 2}, "b": {"s1": 1, "s2": -math.inf}},
    {"a": {"s1": 1, "s2": 2}, "b": {"s1": HUGE, "s2": 2}},          # int too large for float
    {"a": {"s1": -HUGE}},
    {"a": {"s1": 1}, "b": {"s1": 1, "s2": 2}},                      # unequal scenario sets
    {"a": {"s1": 1}, "b": {}},                                      # empty second table
    {"a": {"s1": 1}, "b": 5},
])
def test_regret_validates_every_option_and_scenario(opts):
    with pytest.raises(ValueError):
        project_regret(opts)


def test_regret_messages_name_the_offending_entry():
    with pytest.raises(ValueError, match=r"payoff 'b'/'s2' must be a finite number"):
        project_regret({"a": {"s1": 1, "s2": 2}, "b": {"s1": 1, "s2": "2"}})
    with pytest.raises(ValueError, match=r"payoffs for 'b' must be a non-empty scenario dict"):
        project_regret({"a": {"s1": 1}, "b": {}})
    with pytest.raises(ValueError, match=r"payoff 'a'/'s1' must be a finite number"):
        project_regret({"a": {"s1": HUGE}})


def test_regret_single_option_large_ints_and_overflowing_derived_regret():
    only = project_regret({"solo": {"s1": 5, "s2": -3}})
    assert only["regret_table"] == {"solo": {"s1": 0, "s2": 0}} and only["max_regret"] == {"solo": 0}
    assert only["minimax_choice"] == "solo"
    big = project_regret({"a": {"s": 10 ** 300}, "b": {"s": -10 ** 300}})      # exact int arithmetic, no overflow
    assert big["regret_table"]["b"]["s"] == 2 * 10 ** 300
    with pytest.raises(ValueError, match="derived regret exceeds finite representation"):
        project_regret({"a": {"s": 1.7e308}, "b": {"s": -1.7e308}})
    # scenario order follows the first option; the table covers every scenario of every option
    r = project_regret({"a": {"s2": 1.0, "s1": 5.0}, "b": {"s1": 2.0, "s2": 4.0}})
    assert list(r["regret_table"]["a"]) == ["s2", "s1"]
    assert r["regret_table"] == {"a": {"s2": 3.0, "s1": 0.0}, "b": {"s2": 0.0, "s1": 3.0}}


# ---- row 25 v3
def test_sacrifice_messages_types_and_overflow():
    with pytest.raises(ValueError, match="chosen must be a dict and alternatives a list"):
        quantify_sacrifice([("value", 1)], [])
    with pytest.raises(ValueError, match="chosen must be a dict and alternatives a list"):
        quantify_sacrifice({"value": 1}, ({"value": 2},))
    with pytest.raises(ValueError, match="chosen requires a finite numeric 'value'"):
        quantify_sacrifice({"name": "c"}, [{"value": 1}])
    with pytest.raises(ValueError, match=r"alternatives\[1\] requires a finite numeric 'value'"):
        quantify_sacrifice({"value": 1}, [{"value": 2}, {"value": "3"}])
    for bad in (True, False, "7", None, HUGE, -HUGE, math.nan, -math.inf):
        with pytest.raises(ValueError, match="requires a finite numeric"):
            quantify_sacrifice({"value": bad}, [])
        with pytest.raises(ValueError, match=r"alternatives\[0\] requires"):
            quantify_sacrifice({"value": 1}, [{"value": bad}])
    with pytest.raises(ValueError, match="derived opportunity cost exceeds finite representation"):
        quantify_sacrifice({"value": -1.7e308}, [{"value": 1.7e308}])


def test_sacrifice_returns_same_objects_stable_ranking_and_does_not_reorder_input():
    chosen = {"name": "c", "value": 3.0}
    alts = [{"name": "p", "value": 5.0}, {"name": "q", "value": 9.0}, {"name": "r", "value": 5.0}]
    r = quantify_sacrifice(chosen, alts)
    assert r["chosen"] is chosen and r["best_foregone"] is alts[1]
    assert [a["name"] for a in r["ranked_alternatives"]] == ["q", "p", "r"]       # ties keep input order
    assert [a["name"] for a in alts] == ["p", "q", "r"]
    assert r["opportunity_cost"] == 6.0
    assert set(r) == {"chosen", "best_foregone", "opportunity_cost", "ranked_alternatives"}


# ---- row 26 v3
@pytest.mark.parametrize("opts,msg", [
    ([{"name": "a", "forward_value": 1}, {"name": "b"}], r"options\[1\] requires 'name' and 'forward_value' keys"),
    ([{"name": "a", "forward_value": 1}, {"forward_value": 1}], r"options\[1\] requires"),
    ([{"name": "a", "forward_value": 1}, "x"], r"options\[1\] requires"),
    ([{"name": "a", "forward_value": 1}, {"name": "b", "forward_value": "5"}], r"options\[1\]\['forward_value'\] must be a finite number"),
    ([{"name": "a", "forward_value": "5"}], r"options\[0\]\['forward_value'\] must be a finite number"),
    ([{"name": "a", "forward_value": True}], "finite number"),
    ([{"name": "a", "forward_value": HUGE}], "finite number"),
    ([{"name": "a", "forward_value": -HUGE}], "finite number"),
    ([{"name": "a", "forward_value": 1, "past_investment": HUGE}], r"options\[0\]\['past_investment'\] must be a finite number"),
    ([{"name": "a", "forward_value": 1}, {"name": "b", "forward_value": 1, "past_investment": "9"}], r"options\[1\]\['past_investment'\]"),
    ([{"name": "a", "forward_value": 1}, {"name": "b", "forward_value": 1, "past_investment": math.inf}], r"options\[1\]\['past_investment'\]"),
    ([{"name": "a", "forward_value": 1}, {"name": "b", "forward_value": 1, "past_investment": None}], r"options\[1\]\['past_investment'\]"),
    ([{"name": "a", "forward_value": 1}, {"name": "b", "forward_value": math.nan}], r"options\[1\]\['forward_value'\]"),
])
def test_sunk_cost_validates_every_option_with_indexed_messages(opts, msg):
    with pytest.raises(ValueError, match=msg):
        sunk_cost_choice(opts)


def test_sunk_cost_default_and_negative_past_investment_and_explanations():
    d = sunk_cost_choice([{"name": "a", "forward_value": 5}, {"name": "b", "forward_value": 3}])      # past defaults to 0
    assert d["recommended"] == "a" and d["sunk_cost_influenced"] is False
    assert d["explanation"] == "forward-looking value picks 'a'; past investment is irrelevant"
    neg = sunk_cost_choice([{"name": "x", "forward_value": 10, "past_investment": -900}, {"name": "y", "forward_value": 5}])
    assert neg["recommended"] == "x" and neg["sunk_cost_influenced"] is True
    assert neg["explanation"] == "including past investment would have picked 'y'; forward-looking value alone picks 'x'"
    zero = sunk_cost_choice([{"name": "x", "forward_value": 10, "past_investment": 0.0}, {"name": "y", "forward_value": 5, "past_investment": 4}])
    assert zero["sunk_cost_influenced"] is False
    flip = sunk_cost_choice([{"name": "x", "forward_value": 5, "past_investment": 0}, {"name": "y", "forward_value": 3, "past_investment": 2.5}])
    assert flip["sunk_cost_influenced"] is True and flip["recommended"] == "x"
    tie = sunk_cost_choice([{"name": "x", "forward_value": 5, "past_investment": 0}, {"name": "y", "forward_value": 3, "past_investment": 2}])
    assert tie["recommended"] == "x" and tie["sunk_cost_influenced"] is False        # exact naive tie: first wins
    assert set(sunk_cost_choice([{"name": "a", "forward_value": 1}])) == {"recommended", "sunk_cost_influenced", "explanation"}


def test_regret_huge_int_difference_stays_exact_int_without_overflow_error():
    r = project_regret({"a": {"s": 10 ** 308}, "b": {"s": -10 ** 308}})
    assert r["regret_table"]["b"]["s"] == 2 * 10 ** 308 and isinstance(r["regret_table"]["b"]["s"], int)
    assert r["max_regret"] == {"a": 0, "b": 2 * 10 ** 308} and r["minimax_choice"] == "a"


def test_sunk_cost_missing_past_investment_counts_as_zero_when_others_have_some():
    r = sunk_cost_choice([{"name": "x", "forward_value": 3, "past_investment": 1.5}, {"name": "y", "forward_value": 4}])
    assert r["recommended"] == "y" and r["sunk_cost_influenced"] is True       # naive: x 4.5 beats y 4 only if y's past is 0
    assert "'x'" in r["explanation"]


def test_sunk_cost_missing_past_investment_is_exactly_zero_not_negative():
    r = sunk_cost_choice([{"name": "a", "forward_value": 5, "past_investment": -0.5}, {"name": "b", "forward_value": 5}])
    assert r["sunk_cost_influenced"] is True      # b's missing past counts as 0 (naive 5 > a's 4.5); a -1.0 default would flip this


# ---- v5: default-value sweep. Each pin uses exact (Fraction) comparisons, so it excludes EVERY constant
# default on its side of the true value (not just the sampled mutants), but it does not exclude a default
# that is computed from the option itself.
_TINY = 5e-324  # smallest positive float; Fraction comparison keeps it exact


@pytest.mark.parametrize("opts,expect_influenced,expect_recommended", [
    # base default 0: a's past -0.0005 makes naive pick b -> influenced. Any default d<0 ties/loses b: not influenced.
    ([{"name": "a", "forward_value": 5, "past_investment": -0.0005}, {"name": "b", "forward_value": 5}], True, "a"),
    ([{"name": "a", "forward_value": 5, "past_investment": -_TINY}, {"name": "b", "forward_value": 5}], True, "a"),
    # base: a's naive 5.1 beats b's 5 -> not influenced. Any default d>=0.1 would let b (first-listed) win -> influenced.
    ([{"name": "a", "forward_value": 5, "past_investment": 0.1}, {"name": "b", "forward_value": 5}], False, "a"),
    ([{"name": "b", "forward_value": 5}, {"name": "a", "forward_value": 5, "past_investment": _TINY}], True, "b"),
])
def test_sunk_cost_default_past_investment_is_exactly_zero_on_both_sides(opts, expect_influenced, expect_recommended):
    r = sunk_cost_choice(opts)
    assert r["sunk_cost_influenced"] is expect_influenced and r["recommended"] == expect_recommended


def test_world_model_fresh_defaults_are_exact():
    m = WorldModelRegistry().register("m", {"a": "1"})
    assert m.log_odds == 0.0 and m.version == 1 and m.history == [] and m.posterior is None
    assert WorldModel(name="n", assumptions={}).log_odds == 0.0 and WorldModel(name="n", assumptions={}).version == 1


def test_apply_evidence_default_weight_is_exactly_one_for_both_signs():
    r = WorldModelRegistry(); m = r.register("m", {})
    r.apply_evidence("m", supported=True)
    assert m.log_odds == 1.0            # exact equality excludes every other constant default
    r.apply_evidence("m", supported=False); r.apply_evidence("m", supported=False)
    assert m.log_odds == -1.0
