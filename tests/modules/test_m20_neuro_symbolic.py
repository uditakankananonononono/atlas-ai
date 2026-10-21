"""Row 1973 (Neuro-Symbolic AI) - focused tests, v2.

Output order contract (v7): result["provenance"][fact] lists the distinct
rule ids that derived the fact in LEXICAL sorted order, never in rule
insertion order; pinned by test_row1973_provenance_sorted_not_insertion_order.
(NOTE: the engine module docstring's "distinct rule ids that fired" wording
is unchanged to keep production bytes identical; this file carries the
order contract.)

v2 adds RED pins for coordinator findings on v1:
  fix1 one-shot integration latch -> rescore-across-passes pin
  fix2 stale contributions        -> retraction pin
  fix3 duplicate rule_id clobber  -> rejection pin
  fix4 unvalidated iteration caps -> constructor validation + truncation reporting pins
  fix5 non-finite inputs / zero-init doc -> validation + zero-init pins
  fix6 weak multi-hop / revision pins -> pass-2 firing pin + fitted-unit revision pins
"""
import math

import pytest

from app.modules.m20_general_cognitive_worker.neuro_symbolic import (
    LogisticUnit,
    NeuroSymbolicEngine,
    Rule,
)


def test_row1973_fitting_reduces_logistic_loss():
    unit = LogisticUnit()
    history = unit.fit(
        [({"x": 2.0}, 1), ({"x": 1.0}, 1), ({"x": -1.0}, 0), ({"x": -2.0}, 0)],
        epochs=400,
    )
    assert history[0] == pytest.approx(math.log(2), rel=1e-6)
    assert history[-1] < 0.05
    assert history[-1] < history[0]


def test_row1973_fit_is_zero_init_even_with_supplied_weights():
    # fix5: doc claims zero-init; supplied weights must not seed training.
    unit = LogisticUnit(weights={"x": 50.0}, bias=5.0)
    history = unit.fit([({"x": 2.0}, 1), ({"x": -2.0}, 0)], epochs=10)
    assert history[0] == pytest.approx(math.log(2), rel=1e-6)


def test_row1973_fitted_unit_separates_classes():
    unit = LogisticUnit()
    unit.fit([({"x": 2.0}, 1), ({"x": 1.5}, 1), ({"x": -1.5}, 0), ({"x": -2.0}, 0)], epochs=400)
    hi = unit.score({"x": 2.0})
    lo = unit.score({"x": -2.0})
    assert 0.0 <= lo < 0.01
    assert 0.99 < hi <= 1.0


def test_row1973_rule_fires_only_above_threshold():
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.9))
    eng.add_fact("a", 0.4)
    assert "b" not in eng.infer()["accepted"]
    eng2 = NeuroSymbolicEngine(threshold=0.5)
    eng2.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.9))
    eng2.add_fact("a", 0.9)
    out = eng2.infer()
    assert out["accepted"]["b"] == pytest.approx(0.81)


def test_row1973_derived_score_is_weight_times_min_antecedent():
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_rule(Rule(id="r1", antecedents=("a", "c"), consequent="b", weight=0.7))
    eng.add_fact("a", 0.9)
    eng.add_fact("c", 0.8)
    assert eng.infer()["accepted"]["b"] == pytest.approx(0.7 * 0.8)


def test_row1973_noisy_or_combines_distinct_derivations():
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.75))
    eng.add_rule(Rule(id="r2", antecedents=("c",), consequent="b", weight=0.75))
    eng.add_fact("a", 0.8)
    eng.add_fact("c", 0.8)
    # each rule contributes 0.6; noisy-OR: 1 - (1-0.6)^2 = 0.84
    assert eng.infer()["accepted"]["b"] == pytest.approx(1.0 - (1.0 - 0.6) ** 2)


def test_row1973_multi_hop_requires_second_infer_pass():
    # fix6: r2 cannot fire in pass 1 (b chains to 0.45 < threshold);
    # integration lifts b; r2 must fire in pass 2, recorded in the trace.
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.5))
    eng.add_rule(Rule(id="r2", antecedents=("b",), consequent="c", weight=0.9))
    eng.add_fact("a", 0.9)
    unit = LogisticUnit(weights={"rule_score": 4.0})
    out = eng.infer(unit=unit)
    assert "c" in out["accepted"]
    r2_passes = [t["pass"] for t in out["trace"] if t["rule"] == "r2"]
    assert min(r2_passes) == 2
    assert out["converged"] is True


