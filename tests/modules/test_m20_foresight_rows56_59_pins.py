"""Boundary/oracle pins for rows 56-59 (AsymmetryFinder, EVCalculator, RiskOfRuinAnalyzer, KellySizer).

Expected values are computed independently here (closed forms or a reimplemented loop), not copied from the code.

v3 (whole, tests-only, supersedes v2): reclassifies mutant e1_missing_mass_noclamp
from "equivalent" to killed_new. The v2 basis ("expected_value refuses mass > 1
before the sensitivity pass") was wrong: the validator tolerates total <= 1+1e-12,
so totals in (1, 1+1e-12] reach the unclamped branch and the mutant raises
"probabilities must be in [0,1]". Pinned below via the public EVCalculator API.
Exact float values are CPython 3.12 linux x86_64 fsum-deterministic.

v4 (whole, tests-only, supersedes v3): peer found the shared reasoning.py
validator tolerance constant unguarded (1e-12 -> 1.5e-12 survived all pins; the
2e-12 refusal in v3 sits too far from the boundary). Adds refusal pins at total
1+1.5e-12 and at math.nextafter(1+1e-12, inf). reasoning.py is SHARED with the
reasoning follow-up: this packet pins behavior only; no source change is
authorized or made.

v5 (retained tests): adds direct and EVCalculator zero-total
refusals matching positive, plus public boundary witnesses for a comparison,
constant and neighboring-validator mutation sweep of expected_value. Source
unchanged; shared reasoning follow-up overlap remains explicit.

v6 (retained tests): adds direct Kelly bool/odds/no-edge
pins and the interpreter-sensitive EV fsum witness. No production changes.

v7 (whole, tests-only, supersedes v6): pins Kelly positive-zero sign and the
four-term exact-hex RESULT accumulator fsum witness. TOTAL validator sum
replacement remains non-equivalent on 3.10; no 3.12 total-validator witness or
equivalence proof is claimed. These are distinct accumulation sites."""
import math, random
import pytest
from app.modules.m20_general_cognitive_worker.foresight import (
    AsymmetryFinder, EVCalculator, KellySizer, RiskOfRuinAnalyzer)
from app.modules.m20_general_cognitive_worker.reasoning import expected_value


# ---- row 56
def asym(**kw):
    o = {"name": "x", "upside": 300.0, "downside": 100.0}; o.update(kw)
    return AsymmetryFinder().evaluate(options=[o])["options"][0]


def test_asymmetry_threshold_is_inclusive_at_3():
    at = asym(); assert at["asymmetric"] is True and at["ratio"] == 3.0 and at["flag"] == "limited downside, large upside"
    below = asym(upside=299.0)
    assert below["asymmetric"] is False and below["flag"] == "downside too large relative to upside"


def test_asymmetry_zero_probability_never_asymmetric_but_flag_follows_ratio():
    z = asym(prob_upside=0.0)
    assert z["asymmetric"] is False and z["flag"] == "limited downside, large upside" and z["expected_upside"] == 0.0


def test_asymmetry_fields_default_probability_and_sorting():
    out = AsymmetryFinder().evaluate(options=[
        {"name": "low", "upside": 150.0, "downside": 100.0},
        {"name": "unb", "upside": 999.0},
        {"name": "high", "upside": 5000.0, "downside": 100.0, "prob_upside": 0.1}])["options"]
    assert [o["name"] for o in out] == ["high", "low", "unb"]
    high, low, unb = out
    assert high["ratio"] == 50.0 and high["expected_upside"] == pytest.approx(500.0) and high["downside_cap"] == 100.0
    assert low["expected_upside"] == 75.0           # default prob_upside 0.5
    assert unb["ratio"] is None and unb["expected_upside"] is None and unb["asymmetric"] is False


def test_asymmetry_validation_edges():
    asym(prob_upside=0.0); asym(prob_upside=1.0)
    for p in (-0.01, 1.01):
        with pytest.raises(ValueError, match="prob_upside"):
            asym(prob_upside=p)
    for d in (0, 0.0, -5):
        with pytest.raises(ValueError, match="downside must be > 0"):
            asym(downside=d)
    with pytest.raises(ValueError, match="at least one"):
        AsymmetryFinder().evaluate(options=[])


# ---- row 57
def ev(outcomes):
    return EVCalculator().compute(options=[{"name": "o", "outcomes": outcomes}])["options"][0]


