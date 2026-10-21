import math, random
from fractions import Fraction
from app.modules.m20_general_cognitive_worker.outcome_metacognition_1975_2009 import OutcomeMetacognition
from app.modules.m20_general_cognitive_worker.uncertainty_gate_metacognition import UncertaintyGate, wilson_lower


def mk(**p):
    return OutcomeMetacognition({k: (lambda t, k=k: True) for k in p})


def feed(m, name, wins, losses):
    for _ in range(wins): m.record(name, m.confidence(name), True)
    for _ in range(losses): m.record(name, m.confidence(name), False)


def test_wilson_matches_known_values():
    # reference values for z=1.96: 8/10 -> 0.4902, 0/10 -> 0, 100/100 -> 0.9630
    assert abs(wilson_lower(8, 10) - 0.4902) < 5e-4
    assert wilson_lower(0, 10) == 0.0 and wilson_lower(0, 0) == 0.0
    assert abs(wilson_lower(100, 100) - 0.9630) < 5e-4


def test_high_stakes_never_acts_without_evidence_but_low_stakes_does():
    m = mk(a=1); feed(m, "a", 3, 0)  # 3/3 looks perfect but n=3
    g = UncertaintyGate(m)
    h = g.decide("high")
    assert h["action"] == "ask" and "proceed anyway" in h["question"]
    assert g.decide("low")["action"] == "ask"  # wilson(3,3)=0.44 < 0.5, even low asks
    feed(m, "a", 97, 0)
    d = g.decide("high")  # n=100, wilson ~0.963: eligible, but never auto-act
    assert d["action"] == "eligible_pending_authority" and d["requires_authority"] is True


def test_overconfidence_discounts_confidence():
    m = mk(a=1)
    feed(m, "a", 80, 0)
    base = UncertaintyGate(m).conservative_confidence("a")
    assert base["calibration_shrink"] == 1.0
    for _ in range(20): m.record("a", 0.95, False)  # claimed 0.95, failed every time
    c = UncertaintyGate(m).conservative_confidence("a")
    assert m.reflect()["status"] == "overconfident"
    assert c["calibration_shrink"] < 0.1 and c["confidence"] < base["confidence"] * 0.1


def test_fallback_retries_next_strategy_then_asks():
    calls = []
    def bad(t): calls.append("bad"); raise RuntimeError("x")
    def worse(t): calls.append("worse"); return 0
    def good(t): calls.append("good"); return 42
    m = OutcomeMetacognition({"bad": bad, "worse": worse, "good": good})
    g = UncertaintyGate(m)
    r = g.run_with_fallback(1, lambda t, x: x == 42, "low", max_attempts=3)
    assert r["status"] == "verified" and r["result"] == 42 and len(r["attempts"]) <= 3
    assert any(not a["success"] for a in r["attempts"][:-1]) or len(r["attempts"]) == 1
    m2 = OutcomeMetacognition({"bad": bad})
    r2 = g.__class__(m2).run_with_fallback(1, lambda t, x: True, "medium")
    assert r2["status"] == "ask_user" and r2["attempts"][0]["error"].startswith("RuntimeError")
    assert m2.errors["bad"] == 1 and m2.losses["bad"] == 1
    try:
        g.run_with_fallback(1, lambda t, x: True, "high"); assert False
    except ValueError:
        pass


def test_invalid_inputs_and_retrospective():
    m = mk(a=1, b=1); feed(m, "a", 9, 1); feed(m, "b", 1, 9)
    g = UncertaintyGate(m)
    for bad in ("extreme", None):
        try: g.decide(bad); assert False
        except ValueError: pass
    try: g.run_with_fallback(1, lambda t, x: True, "low", max_attempts=0); assert False
    except ValueError: pass
    try: UncertaintyGate(object()); assert False
    except ValueError: pass
    r = g.retrospective()
    assert r["best"] == "a" and r["worst"] == "b"


