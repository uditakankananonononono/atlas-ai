import random
from app.modules.m20_general_cognitive_worker.outcome_metacognition_1975_2009 import OutcomeMetacognition

def test_learns_best_strategy_and_calibrates():
    rng = random.Random(1)
    # strategy "good" is right 90% of time, "bad" 20% (hidden from learner)
    p = {"good": 0.9, "bad": 0.2, "mid": 0.5}
    strat = {k: (lambda t, k=k: rng.random() < p[k]) for k in p}
    m = OutcomeMetacognition(strat, seed=3)
    picks = [m.run(i, lambda t, r: r)["strategy"] for i in range(400)]
    assert picks[-100:].count("good") > 75
    r = m.report()
    assert abs(r["good"]["confidence"] - 0.9) < 0.07
    assert abs(r["bad"]["confidence"] - 0.2) < 0.2
    assert m.brier() < 0.25


def test_reflect_detects_overconfidence_and_empty_input():
    m = OutcomeMetacognition({"a": lambda t: True})
    assert m.reflect()["status"] == "no_data"
    for _ in range(20):
        m.record("a", 0.95, False)
    r = m.reflect()
    assert r["status"] == "overconfident" and r["explore"] > 1.0
    try:
        OutcomeMetacognition({})
        assert False
    except ValueError:
        pass


def test_independent_oracle_posterior_and_brier():
    from fractions import Fraction
    hist = [["a", True], ["a", False], ["a", True], ["b", False], ["b", False], ["a", True]]
    from app.modules.m20_general_cognitive_worker.outcome_metacognition_1975_2009 import run_from_history
    out = run_from_history({"strategies": ["a", "b"], "history": hist})
    w = {"a": 3, "b": 0}; n = {"a": 4, "b": 2}
    # oracle: Beta(1,1) posterior mean (w+1)/(n+2) with exact fractions, replayed
    cw = {"a": 0, "b": 0}; cn = {"a": 0, "b": 0}; se = Fraction(0)
    for s, ok in hist:
        c = Fraction(cw[s] + 1, cn[s] + 2); se += (c - int(ok)) ** 2
        cw[s] += int(ok); cn[s] += 1
    for s in ("a", "b"):
        assert out["report"][s]["wins"] == w[s]
        assert out["report"][s]["confidence"] == float(Fraction(w[s] + 1, n[s] + 2))
    assert out["brier"] == float(se / len(hist))
    assert out["n_outcomes"] == len(hist)


# Requalified reconstruction; oracle completion and two replacement tests
# reviewer-authored, not original bytes.
def test_record_rejects_invalid_inputs():
    m = OutcomeMetacognition({"a": lambda t: True})
    import pytest as _pytest
    with _pytest.raises(ValueError):
        m.record("unknown", 0.5, True)
    with _pytest.raises(ValueError):
        m.record("a", 1.5, True)
    with _pytest.raises(ValueError):
        m.record("a", 0.5, "yes")


def test_to_state_load_state_roundtrip_exact():
    m = OutcomeMetacognition({"a": lambda t: True, "b": lambda t: False}, seed=3)
    for i in range(10):
        m.record("a", 0.9, True)
        m.record("b", 0.4, i % 2 == 0)
    state = m.to_state()
    fresh = OutcomeMetacognition({"a": lambda t: True, "b": lambda t: False}, seed=3)
    fresh.load_state(state)
    assert fresh.to_state() == state
    assert fresh.report() == m.report()


def test_v4_run_truthy_nonbool_verifier_is_contained():
    learner = OutcomeMetacognition({"a": lambda task: task})
    result = learner.run("task", lambda task, result: 1)
    assert result["success"] is False
    assert result["error"].startswith("TypeError: verifier must return bool")
    assert learner.errors["a"] == 1
    assert learner.losses["a"] == 1


def test_v5_first_audit_record_admission_edges():
    import pytest
    m = OutcomeMetacognition({'a': lambda t: t})
    with pytest.raises(ValueError, match='outcome must be bool'): m.record('a', .5, 1)
    with pytest.raises(ValueError, match='confidence must be finite'): m.record('a', True, True)


def test_v5_second_audit_selection_tie():
    assert OutcomeMetacognition({'b': lambda t: t, 'a': lambda t: t}).select() == ('a', .5)


def test_v5_second_audit_reflect_and_calibration():
    m = OutcomeMetacognition({'a': lambda t: t}, explore=3)
    for _ in range(20): m.record('a', .9, False)
    assert m.reflect()['explore'] == 4.0
    m = OutcomeMetacognition({'a': lambda t: t})
    for i in range(20): m.record('a', .65, bool(i % 2))
    assert m.calibration_summary()['status'] == 'overconfident'


def test_v5_second_audit_count_and_explore_admission():
    import pytest
    with pytest.raises(ValueError, match='explore must be finite'): OutcomeMetacognition({'a': lambda t: t}, explore=True)
    m = OutcomeMetacognition({'a': lambda t: t}); state = m.to_state(); state['wins'] = {'a': True}
    with pytest.raises(ValueError, match='non-negative ints'): m.load_state(state)


def test_v5_public_parameter_bool_int_edges():
    import pytest
    from app.modules.m20_general_cognitive_worker.outcome_metacognition_1975_2009 import run_from_history
    m = OutcomeMetacognition({'a': lambda t: t})
    for val in (True, False, 1.0):
        with pytest.raises(ValueError, match='positive integer'): m.calibration_summary(val)
        with pytest.raises(ValueError, match='positive integer'): m.reflect(val)
    for conf in (True, False):
        with pytest.raises(ValueError, match='confidence must be finite'): m.record('a', conf, True)
    for ok in (0, 1):
        with pytest.raises(ValueError, match='outcome must be bool'): m.record('a', .5, ok)
        result = m.run('t', lambda t, r: ok)
        assert result['success'] is False and result['error'].startswith('TypeError:')
        with pytest.raises(ValueError, match='known_strategy, bool'): run_from_history({'strategies': ['a'], 'history': [['a', ok]]})
    for field in ('wins', 'losses', 'errors'):
        for val in (True, False, 1.0):
            state=m.to_state();state[field]={'a':val}
            with pytest.raises(ValueError):m.load_state(state)
    for pred in ([True,1],[.5,True],[.5,1.0]):
        state=m.to_state();state['predictions']=[pred]
        with pytest.raises(ValueError, match='invalid predictions'):m.load_state(state)
    for val in (True,False):
        state=m.to_state();state['explore']=val
        with pytest.raises(ValueError, match='invalid explore'):m.load_state(state)
