"""M04 row 225 (box-uncertainty robust counterpart) pins. Test-only; runtime unchanged.

The enumeration reference below is numerical (clipping tolerances 1e-12, compared at 1e-6),
not a symbolic exact certificate. No physical-optimization claim is made.
"""
from datetime import datetime, timezone
from itertools import product
import random

import pytest

from app.modules.m04_research_scientist.quant_methods_185_234 import QuantError, run

S = [{'source_id': 'dataset-1', 'observed_at': datetime.now(timezone.utc).isoformat()}]
BOX = [[-1, 1], [-1, 1]]


def go(**kw):
    d = {'sources': S, 'bounds': BOX, 'coefficients': [0, 0], 'coefficient_uncertainty': [1, 1]}
    d.update(kw)
    for k in [k for k, v in d.items() if v is Ellipsis]:
        del d[k]
    return run(225, d)['result']


# ---------------- (a) error pins ----------------
def test_missing_coefficients_key_refused():
    with pytest.raises(QuantError) as e:
        go(coefficients=...)
    assert str(e.value) == 'missing required inputs: coefficients'


def test_missing_uncertainty_key_refused():
    with pytest.raises(QuantError) as e:
        go(coefficient_uncertainty=...)
    assert str(e.value) == 'missing required inputs: coefficient_uncertainty'


def test_missing_both_names_both_in_order():
    with pytest.raises(QuantError) as e:
        go(coefficients=..., coefficient_uncertainty=...)
    assert str(e.value) == 'missing required inputs: coefficients, coefficient_uncertainty'


def test_empty_coefficient_lists_count_as_missing():
    with pytest.raises(QuantError, match='missing required inputs: coefficients$'):
        go(coefficients=[])
    with pytest.raises(QuantError, match='missing required inputs: coefficient_uncertainty$'):
        go(coefficient_uncertainty=[])


def test_three_coefficients_two_bounds_refused():
    with pytest.raises(QuantError) as e:
        go(coefficients=[0, 0, 0])
    assert str(e.value) == 'coefficient dimension mismatch'


def test_three_uncertainty_radii_two_bounds_refused():
    with pytest.raises(QuantError) as e:
        go(coefficient_uncertainty=[1, 1, 1])
    assert str(e.value) == 'nonnegative uncertainty radius required per coefficient'


def test_two_uncertainty_radii_three_bounds_refused():
    with pytest.raises(QuantError) as e:
        go(bounds=[[-1, 1]] * 3)
    assert str(e.value) == 'nonnegative uncertainty radius required per coefficient'


def test_three_bounds_with_three_coefficients_refused_two_variable_limit():
    with pytest.raises(QuantError) as e:
        go(bounds=[[-1, 1]] * 3, coefficients=[0, 0, 0], coefficient_uncertainty=[1, 1, 1])
    assert str(e.value) == 'linear programming reference solver supports exactly two variables'


def test_negative_radius_and_infeasible_and_bad_bounds_refused():
    with pytest.raises(QuantError, match='nonnegative uncertainty radius'):
        go(coefficient_uncertainty=[1, -1e-9])
    with pytest.raises(QuantError) as e:
        go(constraints=[{'coefficients': [1, 1], 'rhs': -5}])
    assert str(e.value) == 'no feasible point: constraints are infeasible'
    with pytest.raises(QuantError, match='lower < upper'):
        go(bounds=[[1, 1], [-1, 1]])
    with pytest.raises(QuantError, match='constraint dimension mismatch'):
        go(constraints=[{'coefficients': [1, 1, 1], 'rhs': 1}])


# ---------------- (b) search label and echoed fields ----------------
def test_search_label_and_echoed_fields_exact_counterexample():
    r = go()
    assert r['search'] == 'exact_vertices_edge_kinks_interior'
    assert r['algorithm'] == 'box_uncertainty_robust_counterpart'
    assert r['method'] == 'Robust Optimization'
    assert r['best_point'] == [0.0, 0.0]
    assert r['best_value'] == 0.0 and r['worst_case_value'] == 0.0
    assert r['evaluations'] == 9          # 4 box vertices + 4 axis kinks + 1 interior candidate
    assert r['iterations'] == 0
    assert r['objective_history'] == [0.0]
    assert r['seed'] == 0 and r['converged'] is False and r['global_optimum_claimed'] is False