def test_row1973_neural_revision_with_fitted_units():
    # fix6: fitted units decide; zero-weight 0.5 artifacts no longer drive this.
    def build(unit):
        eng = NeuroSymbolicEngine(threshold=0.5)
        eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.5))
        eng.add_fact("a", 0.9)
        return eng.infer(unit=unit)

    boosted = build(LogisticUnit(weights={"rule_score": 6.0}))
    assert boosted["accepted"]["b"] > 0.9  # strengthened well past rule score 0.45
    dampened = build(LogisticUnit(weights={"rule_score": -6.0}))
    assert "b" not in dampened["accepted"]  # dampened below threshold


def test_row1973_unfitted_unit_is_inert():
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.7))
    eng.add_fact("a", 0.9)
    assert eng.infer(unit=LogisticUnit())["accepted"]["b"] == pytest.approx(0.63)


def test_row1973_integration_rescores_every_pass():
    # fix1 RED pin: unit with negative prior weight must rescore b every pass,
    # walking it to the fixpoint ~0.34, not latch the first-pass 0.5.
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.9527))
    eng.add_fact("a", 0.9)
    out = eng.infer(unit=LogisticUnit(weights={"prior": -2.0}))
    assert "b" not in out["accepted"]
    assert out["scores"]["b"] < 0.45


def test_row1973_conclusions_retract_when_support_falls():
    # fix2 RED pin: once g drops below threshold, c (derived from g) loses
    # its only support and must disappear entirely.
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="g", weight=0.7))
    eng.add_rule(Rule(id="r2", antecedents=("g",), consequent="c", weight=0.9))
    eng.add_fact("a", 0.9)
    out = eng.infer(unit=LogisticUnit(weights={"prior": -2.0}))
    assert "c" not in out["scores"]
    assert "c" not in out["accepted"]


def test_row1973_duplicate_rule_id_rejected():
    # fix3 RED pin.
    eng = NeuroSymbolicEngine()
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b"))
    with pytest.raises(ValueError):
        eng.add_rule(Rule(id="r1", antecedents=("c",), consequent="d"))


def test_row1973_constructor_and_input_validation():
    # fix4/fix5 RED pins.
    with pytest.raises(ValueError):
        NeuroSymbolicEngine(max_iterations=0)
    with pytest.raises(ValueError):
        NeuroSymbolicEngine(max_iterations=True)
    with pytest.raises(ValueError):
        NeuroSymbolicEngine(threshold=float("nan"))
    with pytest.raises(ValueError):
        NeuroSymbolicEngine(threshold=1.5)
    with pytest.raises(ValueError):
        LogisticUnit(weights={"x": float("nan")})
    with pytest.raises(ValueError):
        LogisticUnit(rate=float("inf"))
    with pytest.raises(ValueError):
        LogisticUnit(rate=-0.1)
    with pytest.raises(ValueError):
        LogisticUnit().score({"x": float("nan")})
    with pytest.raises(ValueError):
        LogisticUnit().fit([], epochs=10)
    with pytest.raises(ValueError):
        LogisticUnit().fit([({"x": 1.0}, 2)], epochs=10)
    eng = NeuroSymbolicEngine()
    with pytest.raises(ValueError):
        eng.add_fact("a", float("nan"))
    with pytest.raises(ValueError):
        eng.add_fact("a", 1.5)
    with pytest.raises(ValueError):
        Rule(id="r", antecedents=("a",), consequent="b", weight=0.0)


def test_row1973_truncation_is_reported():
    # fix4 RED pin: oscillating revision never converges; result must say so.
    eng = NeuroSymbolicEngine(threshold=0.5, max_iterations=8)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.9))
    eng.add_fact("a", 0.9)
    out = eng.infer(unit=LogisticUnit(weights={"prior": -8.0}))
    assert out["iterations"] == 8
    assert out["converged"] is False
    assert out["truncated"] is True


