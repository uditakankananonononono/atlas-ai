"""Independent exact oracles: derive thresholds, do not reuse production helpers."""
import itertools
import json
import math
import random
import sys
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.atomic_concepts_0093_0115 import run, _f

URL = '/api/v1/api/modules/20/atomic-concepts-93-115/analyze'
HEADERS = {'X-Tenant-ID': 'atomic', 'X-Actor-ID': 'tester', 'Content-Type': 'application/json'}


def reserve_oracle(values):
    # Demand is constant between valuation thresholds; increasing the price
    # increases revenue there. Thus thresholds (and zero) suffice.
    vals = [Fraction(v) for v in values]
    outcomes = [(sum((price for v in vals if v >= price), Fraction(0)), price)
                for price in {Fraction(0), *vals}]
    revenue = max(rev for rev, _ in outcomes)
    return min(price for rev, price in outcomes if rev == revenue), revenue


def decimal_oracle(values):
    with localcontext() as ctx:
        ctx.prec = 2500
        vals = [Decimal(v) if isinstance(v, int) else Decimal.from_float(v) for v in values]
        outcomes = [(sum((p for v in vals if v >= p), Decimal(0)), p)
                    for p in {Decimal(0), *vals}]
        revenue = max(rev for rev, _ in outcomes)
        return min(p for rev, p in outcomes if rev == revenue), revenue


def float_representable(value):
    try:
        f = float(value)
    except OverflowError:
        return False
    return math.isfinite(f) and (value == 0 or f != 0)


def check_reserve(values):
    price, revenue = reserve_oracle(values)
    decimal_price, decimal_revenue = decimal_oracle(values)
    assert Fraction(decimal_price) == price and Fraction(decimal_revenue) == revenue
    data = {'buyer_values': values}
    if not float_representable(revenue):
        with pytest.raises(ValueError, match='range'):
            run('selling_optimization', data)
    else:
        result = run('selling_optimization', data)['output']
        assert result['recommended_reserve'] == float(price)
        assert result['empirical_revenue_bound'] == float(revenue)


def test_all_19530_ordinary_vectors():
    count = 0
    for size in range(1, 7):
        for values in itertools.product(range(5), repeat=size):
            check_reserve(list(values))
            count += 1
    assert count == 19530


def test_original_oracle_correction_proof():
    values = [10, 20, 30, 40]
    assert [(p, sum(p for v in values if v >= p)) for p in values] == [(10, 40), (20, 60), (30, 60), (40, 40)]
    assert reserve_oracle(values) == (20, 60)
    assert run('selling_optimization', {'buyer_values': values})['output']['recommended_reserve'] == 20


def test_log_scale_extreme_subnormal_and_exact_ties():
    tiny = math.ulp(0.0)
    maximum = sys.float_info.max
    examples = [[6e307, 1e308, 1e308, 1e308], [maximum], [maximum, maximum],
                [tiny], [tiny, 2*tiny, 3*tiny, 4*tiny], [0, tiny],
                [maximum/4, maximum/2, maximum/2], [1, 2], [0, 0],
                [2**53+1, 2**53+2], [math.nextafter(maximum, 0)],
                [math.nextafter(1e308, 0), 1e308]]
    rng = random.Random(91821)
    pool = [0, tiny, 1e-320, 1e-308, 0.1, 0.25, 1, 1e100, 1e307, maximum]
    for _ in range(1000):
        examples.append([rng.choice(pool) if rng.random() < .5 else
                         math.ldexp(rng.uniform(.5, 1), rng.randint(-1073, 1024))
                         for _ in range(rng.randint(1, 12))])
    for values in examples:
        check_reserve(values)
    assert reserve_oracle(examples[0])[0] == Fraction(1e308)
    assert reserve_oracle(examples[0])[1] > Fraction(maximum)


def lag_oracle(x, y, maximum):
    return [sum((Fraction(x[t])*Fraction(y[t+k]) for t in range(len(x)-k)), Fraction(0))/(len(x)-k)
            for k in range(maximum+1)]