def test_search_label_and_echoed_fields_constrained_case():
    r = go(coefficients=[1, -2], coefficient_uncertainty=[0.5, 0.5], bounds=[[-1, 2], [-1, 3]],
           constraints=[{'coefficients': [1, 1], 'rhs': 2}], seed=7)
    assert r['search'] == 'exact_vertices_edge_kinks_interior'
    assert r['best_point'] == [-1.0, 3.0]
    assert r['best_value'] == -5.0 == r['worst_case_value']
    assert r['evaluations'] == 12 and r['seed'] == 7 and r['objective_history'] == [-5.0]


# ---------------- (c) seeded property test against an enumeration reference ----------------
def _clip(poly, a, b, c):
    """Keep a*x + b*y <= c (Sutherland-Hodgman, tolerance 1e-12)."""
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        fp = a * p[0] + b * p[1] - c
        fq = a * q[0] + b * q[1] - c
        if fp <= 1e-12:
            out.append(p)
        if (fp < -1e-12 and fq > 1e-12) or (fp > 1e-12 and fq < -1e-12):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def _enumerate(nom, rad, bounds, cons):
    """Minimum of sum(nom*x + rad*|x|) over the polygon; None when the polygon is empty."""
    poly = [(bounds[0][0], bounds[1][0]), (bounds[0][1], bounds[1][0]), (bounds[0][1], bounds[1][1]), (bounds[0][0], bounds[1][1])]
    for c in cons:
        poly = _clip(poly, c['coefficients'][0], c['coefficients'][1], c['rhs'])
        if not poly:
            return None
    best = None
    for s1, s2 in product((1, -1), (1, -1)):       # each orthant: the objective is linear there
        piece = _clip(_clip(poly, -s1, 0, 0), 0, -s2, 0)
        for x in piece:
            v = sum(nom[j] * x[j] + rad[j] * abs(x[j]) for j in range(2))
            best = v if best is None or v < best else best
    return best


def _case(rng, scales):
    lo = [rng.uniform(-3, 1) for _ in range(2)]
    hi = [l + rng.uniform(0.3, 4) for l in lo]
    nom = [rng.choice([0, rng.uniform(-3, 3)]) for _ in range(2)]
    rad = [rng.choice([0, rng.uniform(0, 3), abs(nom[j])]) for j in range(2)]
    cons = []
    for _ in range(rng.randint(0, 3)):
        a = [rng.uniform(-2, 2), rng.uniform(-2, 2)]
        pt = [rng.uniform(lo[j], hi[j]) for j in range(2)]
        k = rng.choice(scales)
        a = [k * a[0], k * a[1]]
        cons.append({'coefficients': a, 'rhs': a[0] * pt[0] + a[1] * pt[1] + k * rng.uniform(-0.3, 1)})
    return [list(b) for b in zip(lo, hi)], nom, rad, cons


def _compare(seed, scales, n_cases):
    rng = random.Random(seed)            # local generator, no global state touched
    feasible = infeasible = 0
    for idx in range(n_cases):
        bounds, nom, rad, cons = _case(rng, scales)
        want = _enumerate(nom, rad, bounds, cons)
        d = {'sources': S, 'bounds': bounds, 'coefficients': nom, 'coefficient_uncertainty': rad, 'constraints': cons}
        if want is None:
            with pytest.raises(QuantError, match='no feasible point'):
                run(225, d)
            infeasible += 1
            continue
        got = run(225, d)['result']['best_value']       # an unexpected exception fails the test
        assert abs(got - want) <= 1e-6 * max(1.0, abs(want)), (seed, idx, got, want)
        feasible += 1
    return feasible, infeasible


def test_property_unit_scale_matches_enumeration():
    feasible, infeasible = _compare(11, [1], 300)
    assert feasible > 150 and infeasible >= 0 and feasible + infeasible == 300


def test_property_scaled_constraints_002_005_match_enumeration():
    feasible, infeasible = _compare(23, [0.02, 0.05, 1], 300)
    assert feasible > 150 and feasible + infeasible == 300


@pytest.mark.parametrize('scale', [0.02, 0.05])
def test_property_each_scale_alone(scale):
    feasible, infeasible = _compare(int(scale * 1000), [scale], 150)
    assert feasible > 60 and feasible + infeasible == 150


def test_reference_enumeration_known_values():
    assert _enumerate([0, 0], [1, 1], [[-1, 1], [-1, 1]], []) == 0
    assert _enumerate([0, 0], [1, 1], [[-1, 1], [-1, 1]], [{'coefficients': [1, 1], 'rhs': -5}]) is None
    assert _enumerate([1, -2], [.5, .5], [[-1, 2], [-1, 3]], [{'coefficients': [1, 1], 'rhs': 2}]) == pytest.approx(-5)