def test_ev_sensitivity_complete_distribution():
    r = ev([[0.5, 100.0], [0.5, 0.0]])
    assert r["ev"] == pytest.approx(50.0) and r["selected_best_index"] == 0
    assert r["best_probability_up"] == pytest.approx(0.6) and r["best_probability_down"] == pytest.approx(0.4)
    assert r["ev_if_best_+10pp"] == pytest.approx(60.0) and r["ev_if_best_-10pp"] == pytest.approx(40.0)
    assert r["probability_mass"] == pytest.approx(1.0) and r["missing_mass_zero"] == 0.0


def test_ev_missing_mass_is_zero_valued_and_redistribution_is_proportional():
    r = ev([[0.5, 100.0], [0.2, 50.0]])           # 0.3 missing mass at value 0
    assert r["ev"] == pytest.approx(60.0) and r["missing_mass_zero"] == pytest.approx(0.3)
    assert r["probability_mass"] == pytest.approx(0.7)
    assert r["ev_if_best_+10pp"] == pytest.approx(0.6 * 100 + 0.16 * 50)
    assert r["ev_if_best_-10pp"] == pytest.approx(0.4 * 100 + 0.24 * 50)


def test_ev_probability_clamps_and_certain_best_outcome():
    hi = ev([[0.95, 10.0], [0.05, 0.0]])
    assert hi["best_probability_up"] == 1.0 and hi["best_probability_down"] == pytest.approx(0.85)
    cert = ev([[1.0, 10.0]])
    assert cert["best_probability_up"] == 1.0 and cert["best_probability_down"] == pytest.approx(0.9)
    assert cert["ev_if_best_-10pp"] == pytest.approx(9.0) and cert["ev_if_best_+10pp"] == pytest.approx(10.0)
    lo = ev([[0.05, 10.0], [0.95, 0.0]])
    assert lo["best_probability_down"] == 0.0 and lo["ev_if_best_-10pp"] == pytest.approx(0.0)


def test_ev_best_tie_takes_first_and_options_sort_descending():
    assert ev([[0.5, 7.0], [0.5, 7.0]])["selected_best_index"] == 0
    out = EVCalculator().compute(options=[
        {"name": "lo", "outcomes": [[1.0, 1.0]]}, {"name": "hi", "outcomes": [[1.0, 5.0]]},
        {"name": "mid", "outcomes": [[1.0, 3.0]]}])["options"]
    assert [o["name"] for o in out] == ["hi", "mid", "lo"]
    with pytest.raises(ValueError, match="at least one"):
        EVCalculator().compute(options=[])


# ---- row 58
A = RiskOfRuinAnalyzer()


def test_closed_form_ruin_values_and_verdict_bands():
    for units, p, verdict in ((5, 0.6, "caution"), (10, 0.6, "acceptable"), (1, 0.6, "danger")):
        r = A.analyze(capital=float(units), bet_size=1.0, win_prob=p)
        assert r["method"] == "closed_form" and r["ruin_probability"] == pytest.approx(((1 - p) / p) ** units)
        assert r["verdict"] == verdict and r["units_at_risk"] == units
        assert r["edge_per_trial"] == pytest.approx(p - (1 - p))
    assert A.analyze(capital=10.0, bet_size=1.0, win_prob=0.3)["ruin_probability"] == 1.0
    sure = A.analyze(capital=10.0, bet_size=1.0, win_prob=1.0)
    assert sure["ruin_probability"] == 0.0 and sure["verdict"] == "acceptable"
    zero = A.analyze(capital=10.0, bet_size=1.0, win_prob=0.0)
    assert zero["ruin_probability"] == 1.0 and zero["verdict"] == "danger"


def test_even_odds_and_non_unit_payoff_use_monte_carlo_matching_independent_loop():
    a = RiskOfRuinAnalyzer(mc_trials=300, seed=7)
    for p, b in ((0.5, 1.0), (0.55, 2.0), (0.4, 1.5)):
        r = a.analyze(capital=20.0, bet_size=5.0, win_prob=p, payoff_ratio=b, trials=30)
        rng = random.Random(7); ruined = 0
        for _ in range(300):
            c = 20.0
            for _ in range(30):
                c += 5.0 * b if rng.random() < p else -5.0
                if c <= 0:
                    ruined += 1; break
        assert r["method"] == "monte_carlo" and r["ruin_probability"] == ruined / 300
        assert r["edge_per_trial"] == pytest.approx(p * b - (1 - p))
        assert r["assumptions"][0] == "30 trials per path" and "7" in r["assumptions"][1] and "300" in r["assumptions"][1]