def test_row1973_converges_and_is_deterministic():
    def run():
        eng = NeuroSymbolicEngine(threshold=0.5)
        eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.9))
        eng.add_rule(Rule(id="r2", antecedents=("b",), consequent="c", weight=0.9))
        eng.add_fact("a", 0.9)
        return eng.infer()

    first, second = run(), run()
    assert first["converged"] is True
    assert first["truncated"] is False
    assert first["accepted"] == second["accepted"]
    assert first["accepted"]["c"] == pytest.approx(0.9 * 0.9 * 0.9)


def test_row1973_provenance_and_trace_recorded():
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.9))
    eng.add_fact("a", 0.9)
    out = eng.infer()
    assert out["provenance"]["b"] == ["r1"]
    assert any(t["rule"] == "r1" and t["derived"] == "b" and t["pass"] == 1 for t in out["trace"])


def test_row1973_fact_exactly_at_threshold_fires():
    # boundary pin: gating is INCLUSIVE - a fact scoring == threshold fires
    # (and counts as accepted); blocking happens only strictly below it.
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.9))
    eng.add_fact("a", 0.5)
    out = eng.infer()
    assert out["scores"]["b"] == pytest.approx(0.45)
    assert any(t["rule"] == "r1" for t in out["trace"])
    eng2 = NeuroSymbolicEngine(threshold=0.5)
    eng2.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.9))
    eng2.add_fact("a", 0.499999)
    out2 = eng2.infer()
    assert "b" not in out2["scores"]


def test_row1973_huge_int_refused_as_valueerror_not_overflowerror():
    # v3 fix1 RED pin: 10**1000 must be refused with ValueError, not crash
    with pytest.raises(ValueError):
        LogisticUnit(weights={"x": 10 ** 1000})
    with pytest.raises(ValueError):
        NeuroSymbolicEngine().add_fact("a", 10 ** 1000)


def test_row1973_logit_overflow_refused():
    # v3 fix2 RED pin: finite but huge weights/features must not yield inf/nan
    unit = LogisticUnit(weights={"x": 1e308})
    with pytest.raises(ValueError):
        unit.score({"x": 1e308})
    unit2 = LogisticUnit(weights={"x": 1e308, "y": -1e308})
    with pytest.raises(ValueError):
        unit2.score({"x": 1e308, "y": 1e308})


def test_row1973_fit_divergence_refused():
    # v3 fix2 RED pin: exploding gradients must raise, not silently go NaN
    # saturated sigmoid keeps err small, so divergence needs a huge rate:
    # one update step overflows the weight to inf and must be refused
    unit = LogisticUnit(rate=1e308)
    with pytest.raises(ValueError):
        unit.fit([({"x": 1e308}, 1)], epochs=3)
    # divergence in the FINAL epoch never reaches another guarded logit
    # call, so the post-update finite check is what must refuse it
    unit_last = LogisticUnit(rate=1e308)
    with pytest.raises(ValueError):
        unit_last.fit([({"x": 1e308}, 1)], epochs=1)
    # mixed infinities in the weighted sum produce NaN, also refused
    unit2 = LogisticUnit(rate=1e308)
    with pytest.raises(ValueError):
        unit2.fit([({"x": 1e308, "y": 1e308}, 1), ({"x": 1e308}, 0)], epochs=3)


def test_row1973_self_loop_rule_rejected():
    # v3 fix3 RED pin
    with pytest.raises(ValueError):
        Rule(id="r", antecedents=("a",), consequent="a")


def test_row1973_fact_consequent_collision_rejected():
    # v3 fix3 RED pin: supplied facts are authoritative and immutable
    eng = NeuroSymbolicEngine()
    eng.add_fact("a", 0.9)
    with pytest.raises(ValueError):
        eng.add_rule(Rule(id="r1", antecedents=("b",), consequent="a"))
    eng2 = NeuroSymbolicEngine()
    eng2.add_rule(Rule(id="r1", antecedents=("b",), consequent="a"))
    with pytest.raises(ValueError):
        eng2.add_fact("a", 0.9)