def test_gate_reduces_high_stakes_errors_vs_always_act_seeded():
    """Measured: strategies with hidden success probs; after a few outcomes, acting
    always vs acting only when the high-stakes gate says act. Gated error rate on the
    acted subset must be lower, and gate must abstain on the thin-evidence strategy."""
    rng = random.Random(7)
    probs = {"solid": 0.97, "flaky": 0.6, "rare": 0.95}
    m = OutcomeMetacognition({k: (lambda t, k=k: rng.random() < probs[k]) for k in probs}, seed=1)
    # evidence: solid 200 outcomes, flaky 200, rare only 3
    for k, n in (("solid", 200), ("flaky", 200), ("rare", 3)):
        for _ in range(n):
            m.record(k, m.confidence(k), rng.random() < probs[k])
    g = UncertaintyGate(m)
    d = g.decide("high")
    assert d["action"] == "eligible_pending_authority" and d["strategy"] == "solid"
    table = {t["strategy"]: t for t in d["table"]}
    assert table["rare"]["confidence"] < 0.9 and table["flaky"]["confidence"] < 0.9
    # error rate comparison on fresh trials
    N = 2000
    always = sum(1 for i in range(N) if not (rng.random() < probs[rng.choice(list(probs))]))
    gated = sum(1 for i in range(N) if not (rng.random() < probs[d["strategy"]]))
    assert gated / N < always / N
    assert gated / N < 0.06


def test_state_roundtrip_preserves_gate_decision():
    m = mk(a=1, b=1); feed(m, "a", 150, 5); feed(m, "b", 10, 10)
    d1 = UncertaintyGate(m).decide("high")
    m2 = mk(a=1, b=1); m2.load_state(m.to_state())
    d2 = UncertaintyGate(m2).decide("high")
    assert d1 == d2


def test_configurable_policy_and_validation():
    m = mk(a=1); feed(m, "a", 30, 0)
    strict = UncertaintyGate(m, {"low": (0.99, 0), "medium": (0.99, 5), "high": (0.99, 50)})
    assert strict.decide("low")["action"] == "ask"
    lax = UncertaintyGate(m, {"low": (0.1, 0), "medium": (0.1, 0), "high": (0.1, 0)})
    assert lax.decide("low")["action"] == "act" and lax.decide("high")["action"] == "eligible_pending_authority"
    for bad in ({"low": (0.5, 0)}, {"low": (2, 0), "medium": (.5, 0), "high": (.5, 0)},
                {"low": (float("nan"), 0), "medium": (.5, 0), "high": (.5, 0)},
                {"low": (.5, -1), "medium": (.5, 0), "high": (.5, 0)}):
        try: UncertaintyGate(m, bad); assert False
        except ValueError: pass




# Reviewer-authored RED pins (requalified reconstruction): documented bypass and
# callback-purity contract of run_with_fallback, not original bytes.
def test_run_with_fallback_low_executes_below_decide_threshold():
    # decide('low') refuses (no evidence), yet run_with_fallback('low') executes:
    # the documented bypass - calling it is itself the decision to execute.
    learner = OutcomeMetacognition({"a": lambda t: "done"}, seed=1)
    gate = UncertaintyGate(learner, {"low": (0.9, 5), "medium": (0.9, 5), "high": (0.9, 5)})
    assert gate.decide("low")["action"] == "ask"
    out = gate.run_with_fallback("task", lambda t, r: True, "low")
    assert out["status"] == "verified" and out["strategy"] == "a"


def test_run_with_fallback_callback_exception_is_retryable_failure():
    # Pin the purity contract: a raised exception is recorded as ordinary failure
    # and the next strategy runs - so callbacks must be pure/read-only.
    calls = []
    def boom(task):
        calls.append("a"); raise RuntimeError("ambiguous effect")
    learner = OutcomeMetacognition({"a": boom, "b": lambda t: "ok"}, seed=1)
    gate = UncertaintyGate(learner)
    out = gate.run_with_fallback("task", lambda t, r: True, "low")
    assert out["status"] == "verified" and out["strategy"] == "b"
    assert out["attempts"][0]["strategy"] == "a" and out["attempts"][0]["success"] is False
    assert "RuntimeError" in out["attempts"][0]["error"]