def test_negative_edge_is_always_danger_even_if_simulated_ruin_is_low():
    r = RiskOfRuinAnalyzer(mc_trials=50, seed=1).analyze(capital=1000.0, bet_size=1.0, win_prob=0.3, payoff_ratio=2.0, trials=1)
    assert r["edge_per_trial"] < 0 and r["ruin_probability"] == 0.0 and r["verdict"] == "danger"


def test_ruin_validation_edges():
    A.analyze(capital=10.0, bet_size=10.0, win_prob=0.6)          # bet == capital allowed
    for kw in ({"capital": 0.0}, {"capital": -1.0}, {"bet_size": 0.0}, {"bet_size": -1.0}, {"bet_size": 11.0}):
        base = {"capital": 10.0, "bet_size": 1.0, "win_prob": 0.6}; base.update(kw)
        with pytest.raises(ValueError, match="0 < bet_size <= capital"):
            A.analyze(**base)
    for kw in ({"win_prob": -0.01}, {"win_prob": 1.01}, {"payoff_ratio": 0.0}, {"payoff_ratio": -1.0}):
        base = {"capital": 10.0, "bet_size": 1.0, "win_prob": 0.6}; base.update(kw)
        with pytest.raises(ValueError, match="win_prob"):
            A.analyze(**base)


# ---- row 59
def test_kelly_formula_recommendation_and_growth_oracle():
    k = KellySizer(fraction=0.5, cap=0.25)
    p, b = 0.6, 2.0
    full = p - (1 - p) / b
    r = k.size(win_prob=p, payoff_ratio=b)
    rec = min(full * 0.5, 0.25)
    assert r["full_kelly"] == pytest.approx(full) and r["recommended"] == pytest.approx(rec)
    assert r["growth_rate"] == pytest.approx(p * math.log(1 + rec * b) + (1 - p) * math.log(1 - rec))
    assert r["note"] == "50%-Kelly capped at 25%"
    s = KellySizer(fraction=1.0, cap=1.0).size(win_prob=0.6, payoff_ratio=2.0)
    assert s["recommended"] == pytest.approx(full) and s["note"] == "100%-Kelly capped at 100%"
    sure = KellySizer(fraction=1.0, cap=0.3).size(win_prob=1.0, payoff_ratio=1.0)
    assert sure["recommended"] == 0.3 and sure["growth_rate"] == pytest.approx(math.log(1.3))


def test_kelly_no_edge_cases_never_size_positive():
    k = KellySizer()
    for p, b in ((0.5, 1.0), (0.2, 1.0), (0.0, 3.0)):
        r = k.size(win_prob=p, payoff_ratio=b)
        assert r["recommended"] == 0.0 and r["full_kelly"] == 0.0 and r["growth_rate"] == 0.0 and "No edge" in r["note"]


@pytest.mark.parametrize("kw", [
    {"fraction": 0.0}, {"fraction": 1.01}, {"cap": 0.0}, {"cap": 1.01}, {"fraction": math.nan},
    {"cap": math.inf}, {"fraction": True}, {"cap": "0.2"}, {"fraction": -0.5}])
def test_kelly_constructor_validation(kw):
    with pytest.raises(ValueError, match="fraction and cap"):
        KellySizer(**kw)


def test_units_at_risk_is_capital_over_bet_size():
    r = A.analyze(capital=100.0, bet_size=20.0, win_prob=0.6)
    assert r["units_at_risk"] == 5.0
    assert r["ruin_probability"] == pytest.approx((0.4 / 0.6) ** 5)


def test_verdict_thresholds_are_inclusive_at_exact_ruin_fractions():
    # ruin = ruined/mc_trials computed by an independent re-run of the loop; seeds/trials found by search
    for n, seed, trials, want_ruin, verdict in ((4, 1, 2, 0.25, "danger"), (20, 7, 2, 0.05, "caution")):
        rng = random.Random(seed); ruined = 0
        for _ in range(n):
            c = 2.0
            for _ in range(trials):
                c += 2.0 if rng.random() < 0.55 else -1.0
                if c <= 0:
                    ruined += 1; break
        assert ruined / n == want_ruin
        r = RiskOfRuinAnalyzer(mc_trials=n, seed=seed).analyze(
            capital=2.0, bet_size=1.0, win_prob=0.55, payoff_ratio=2.0, trials=trials)
        assert r["ruin_probability"] == want_ruin and r["edge_per_trial"] > 0 and r["verdict"] == verdict