def test_row1973_supplied_fact_score_never_changes():
    # v3 fix3 policy pin: supplied facts keep their supplied score in output
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_fact("a", 0.9)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.9))
    out = eng.infer()
    assert out["scores"]["a"] == 0.9
    assert eng.facts == {"a": 0.9}  # infer must not mutate engine state


def test_row1973_max_iterations_upper_bound():
    # v3 fix4 RED pin: default is 8; values above 64 are rejected
    with pytest.raises(ValueError):
        NeuroSymbolicEngine(max_iterations=65)
    NeuroSymbolicEngine(max_iterations=64)  # boundary accepted


def test_row1973_identical_runs_are_deterministic():
    # determinism only: identical runs agree on scores, provenance (rule
    # ids), iterations and flags. This is NOT a fixed-point proof.
    def run():
        eng = NeuroSymbolicEngine(threshold=0.5)
        eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b", weight=0.9))
        eng.add_rule(Rule(id="r2", antecedents=("b",), consequent="c", weight=0.9))
        eng.add_rule(Rule(id="r3", antecedents=("a",), consequent="c", weight=0.5))
        eng.add_fact("a", 0.9)
        return eng.infer()

    first, second = run(), run()
    assert first == second
    assert first["converged"] is True
    assert first["provenance"]["c"] == ["r2", "r3"]


def test_row1973_rule_cycle_converges_scores_only():
    # v4 fix1 pin: with a rule cycle, convergence is SCORES-ONLY. Scores
    # stabilize at 1.0 and the engine reports converged; provenance carries
    # rule ids only and no depth stability is claimed.
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_fact("a", 1.0)
    eng.add_rule(Rule(id="r1", antecedents=("a",), consequent="b"))
    eng.add_rule(Rule(id="r2", antecedents=("b",), consequent="c"))
    eng.add_rule(Rule(id="r3", antecedents=("c",), consequent="b"))
    out = eng.infer()
    assert out["converged"] is True
    assert out["truncated"] is False
    assert out["accepted"]["b"] == 1.0
    assert out["accepted"]["c"] == 1.0
    assert out["provenance"]["b"] == ["r1", "r3"]
    assert out["provenance"]["c"] == ["r2"]


def test_row1973_fit_uses_guarded_accumulation():
    # v4 fix2 RED pin: an infinite intermediate in fit's weighted sum must
    # raise, not saturate through the sigmoid and be silently accepted.
    # rate=2.0 drives both weights to 1e308 in epoch 1; in epoch 2 the
    # products overflow to inf.
    unit = LogisticUnit(rate=2.0)
    with pytest.raises(ValueError):
        unit.fit([({"x": 1e308, "y": 1e308}, 1)], epochs=3)


_reference_cycle_tolerance = 1e-9


def _reference_cycle(max_passes=64):
    """Independent minimal oracle for the s->a->b->a cycle: per pass, each
    rule's base = weight * snapshot antecedent score; a fact's score is the
    noisy-OR of its distinct rule contributions; convergence when neither
    score moves by more than _reference_cycle_tolerance. Returns
    (passes, a, b). Written separately from the engine on purpose."""
    a = b = None
    for it in range(1, max_passes + 1):
        new_a = 1.0 - (1.0 - 0.9) * (1.0 - (0.9 * b if b is not None else 0.0))
        new_b = 0.9 * a if a is not None else None
        done = (a is not None and b is not None
                and abs(new_a - a) <= _reference_cycle_tolerance
                and abs(new_b - b) <= _reference_cycle_tolerance)
        a, b = new_a, new_b
        if done:
            return it, a, b
    raise AssertionError("reference cycle did not converge")