def test_exact_lag_log_scale_cancellation_and_constants():
    tiny = math.ulp(0.0)
    cases = [([1e308], [1e308]), ([tiny], [tiny]),
             ([1e308, 1e308], [2, -2]), ([1e308, 1e308], [1, 1]),
             ([0, 0], [1e308, 1e308]), ([1, 1], [1, 1]),
             ([tiny, tiny], [1, 1]), ([1e308, -1e308, 1], [1e308, 1e308, 1])]
    rng = random.Random(91822)
    pool = [0, tiny, -tiny, 1e-308, -1e-308, .5, -2, 1e100, -1e308, 1e308]
    for _ in range(1000):
        n = rng.randint(1, 8)
        cases.append(([rng.choice(pool) for _ in range(n)], [rng.choice(pool) for _ in range(n)]))
    for x, y in cases:
        m = len(x)-1
        exact = lag_oracle(x, y, m)
        data = {'input': x, 'response': y, 'max_lag': m}
        if all(float_representable(s) for s in exact):
            output = run('system_delay', data)['output']
            assert output['lag_scores'] == [float(s) for s in exact]
            assert output['estimated_delay_periods'] == max(range(m+1), key=lambda i: exact[i])
        else:
            with pytest.raises(ValueError, match='range'):
                run('system_delay', data)
    # Huge intermediate products can cancel exactly, without data rescaling.
    output = run('system_delay', {'input': [1e308, -1e308, 1], 'response': [1e308, 1e308, 1], 'max_lag': 0})['output']
    assert output['lag_scores'] == [float(Fraction(1, 3))]


@pytest.mark.parametrize('bad', [10**400, True, float('nan'), float('inf'), float('-inf'), '1'])
def test_invalid_numbers_rejected_before_conversion_and_at_route(bad):
    with pytest.raises(ValueError):
        _f(bad, 'sample')
    client = TestClient(app, raise_server_exceptions=False)
    for method, data in [('selling_optimization', {'buyer_values': [bad]}),
                         ('system_delay', {'input': [bad], 'response': [1]})]:
        with pytest.raises(ValueError):
            run(method, data)
        response = client.post(URL, headers=HEADERS, content=json.dumps({'method': method, 'data': data}))
        assert response.status_code == 422, response.text
        assert isinstance(response.json()['detail'], str)


def test_real_json_encoding_overflow_and_finite_successes():
    client = TestClient(app, raise_server_exceptions=False)
    for method, data, status in [
        ('selling_optimization', {'buyer_values': [6e307, 1e308, 1e308, 1e308]}, 422),
        ('selling_optimization', {'buyer_values': [sys.float_info.max]}, 200),
        ('selling_optimization', {'buyer_values': [math.ulp(0.0)]}, 200),
        ('system_delay', {'input': [1e308], 'response': [1e308]}, 422),
        ('system_delay', {'input': [math.ulp(0.0)], 'response': [math.ulp(0.0)]}, 422),
        ('system_delay', {'input': [1e308, 1e308], 'response': [1, 1]}, 200),
        ('system_delay', {'input': [0, 0], 'response': [1, 1]}, 200),
        ('exponential_model', {'x': [1, 2, 3], 'y': [1e308, 1, 1e-308]}, 422),
        ('logarithmic_model', {'x': [1, 1, 1], 'y': [1, 2, 3]}, 422),
    ]:
        response = client.post(URL, headers=HEADERS, json={'method': method, 'data': data})
        assert response.status_code == status, response.text
        # json.loads normally accepts Infinity, so reject nonstandard constants explicitly.
        json.loads(response.text, parse_constant=lambda token: pytest.fail(token))


def test_exact_winner_is_selected_before_float_rounding():
    # Both revenues round to 2**53, but the exact larger reserve is better.
    values = [2**52, 2**53+1]
    check_reserve(values)
    assert run('selling_optimization', {'buyer_values': values})['output']['recommended_reserve'] == float(values[1])
    # Lag 0 rounds to 1 like lag 1, but its exact score is smaller.
    data = {'input': [1, math.nextafter(1.0, 0)], 'response': [1, 1]}
    output = run('system_delay', data)['output']
    assert output['lag_scores'] == [1.0, 1.0]
    assert output['estimated_delay_periods'] == 1


@pytest.mark.parametrize('lag', [False, 1.0, [], {}, '1'])
def test_additional_strict_lag_type_guards(lag):
    data = {'input': [1, 1], 'response': [1, 1], 'max_lag': lag}
    with pytest.raises(ValueError):
        run('system_delay', data)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post(URL, headers=HEADERS, json={'method': 'system_delay', 'data': data}).status_code == 422