# ---- row 58 v2 pins: peer-audit survivors now pinned
def test_ruin_exact_zero_edge_is_danger_even_with_zero_simulated_ruin():
    out = RiskOfRuinAnalyzer().analyze(capital=1000.0, bet_size=1.0, win_prob=0.5, trials=100)
    assert out["ruin_probability"] == 0.0
    assert out["edge_per_trial"] == 0.0
    assert out["verdict"] == "danger"


def test_ruin_monte_carlo_win_uses_strict_less_than_on_exact_draw_equality():
    # win_prob equals the FIRST draw of random.Random(0); '<' makes that draw a
    # loss, '<=' would make it a win. Seeded exact-draw oracle.
    out = RiskOfRuinAnalyzer(mc_trials=5, seed=0).analyze(
        capital=1.0, bet_size=1.0, win_prob=0.8444218515250481, payoff_ratio=0.5, trials=1)
    assert out["method"] == "monte_carlo"
    assert out["ruin_probability"] == 0.2

def test_ev_missing_mass_clamp_inside_validator_tolerance_band():
    # Kills e1_missing_mass_noclamp (max(0.0, ...) dropped from the appended
    # zero-mass outcome). Public-API witnesses for the reclassification:
    # (1) total = 1+5e-13 (inside the band): must RETURN, missing mass clamped to 0.0.
    w = EVCalculator().compute(options=[{"name": "x", "outcomes": [(0.6, 10.0), (0.4 + 5e-13, 20.0)]}])["options"][0]
    assert w["missing_mass_zero"] == 0.0 and w["probability_mass"] == 1.0000000000005
    assert w["ev"] == 14.000000000010001 and w["ev_if_best_+10pp"] == 15.000000000005
    # (2) total exactly 1+1e-12 (inclusive bound): accepted.
    b = EVCalculator().compute(options=[{"name": "x", "outcomes": [(0.6, 10.0), (0.4, 20.0), (1e-12, 30.0)]}])["options"][0]
    assert b["probability_mass"] == 1.000000000001 and b["missing_mass_zero"] == 0.0 and b["ev"] == 14.00000000003
    # (3) total just above the bound: refused by the validator.
    with pytest.raises(ValueError, match="^probability mass must be positive and at most1$"):
        EVCalculator().compute(options=[{"name": "x", "outcomes": [(0.6, 10.0), (0.4, 20.0), (2e-12, 30.0)]}])

def test_ev_validator_tolerance_refuses_immediately_above_bound():
    # Kills tolerance-constant mutants of the shared reasoning.py validator
    # widened to 1.25x/1.5x/2x; the existing inclusive-bound pin kills
    # 0.5x/0.75x narrowing. Construction guards prove the
    # supplied outcomes land on the intended floats.
    # (a) total = 1+1.5e-12 (peer witness): base refuses; a 1.5x/2x mutant accepts.
    outs = [(0.6, 10.0), (0.4, 20.0), (1.5e-12, 30.0)]
    assert math.fsum(p for p, _ in outs) == 1.0000000000015
    with pytest.raises(ValueError, match="^probability mass must be positive and at most1$"):
        expected_value(outs)
    with pytest.raises(ValueError, match="^probability mass must be positive and at most1$"):
        EVCalculator().compute(options=[{"name": "x", "outcomes": outs}])
    # (b) total = math.nextafter(1+1e-12, inf), the first float above the
    # inclusive bound: base refuses; any widened-tolerance mutant accepts.
    outs2 = [(0.6, 10.0), (0.4, 20.0), (1e-12, 30.0), (2.0**-52, 40.0)]
    assert math.fsum(p for p, _ in outs2) == math.nextafter(1 + 1e-12, math.inf)
    with pytest.raises(ValueError, match="^probability mass must be positive and at most1$"):
        expected_value(outs2)


def test_ev_zero_total_mass_is_not_positive():
    with pytest.raises(ValueError, match="positive"):
        expected_value([(0.0, 5.0)])
    with pytest.raises(ValueError, match="positive"):
        EVCalculator().compute(options=[{"name": "x", "outcomes": [[0.0, 1.0]]}])


