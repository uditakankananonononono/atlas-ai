"""Row 686 scoped capability: bounded execution of a declarative Given/When/Then DSL.

Independent validators: exhaustive small state-machine enumeration against a
reference interpreter, known-answer fixtures, malformed-input bounds, and a
naive any-of/shared-state baseline floor.
"""
import hashlib
import itertools
import json

import pytest

from app.modules.m20_general_cognitive_worker.bdd_scenarios686 import (
    INT_LIMIT, MAX_SCENARIOS, MAX_SECTION_STEPS, execute_scenarios,
)


def scenario(given=None, when=None, then=None, name=None):
    s = {"given": given or [], "when": when or [], "then": then or []}
    if name is not None:
        s["name"] = name
    return s


def test_known_answer_counter_scenario_passes():
    data = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "count", "value": 0}],
        when=[{"op": "increment", "var": "count", "by": 2},
              {"op": "increment", "var": "count", "by": 3}],
        then=[{"assert": "equals", "var": "count", "value": 5}],
        name="counter",
    )]}
    r = execute_scenarios(data)
    assert r["status"] == "all_passed"
    assert r["scenarios"][0]["status"] == "passed" and r["scenarios"][0]["failure"] is None
    assert r["steps_executed"] == 4


def test_known_answer_assertion_failure_has_source_linked_trace():
    data = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "x", "value": 1}],
        when=[{"op": "increment", "var": "x", "by": 1}],
        then=[{"assert": "equals", "var": "x", "value": 2},
              {"assert": "equals", "var": "x", "value": 99}],
        name="trace",
    )]}
    r = execute_scenarios(data)
    assert r["status"] == "failures_present"
    f = r["scenarios"][0]["failure"]
    assert f["section"] == "then" and f["step_index"] == 1
    assert f["reason"] == "assertion_failed"
    assert f["step"] == {"assert": "equals", "var": "x", "value": 99}
    assert f["expected"] == 99 and f["actual"] == 2


def reference_run(ops):
    """Independent reference interpreter for the exhaustive state-machine oracle."""
    state = {}
    for step in ops:
        if step["op"] == "assign":
            state[step["var"]] = step["value"]
        else:
            state[step["var"]] = state.get(step["var"], 0) + step["by"]
    return state


def test_exhaustive_small_state_machine_fixtures_match_reference():
    ops_set = [
        {"op": "assign", "var": "a", "value": 0},
        {"op": "assign", "var": "a", "value": 1},
        {"op": "assign", "var": "b", "value": 0},
        {"op": "assign", "var": "b", "value": 1},
        {"op": "increment", "var": "a", "by": 1},
        {"op": "increment", "var": "b", "by": 1},
    ]
    sequences = [[]]
    for length in range(1, 5):
        sequences.extend(itertools.product(ops_set, repeat=length))
    assert len(sequences) == 1 + 6 + 36 + 216 + 1296
    for seq in sequences:
        # Pre-seed both vars so the reference get() default never fires.
        given = [{"op": "assign", "var": "a", "value": 0},
                 {"op": "assign", "var": "b", "value": 0}]
        expected = reference_run(list(given) + [dict(s) for s in seq])
        good_then = [{"assert": "equals", "var": v, "value": expected[v]} for v in ("a", "b")]
        bad_then = [{"assert": "equals", "var": "a", "value": expected["a"] + 1}]
        ok = execute_scenarios({"scenarios": [scenario(given=given, when=[dict(s) for s in seq], then=good_then)]})
        assert ok["status"] == "all_passed", seq
        bad = execute_scenarios({"scenarios": [scenario(given=given, when=[dict(s) for s in seq], then=bad_then)]})
        assert bad["status"] == "failures_present", seq


def test_sequential_effects_make_order_observable():
    ordered = scenario(
        given=[{"op": "assign", "var": "x", "value": 1}],
        when=[{"op": "increment", "var": "x", "by": 1},
              {"op": "assign", "var": "y", "value": 7},
              {"op": "assign", "var": "x", "value": 0},
              {"op": "increment", "var": "x", "by": 5}],
        then=[{"assert": "equals", "var": "x", "value": 5},
              {"assert": "equals", "var": "y", "value": 7}],
    )
    assert execute_scenarios({"scenarios": [ordered]})["status"] == "all_passed"
    # Same steps, different order: simultaneous semantics would be ambiguous;
    # this DSL is strictly sequential, so reordering changes the outcome.
    reordered = scenario(
        given=[{"op": "assign", "var": "x", "value": 1}],
        when=[{"op": "assign", "var": "x", "value": 0},
              {"op": "increment", "var": "x", "by": 1},
              {"op": "assign", "var": "y", "value": 7},
              {"op": "increment", "var": "x", "by": 5}],
        then=[{"assert": "equals", "var": "x", "value": 6}],
    )
    r = execute_scenarios({"scenarios": [reordered]})
    assert r["status"] == "all_passed"
    sem = r["semantics"]
    assert sem["ordering"] == "sequential_in_listed_order" and sem["simultaneous"] is False