def test_run_with_fallback_high_refuses_before_any_execution():
    learner = OutcomeMetacognition({"a": lambda t: (_ for _ in ()).throw(AssertionError("executed"))})
    gate = UncertaintyGate(learner)
    import pytest as _pytest
    with _pytest.raises(ValueError):
        gate.run_with_fallback("task", lambda t, r: True, "high")


# v3 RED pins (requalified reconstruction): peer-audit survivors now pinned -
# retry order, verifier strictness, and the default high-stakes bar.
def test_v3_fallback_tries_strategies_in_confidence_order():
    learner = OutcomeMetacognition(
        {"high": lambda t: "high-result", "low": lambda t: "low-result"}, seed=1)
    for _ in range(20):
        learner.record("high", 0.9, True)
    for ok in (True, True, False, False):
        learner.record("low", 0.4, ok)
    gate = UncertaintyGate(learner)
    assert (gate.conservative_confidence("high")["confidence"]
            > gate.conservative_confidence("low")["confidence"])
    out = gate.run_with_fallback("task", lambda t, r: r == "low-result", "low")
    assert out["status"] == "verified" and out["strategy"] == "low"
    assert len(out["attempts"]) == 2
    assert out["attempts"][0]["strategy"] == "high" and out["attempts"][0]["success"] is False
    assert out["attempts"][1]["strategy"] == "low" and out["attempts"][1]["success"] is True


def test_v3_verifier_truthy_nonbool_is_failure_via_typeerror():
    learner = OutcomeMetacognition(
        {"high": lambda t: "high-result", "low": lambda t: "low-result"}, seed=1)
    for _ in range(20):
        learner.record("high", 0.9, True)
    for ok in (True, True, False, False):
        learner.record("low", 0.4, ok)
    gate = UncertaintyGate(learner)
    verifier = lambda t, r: 1 if r == "high-result" else True
    out = gate.run_with_fallback("task", verifier, "low")
    assert out["status"] == "verified" and out["strategy"] == "low"
    assert out["attempts"][0]["strategy"] == "high"
    assert out["attempts"][0]["success"] is False
    assert out["attempts"][0]["error"].startswith("TypeError")


def test_v3_decide_high_asks_at_confidence_below_default_bar():
    learner = OutcomeMetacognition({"a": lambda t: None}, seed=1)
    for _ in range(43):
        learner.record("a", 0.9556, True)
    for _ in range(2):
        learner.record("a", 0.9556, False)
    gate = UncertaintyGate(learner)
    conf = gate.conservative_confidence("a")["confidence"]
    assert 0.8 < conf < 0.9, conf
    out = gate.decide("high")
    assert out["action"] == "ask"
    assert out["confidence"] == conf


def test_v4_boolean_max_attempts_is_refused():
    import pytest
    gate = UncertaintyGate(OutcomeMetacognition({"a": lambda task: task}))
    with pytest.raises(ValueError, match="positive int"):
        gate.run_with_fallback("task", lambda task, result: True, "low", max_attempts=True)


def test_v5_second_audit_decide_tie():
    m=OutcomeMetacognition({'a':lambda t:t,'b':lambda t:t})
    for name in ('a','b'):
        for _ in range(25):m.record(name,.9,True)
    assert UncertaintyGate(m).decide('low')['strategy']=='b'


def test_v5_gate_parameter_bool_int_edges():
    import pytest
    m=OutcomeMetacognition({'a':lambda t:t});g=UncertaintyGate(m)
    for val in (True,False,1.0):
        with pytest.raises(ValueError, match='positive int'):g.run_with_fallback('t',lambda t,r:True,'low',val)
        with pytest.raises(ValueError, match='positive integer'):g.retrospective(val)
    for threshold,n in [(True,0),(False,0),(.5,True),(.5,False),(.5,1.0)]:
        with pytest.raises(ValueError, match='invalid stakes policy'):UncertaintyGate(m,{'low':(threshold,n),'medium':(.7,5),'high':(.9,20)})
    for val in (0,1):
        r=g.run_with_fallback('t',lambda t,r:val,'low')
        assert r['status']=='ask_user' and r['attempts'][0]['success'] is False and r['attempts'][0]['error'].startswith('TypeError:')