def test_row1973_cycle_fixpoint_exact_scores_and_iterations():
    # v6 pin killing BOTH peer survivors (tolerance 1e-9->1e-3 and the
    # rescore latch "final=prior snapshot"): s=1, r1 s->a .9, r2 a->b .9,
    # r3 b->a .9 must reach the noisy-OR fixpoint. The pass count and
    # scores are pinned against the INDEPENDENT oracle above (not only
    # engine-measured) with abs=1e-12, rel=0; the oracle values are
    # cross-checked against the peer audit's published reference
    # .979325353633 / .881392818148.
    it_ref, a_ref, b_ref = _reference_cycle()
    assert it_ref == 19
    assert a_ref == pytest.approx(0.9793253536333603, abs=1e-12, rel=0)
    assert b_ref == pytest.approx(0.8813928181484476, abs=1e-12, rel=0)
    eng = NeuroSymbolicEngine(threshold=0.5, max_iterations=64)
    eng.add_fact("s", 1.0)
    eng.add_rule(Rule(id="r1", antecedents=("s",), consequent="a", weight=0.9))
    eng.add_rule(Rule(id="r2", antecedents=("a",), consequent="b", weight=0.9))
    eng.add_rule(Rule(id="r3", antecedents=("b",), consequent="a", weight=0.9))
    out = eng.infer()
    assert out["converged"] is True
    assert out["truncated"] is False
    assert out["iterations"] == it_ref
    assert out["scores"]["a"] == pytest.approx(a_ref, abs=1e-12, rel=0)
    assert out["scores"]["b"] == pytest.approx(b_ref, abs=1e-12, rel=0)
    # two DISTINCT rules reinforce consequent a every pass
    assert out["provenance"]["a"] == ["r1", "r3"]
    assert out["provenance"]["b"] == ["r2"]


def test_row1973_cycle_hits_default_iteration_cap_without_converging():
    # v6 pin: with the DEFAULT max_iterations=8 the same network is
    # truncated (not converged) at the measured pass-8 values. Note the
    # peer audit's tolerance mutant converged at PASS 7 with a=.9792831969,
    # b=.88092441; the pass-8 a here equals the peer's pass-7 a, while the
    # pass-8 b (0.88135487721) is one pass of lag AHEAD of the peer's
    # pass-7 b - the b values are intentionally not equated.
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_fact("s", 1.0)
    eng.add_rule(Rule(id="r1", antecedents=("s",), consequent="a", weight=0.9))
    eng.add_rule(Rule(id="r2", antecedents=("a",), consequent="b", weight=0.9))
    eng.add_rule(Rule(id="r3", antecedents=("b",), consequent="a", weight=0.9))
    out = eng.infer()
    assert out["iterations"] == 8
    assert out["converged"] is False
    assert out["truncated"] is True
    assert out["scores"]["a"] == pytest.approx(0.9792831969, abs=1e-9, rel=0)
    assert out["scores"]["b"] == pytest.approx(0.88135487721, abs=1e-9, rel=0)


def test_row1973_default_max_iterations_is_8():
    # v5 cheap pin for the default 8->9 survivor
    assert NeuroSymbolicEngine().max_iterations == 8


def test_row1973_large_finite_logits_saturate():
    # v5 cheap pin for the no-overflow-guard survivor: large finite logits
    # saturate cleanly (no exception, exact 1.0/0.0)
    unit = LogisticUnit(weights={"x": 1.0})
    assert unit.score({"x": 800.0}) == 1.0
    assert unit.score({"x": -800.0}) == 0.0


def test_row1973_provenance_sorted_not_insertion_order():
    # v7 pin (peer survivor: sorted(slot) -> list(slot)).
    # ORDER CONTRACT: result["provenance"][fact] lists the DISTINCT rule ids
    # that derived the fact in LEXICAL sorted order, never in rule-insertion
    # order. Witness from the peer audit: r2 (s->a, .9) added BEFORE
    # r10 (s->a, .8) must yield ["r10", "r2"] because "r10" < "r2"
    # lexicographically.
    eng = NeuroSymbolicEngine(threshold=0.5)
    eng.add_fact("s", 1.0)
    eng.add_rule(Rule(id="r2", antecedents=("s",), consequent="a", weight=0.9))
    eng.add_rule(Rule(id="r10", antecedents=("s",), consequent="a", weight=0.8))
    out = eng.infer()
    assert out["provenance"]["a"] == ["r10", "r2"]
    assert out["accepted"]["a"] == pytest.approx(1.0 - (1.0 - 0.9) * (1.0 - 0.8), rel=0, abs=1e-12)