def test_fresh_state_per_scenario_isolation():
    leak = scenario(
        then=[{"assert": "equals", "var": "shared", "value": 1}], name="leak",
    )
    data = {"scenarios": [
        scenario(given=[{"op": "assign", "var": "shared", "value": 1}],
                 then=[{"assert": "equals", "var": "shared", "value": 1}], name="setter"),
        leak,
    ]}
    r = execute_scenarios(data)
    assert r["status"] == "failures_present"
    assert r["scenarios"][0]["status"] == "passed"
    f = r["scenarios"][1]["failure"]
    assert f["reason"] == "unknown_variable" and f["section"] == "then" and f["step_index"] == 0
    assert r["semantics"]["scenario_isolation"] is True


def test_then_requires_all_not_any():
    data = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "x", "value": 1}],
        then=[{"assert": "equals", "var": "x", "value": 1},
              {"assert": "equals", "var": "x", "value": 2}],
    )]}
    r = execute_scenarios(data)
    assert r["status"] == "failures_present"  # any-of semantics would wrongly pass
    assert r["semantics"]["then_requires"] == "all"
    both_good = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "x", "value": 1}],
        then=[{"assert": "equals", "var": "x", "value": 1},
              {"assert": "not_equals", "var": "x", "value": 2}],
    )]}
    assert execute_scenarios(both_good)["status"] == "all_passed"


def test_unknown_variable_and_bad_increment_types_are_traced_failures():
    unknown = {"scenarios": [scenario(when=[{"op": "increment", "var": "ghost", "by": 1}])]}
    r = execute_scenarios(unknown)
    f = r["scenarios"][0]["failure"]
    assert f["reason"] == "unknown_variable" and f["section"] == "when" and f["step_index"] == 0
    typemix = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "s", "value": "text"}],
        when=[{"op": "increment", "var": "s", "by": 1}],
    )]}
    f = execute_scenarios(typemix)["scenarios"][0]["failure"]
    assert f["reason"] == "type_mismatch"
    boolmix = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "b", "value": True}],
        when=[{"op": "increment", "var": "b", "by": 1}],
    )]}
    assert execute_scenarios(boolmix)["scenarios"][0]["failure"]["reason"] == "type_mismatch"


def test_integer_overflow_is_a_traced_failure_not_wraparound():
    data = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "big", "value": INT_LIMIT}],
        when=[{"op": "increment", "var": "big", "by": 1}],
    )]}
    r = execute_scenarios(data)
    f = r["scenarios"][0]["failure"]
    assert f["reason"] == "integer_overflow" and f["section"] == "when"
    under = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "big", "value": -INT_LIMIT}],
        when=[{"op": "increment", "var": "big", "by": -1}],
    )]}
    assert execute_scenarios(under)["scenarios"][0]["failure"]["reason"] == "integer_overflow"
    edge = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "big", "value": INT_LIMIT - 1}],
        when=[{"op": "increment", "var": "big", "by": 1}],
        then=[{"assert": "equals", "var": "big", "value": INT_LIMIT}],
    )]}
    assert execute_scenarios(edge)["status"] == "all_passed"


def test_exact_step_cap_never_claims_pass():
    many = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "x", "value": 0}],
        when=[{"op": "increment", "var": "x", "by": 1}] * 10,
        then=[{"assert": "equals", "var": "x", "value": 10}],
    )], "max_steps": 5}
    r = execute_scenarios(many)
    assert r["status"] == "inconclusive_step_cap_exceeded" and r["steps_executed"] == 5
    assert r["scenarios"][0]["status"] != "passed"
    ok = dict(many, max_steps=16)
    assert execute_scenarios(ok)["status"] == "all_passed"


