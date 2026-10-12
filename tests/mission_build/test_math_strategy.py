import copy
import pytest
from app.mission_build.exact_math import analyze, verify_certificate
from app.mission_build.robust_strategy import optimize


def test_polynomial_certificate_and_tamper():
    p = {'coefficients': [-1, 0, 1], 'at': '3/2', 'root_candidates': [-1, 0, 1], 'integrate_between': [0, 3]}
    r = analyze(p)
    assert r['value'] == '5/4' and r['derivative'] == ['0', '2']
    assert r['definite_integral'] == '6' and [x['is_root'] for x in r['root_checks']] == [True, False, True]
    assert verify_certificate(p, r)
    r['value'] = '999'
    assert not verify_certificate(p, r)


@pytest.mark.parametrize('bad', [True, 1.0, '1/0', '__import__("os")', '1e9', '1/' + '9'*41])
def test_exact_math_rejects_nonrational(bad):
    with pytest.raises(ValueError):
        analyze({'coefficients': [bad]})


def test_degree_budget_and_zero_polynomial():
    with pytest.raises(ValueError):
        analyze({'coefficients': [1]*34})
    assert analyze({'coefficients': [0, 0]})['derivative'] == ['0']


def test_robust_choice_not_highest_best_case_and_no_effect_claim():
    p = {'budget': 5, 'scenarios': ['up', 'down'], 'options': [
        {'id': 'risky', 'cost': 2, 'utility': {'up': 10, 'down': -8}},
        {'id': 'steady', 'cost': 3, 'utility': {'up': 6, 'down': 4}},
        {'id': 'unaffordable', 'cost': 6, 'utility': {'up': 100, 'down': 100}}]}
    before = copy.deepcopy(p)
    r = optimize(p)
    assert r['choice'] == 'steady' and r['ranking'][0]['max_regret'] == '4'
    assert not r['effectiveness_verified'] and p == before
    p['budget'] = 0
    assert optimize(p)['status'] == 'no_feasible_option'


def test_scenario_coverage_duplicates_and_boolean_budget():
    p = {'budget': 0, 'scenarios': ['s'], 'options': [{'id': 'a', 'cost': 0, 'utility': {'s': 1}}]}
    for changed in [dict(p, budget=True), dict(p, scenarios=['s', 's']), dict(p, options=p['options']*2)]:
        with pytest.raises(ValueError):
            optimize(changed)
    p['options'][0]['utility'] = {}
    with pytest.raises(ValueError):
        optimize(p)