def test_ev_validator_shape_numeric_and_length_boundaries():
    # Public expected_value boundary witnesses, not private helper calls.
    assert expected_value([(1.0, 5.0)]) == 5.0
    assert expected_value([(0.0, 5.0), (1.0, 2.0)]) == 2.0
    assert expected_value([(1.0, 0.0)]) == 0.0
    assert expected_value([(0.5, -8.0), (0.5, 4.0)]) == -2.0
    assert expected_value([(0.5, 1e308), (0.5, 1e308)]) == 1e308
    assert expected_value([(1.0, 5.0)] + [(0.0, 0.0)] * 9999) == 5.0
    bad_shapes = [[], (), [(1.0, 5.0)] * 10001, [(1.0,)],
                  [(1.0, 5.0, 7.0)], [{0: 1.0, 1: 5.0}],
                  [(True, 5.0)], [(1.0, False)], [("1", 5.0)],
                  [(float("nan"), 5.0)], [(1.0, float("inf"))],
                  [(-0.01, 5.0)], [(1.01, 5.0)]]
    for outcomes in bad_shapes:
        with pytest.raises(ValueError):
            expected_value(outcomes)
    # Accepted mass tolerance can push the result outside finite float range.
    with pytest.raises(ValueError, match="numeric range"):
        expected_value([(1.0, float.fromhex("0x1.fffffffffffffp+1023")),
                        (5e-13, float.fromhex("0x1.fffffffffffffp+1023"))])


def test_ev_length_refusals_have_shape_message():
    with pytest.raises(ValueError, match="^need1[.][.]10000 outcome pairs$"):
        expected_value([])
    with pytest.raises(ValueError, match="^need1[.][.]10000 outcome pairs$"):
        expected_value([(1.0, 5.0)] + [(0.0, 0.0)] * 10000)


def test_ev_individual_probability_cannot_use_total_tolerance():
    with pytest.raises(ValueError, match=r"^probabilities must be in \[0,1\]$"):
        expected_value([(1.0 + 5e-13, 5.0)])


def test_ev_type_and_finite_refusal_messages():
    with pytest.raises(ValueError, match="^need1[.][.]10000 outcome pairs$"):
        expected_value(((1.0, 5.0),))
    with pytest.raises(ValueError, match="^finite numeric probability/value pairs required$"):
        expected_value([{0: 1.0, 1: 5.0}])
    with pytest.raises(ValueError, match="^finite numeric probability/value pairs required$"):
        expected_value([(1.0, float("nan"))])
    # Avoid overflow from normalizing negative values by a tiny negative max.
    assert expected_value([(0.5, -1e308), (0.5, -1e-308)]) == -5e307


def test_kelly_exact_type_odds_and_no_edge_boundaries():
    from app.modules.m20_general_cognitive_worker.reasoning import kelly_criterion
    with pytest.raises(ValueError):
        kelly_criterion(True, 2.0)
    with pytest.raises(ValueError):
        kelly_criterion(0.6, True)
    with pytest.raises(ValueError, match="positive odds"):
        kelly_criterion(0.6, 0.0)
    assert kelly_criterion(0.4, 1.0) == 0.0
    assert kelly_criterion(0.0, 1.0) == 0.0
    assert kelly_criterion(1.0, 1.0) == 1.0


def test_ev_fsum_guard_interpreter_sensitive_distribution():
    outcomes = [(0.0001250000000001, 1.0)] * 8000
    assert expected_value(outcomes) == 1.0000000000008


def test_kelly_zero_returns_are_positive_zero():
    from app.modules.m20_general_cognitive_worker.reasoning import kelly_criterion
    for probability, odds in [(0.5, 1.0), (0.4, 1.0), (0.0, 1.0),
                              (0.25, 3.0), (0.1, 2.0), (0.0, 2.0)]:
        result = kelly_criterion(probability, odds)
        assert result == 0.0
        assert math.copysign(1.0, result) == 1.0


def test_ev_result_fsum_exact_hex_four_term_witness():
    maximum = float.fromhex('0x1.d5c9467743c20p+29')
    outcomes = [(float.fromhex('0x1.d5c9467743c20p-2'), maximum),
                (float.fromhex('0x1.80b41bef19b39p-3'), -maximum),
                (float.fromhex('0x1.cead8e5b009cfp-109'), -maximum),
                (float.fromhex('0x1.725ece02ada5ep-115'), -maximum)]
    assert expected_value(outcomes).hex() == '0x1.fd1ee332fff28p+27'