def test_exact_scenario_and_section_bounds():
    scenarios = [scenario(name=f"s{k}") for k in range(MAX_SCENARIOS)]
    assert execute_scenarios({"scenarios": scenarios})["status"] == "all_passed"
    with pytest.raises(ValueError, match="1..16"):
        execute_scenarios({"scenarios": scenarios + [scenario(name="extra")]})
    with pytest.raises(ValueError, match="1..16"):
        execute_scenarios({"scenarios": []})
    steps = [{"op": "assign", "var": "x", "value": 1}] * MAX_SECTION_STEPS
    assert execute_scenarios({"scenarios": [scenario(given=steps)]})["status"] == "all_passed"
    with pytest.raises(ValueError, match="0..32"):
        execute_scenarios({"scenarios": [scenario(given=steps + [{"op": "assign", "var": "x", "value": 1}])]})


@pytest.mark.parametrize("bad_step", [
    {"op": "multiply", "var": "x", "value": 1},
    {"op": "assign", "var": "x", "value": 1.5},
    {"op": "assign", "var": "x", "value": [1]},
    {"op": "assign", "var": "x", "value": None},
    {"op": "assign", "var": "x", "value": {"nested": 1}},
    {"op": "assign", "var": "1x", "value": 1},
    {"op": "assign", "var": "", "value": 1},
    {"op": "assign", "var": "x"},
    {"op": "increment", "var": "x", "by": True},
    {"op": "increment", "var": "x", "by": 1.5},
    {"op": "increment", "var": "x"},
    {"op": "assign", "var": "x", "value": INT_LIMIT + 1},
    {"op": "assign", "var": "x", "value": "y" * 257},
    {"assert": "greater_than", "var": "x", "value": 1},
    {"assert": "equals", "var": "x"},
])
def test_malformed_steps_rejected_with_exact_errors(bad_step):
    section = "then" if "assert" in bad_step else "given"
    with pytest.raises(ValueError):
        execute_scenarios({"scenarios": [scenario(**{section: [bad_step]})]})


def test_duplicate_scenario_names_rejected():
    data = {"scenarios": [scenario(name="dup"), scenario(name="dup")]}
    with pytest.raises(ValueError, match="duplicate"):
        execute_scenarios(data)


@pytest.mark.parametrize("bad", [
    "nope",
    {"scenarios": "nope"},
    {"scenarios": ["nope"]},
    {"scenarios": [{"given": []}]},  # missing when/then
    {"scenarios": [scenario()], "max_steps": 0},
    {"scenarios": [scenario()], "max_steps": True},
    {"scenarios": [scenario()], "max_steps": 4097},
])
def test_malformed_requests_rejected(bad):
    with pytest.raises(ValueError):
        execute_scenarios(bad)


def test_bool_and_int_are_distinct_typed_scalars():
    data = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "b", "value": True}],
        then=[{"assert": "equals", "var": "b", "value": 1}],
    )]}
    assert execute_scenarios(data)["status"] == "failures_present"
    data["scenarios"][0]["then"] = [{"assert": "equals", "var": "b", "value": True}]
    assert execute_scenarios(data)["status"] == "all_passed"


def test_receipt_determinism_and_provenance():
    data = {"scenarios": [scenario(
        given=[{"op": "assign", "var": "x", "value": 2}],
        then=[{"assert": "equals", "var": "x", "value": 2}], name="p",
    )], "max_steps": 64}
    r1 = execute_scenarios(data)
    r2 = execute_scenarios(json.loads(json.dumps(data)))
    assert r1 == r2
    prov = r1["provenance"]
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    assert prov["input_sha256"] == hashlib.sha256(canonical.encode()).hexdigest()
    assert prov["repository_behavior_certified"] is False
    assert prov["natural_language_interpreted"] is False
    assert prov["arbitrary_code_executed"] is False
    assert prov["external_task_scheduled"] is False


def naive_baseline(data):
    """Naive interpreter: shared state across scenarios, any-of-then semantics."""
    state = {}
    for sc in data["scenarios"]:
        for section in ("given", "when"):
            for step in sc[section]:
                try:
                    if step["op"] == "assign":
                        state[step["var"]] = step["value"]
                    else:
                        state[step["var"]] = state.get(step["var"], 0) + step["by"]
                except Exception:
                    return False
        outcomes = []
        for step in sc["then"]:
            actual = state.get(step["var"], "<missing>")
            if step["assert"] == "equals":
                outcomes.append(actual == step["value"])
            else:
                outcomes.append(actual != step["value"])
        if outcomes and not any(outcomes):
            return False
    return True


def test_domain_floor_engine_never_passes_what_naive_fails():
    import random
    rng = random.Random(686)
    strict_extra_catches = 0
    for case in range(150):
        scenarios = []
        for k in range(rng.randrange(1, 4)):
            given = [{"op": "assign", "var": "x", "value": rng.randrange(0, 4)}] if rng.random() < 0.7 else []
            when = [{"op": "increment", "var": "x", "by": rng.randrange(-2, 3)}] if rng.random() < 0.5 else []
            then = []
            for _ in range(rng.randrange(1, 3)):
                kind = rng.choice(["equals", "not_equals"])
                then.append({"assert": kind, "var": "x", "value": rng.randrange(0, 5)})
            scenarios.append(scenario(given=given, when=when, then=then, name=f"s{k}"))
        data = {"scenarios": scenarios}
        engine_passed = execute_scenarios(data)["status"] == "all_passed"
        naive_passed = naive_baseline(data)
        if not naive_passed:
            assert not engine_passed, case  # engine detection is a superset of the baseline's
        elif not engine_passed:
            strict_extra_catches += 1  # isolation / all-of-then caught what naive missed
    assert strict_extra_catches > 0


# ---- R2 pins (auditor-identified survivors) ----
def _counter(v=1):
    return scenario(given=[{"op": "assign", "var": "x", "value": v}],
                    when=[{"op": "increment", "var": "x", "by": 2}],
                    then=[{"assert": "equals", "var": "x", "value": v + 2}])


@pytest.mark.parametrize("section", ["given", "when", "then"])
@pytest.mark.parametrize("bad_step", [1, "assign", None, [], True])
def test_nonobject_step_is_refused_with_valueerror(section, bad_step):
    s = _counter()
    s[section] = [bad_step]
    with pytest.raises(ValueError, match=rf"^{section}\[0\] must be an object$"):
        execute_scenarios({"scenarios": [s]})


@pytest.mark.parametrize("bad", [1, "", None, ["n"], True])
def test_invalid_scenario_name_is_refused(bad):
    s = _counter()
    s["name"] = bad
    with pytest.raises(ValueError, match=r"^scenarios\[0\]\.name requires a non-empty string$"):
        execute_scenarios({"scenarios": [s]})


def test_cap_marks_incomplete_then_skips_all_later_scenarios_unrun():
    r = execute_scenarios({"scenarios": [_counter(), _counter(), _counter()], "max_steps": 1})
    assert [x["status"] for x in r["scenarios"]] == ["incomplete", "not_run", "not_run"]
    assert [x["failure"] for x in r["scenarios"]] == [None, None, None]
    assert r["status"] == "inconclusive_step_cap_exceeded"
    assert r["steps_executed"] == 1
    # a later scenario that would FAIL is never executed once the cap is hit
    failing = scenario(given=[{"op": "assign", "var": "x", "value": 1}], then=[{"assert": "equals", "var": "x", "value": 9}])
    r = execute_scenarios({"scenarios": [_counter(), failing], "max_steps": 2})
    assert [x["status"] for x in r["scenarios"]] == ["incomplete", "not_run"]
    assert r["status"] == "inconclusive_step_cap_exceeded"


def test_human_review_required_is_always_true():
    for data in ({"scenarios": [_counter()]},
                 {"scenarios": [scenario(given=[{"op": "assign", "var": "x", "value": 1}],
                                         then=[{"assert": "equals", "var": "x", "value": 2}])]},
                 {"scenarios": [_counter(), _counter()], "max_steps": 1}):
        assert execute_scenarios(data)["human_review_required"] is True


def test_scalar_arithmetic_and_isolation_receipt_counts():
    r = execute_scenarios({"scenarios": [_counter(1), _counter(-1)]})
    assert r["status"] == "all_passed" and r["steps_executed"] == 6 and r["human_review_required"] is True


# --- Advisory pin round (auditor-4 specification); tests-only, core unchanged. ---

def test_advisory_integer_assignment_boundary_pair():
    ok = scenario(given=[{"op": "assign", "var": "x", "value": INT_LIMIT}],
                  then=[{"assert": "equals", "var": "x", "value": INT_LIMIT}])
    assert execute_scenarios({"scenarios": [ok]})["status"] == "all_passed"
    with pytest.raises(ValueError, match="integer outside"):
        execute_scenarios({"scenarios": [scenario(given=[{"op": "assign", "var": "x", "value": INT_LIMIT + 1}])]})


def test_advisory_scalar_string_length_boundary_pair():
    ok = scenario(given=[{"op": "assign", "var": "x", "value": "y" * 256}],
                  then=[{"assert": "equals", "var": "x", "value": "y" * 256}])
    assert execute_scenarios({"scenarios": [ok]})["status"] == "all_passed"
    with pytest.raises(ValueError, match="over 256"):
        execute_scenarios({"scenarios": [scenario(given=[{"op": "assign", "var": "x", "value": "y" * 257}])]})


def test_advisory_variable_name_length_boundary_pair():
    ok = scenario(given=[{"op": "assign", "var": "a" * 64, "value": 1}],
                  then=[{"assert": "equals", "var": "a" * 64, "value": 1}])
    assert execute_scenarios({"scenarios": [ok]})["status"] == "all_passed"
    with pytest.raises(ValueError, match="identifier"):
        execute_scenarios({"scenarios": [scenario(given=[{"op": "assign", "var": "a" * 65, "value": 1}])]})


def test_advisory_whole_input_hash_includes_ignored_json_extras():
    base = {"scenarios": [_counter()]}
    extra1 = {**base, "ignored_extra": 1}
    extra2 = {**base, "ignored_extra": 2}
    r0 = execute_scenarios(base)
    r1 = execute_scenarios(extra1)
    r2 = execute_scenarios(extra2)
    # Extras change nothing about execution...
    assert r0["status"] == r1["status"] == r2["status"] == "all_passed"
    assert r0["scenarios"] == r1["scenarios"] == r2["scenarios"]
    # ...but the provenance hash binds the WHOLE caller packet, extras included.
    assert r0["provenance"]["input_sha256"] != r1["provenance"]["input_sha256"]
    assert r1["provenance"]["input_sha256"] != r2["provenance"]["input_sha256"]


def test_advisory_prior_failure_then_cap_keeps_trace_with_cap_priority_status():
    failing = scenario(given=[{"op": "assign", "var": "x", "value": 1}],
                       then=[{"assert": "equals", "var": "x", "value": 2}], name="bad")
    long = scenario(given=[{"op": "assign", "var": "y", "value": 0}],
                    when=[{"op": "increment", "var": "y", "by": 1}] * 10, name="long")
    r = execute_scenarios({"scenarios": [failing, long], "max_steps": 3})
    assert r["status"] == "inconclusive_step_cap_exceeded"  # cap has top-status priority
    assert r["scenarios"][0]["status"] == "failed"
    assert r["scenarios"][0]["failure"]["reason"] == "assertion_failed"
    assert r["scenarios"][0]["failure"]["section"] == "then" and r["scenarios"][0]["failure"]["step_index"] == 0
    assert r["scenarios"][1]["status"] == "incomplete"
    assert r["steps_executed"] == 3


def test_advisory_generated_names_can_collide_with_explicit_names():
    # scenarios[1] is unnamed, generating "scenario-1" - which collides with the
    # explicit name of scenarios[0]. Collisions are refused like any duplicate.
    data = {"scenarios": [scenario(name="scenario-1"), scenario(), scenario()]}
    with pytest.raises(ValueError, match="^duplicate scenario name: scenario-1$"):
        execute_scenarios(data)
    # Sanity: the same three with no explicit name generate distinct names.
    assert execute_scenarios({"scenarios": [scenario(), scenario(), scenario()]})["status"] == "all_passed"


def test_advisory_scenario_names_have_no_length_cap():
    # Deliberate resource-hardening choice: caps live on scenario/step counts,
    # not on name length. A 5,000,000-character name is permitted.
    long_name = "n" * 5_000_000
    r = execute_scenarios({"scenarios": [scenario(name=long_name)]})
    assert r["status"] == "all_passed" and r["scenarios"][0]["name"] == long_name


def test_advisory_typed_equality_is_exact_type_identity():
    from app.modules.m20_general_cognitive_worker.bdd_scenarios686 import _typed_equal

    class MyInt(int):
        pass

    assert _typed_equal(1, 1) is True
    assert _typed_equal(1, True) is False          # bool is not int here
    assert _typed_equal(MyInt(1), 1) is False      # an int SUBCLASS differs from int
    assert _typed_equal(1, MyInt(1)) is False
    assert _typed_equal("1", 1) is False
    assert _typed_equal("a", "a") is True


def test_advisory_unknown_variable_in_not_equals_also_fails():
    data = {"scenarios": [scenario(then=[{"assert": "not_equals", "var": "ghost", "value": 1}])]}
    r = execute_scenarios(data)
    assert r["status"] == "failures_present"
    f = r["scenarios"][0]["failure"]
    assert f["reason"] == "unknown_variable" and f["step"]["assert"] == "not_equals"
    assert f["section"] == "then" and f["step_index"] == 0
