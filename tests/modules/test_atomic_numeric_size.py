"""Bound exact arithmetic before conversion; exercise the real mounted API."""
from fractions import Fraction
import math
import random
import time

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.atomic_concepts_0093_0115 import run

# Intentionally independent of the production constant: changing the policy
# requires an explicit test/documentation review, not a silently moving boundary.
MAX_SAMPLES = 256
MAX_SECONDS = 5.0
URL = '/api/v1/api/modules/20/atomic-concepts-93-115/analyze'
HEADERS = {'X-Tenant-ID': 'atomic', 'X-Actor-ID': 'tester'}


@pytest.mark.parametrize('method,key', [
    ('selling_optimization', 'buyer_values'),
    ('system_delay', 'input'),
    ('system_delay', 'response'),
])
def test_oversize_is_rejected_before_numeric_conversion_at_run_and_route(method, key):
    data = {'input': [1], 'response': [1], 'max_lag': 0}
    # None would fail numeric validation if the size check were too late.
    data[key] = [None] * (MAX_SAMPLES + 1)
    detail = f'{key} supports at most {MAX_SAMPLES} values'
    with pytest.raises(ValueError, match=detail):
        run(method, data)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(URL, headers=HEADERS, json={'method': method, 'data': data})
    assert response.status_code == 422, response.text
    assert response.json()['detail'] == detail


def test_max_size_lag_exact_oracle_and_timing_bound():
    rng = random.Random(10793)
    x = [math.ldexp(rng.uniform(-1, 1), rng.randint(-500, 500)) for _ in range(MAX_SAMPLES)]
    y = [math.ldexp(rng.uniform(-1, 1), rng.randint(-500, 500)) for _ in range(MAX_SAMPLES)]
    exact = [sum((Fraction(x[t]) * Fraction(y[t+k])
                  for t in range(MAX_SAMPLES-k)), Fraction(0)) / (MAX_SAMPLES-k)
             for k in range(MAX_SAMPLES)]
    started = time.perf_counter()
    output = run('system_delay', {'input': x, 'response': y})['output']
    elapsed = time.perf_counter() - started
    assert elapsed < MAX_SECONDS, f'max-size all-lags request took {elapsed:.3f}s'
    assert output['lag_scores'] == [float(score) for score in exact]
    assert output['estimated_delay_periods'] == max(range(MAX_SAMPLES), key=exact.__getitem__)
    print(f'max-size lag: {MAX_SAMPLES} samples/all lags, {elapsed:.6f}s < {MAX_SECONDS}s')


def test_max_size_reserve_exact_oracle_and_timing_bound():
    rng = random.Random(107)
    values = [math.ldexp(rng.uniform(.5, 1), rng.randint(-500, 500)) for _ in range(MAX_SAMPLES)]
    vals = [Fraction(v) for v in values]
    outcomes = [(p * sum(v >= p for v in vals), p) for p in {Fraction(0), *vals}]
    revenue = max(rev for rev, _ in outcomes)
    reserve = min(p for rev, p in outcomes if rev == revenue)
    started = time.perf_counter()
    output = run('selling_optimization', {'buyer_values': values})['output']
    elapsed = time.perf_counter() - started
    assert elapsed < MAX_SECONDS, f'max-size reserve request took {elapsed:.3f}s'
    assert output['recommended_reserve'] == float(reserve)
    assert output['empirical_revenue_bound'] == float(revenue)
    assert output['buyer_count'] == MAX_SAMPLES
    print(f'max-size reserve: {MAX_SAMPLES} samples, {elapsed:.6f}s < {MAX_SECONDS}s')


@pytest.mark.parametrize('method,data', [
    ('selling_optimization', {'buyer_values': [1] * MAX_SAMPLES}),
    ('system_delay', {'input': [1] * MAX_SAMPLES, 'response': [1] * MAX_SAMPLES}),
])
def test_max_size_is_accepted_at_real_route(method, data):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(URL, headers=HEADERS, json={'method': method, 'data': data})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize('method,data', [
    ('selling_optimization', {'buyer_values': [1] * (MAX_SAMPLES + 1)}),
    ('system_delay', {'input': [1] * (MAX_SAMPLES + 1), 'response': [1] * (MAX_SAMPLES + 1), 'max_lag': 0}),
])
def test_valid_oversize_lists_are_not_accepted_even_for_zero_lag(method, data):
    with pytest.raises(ValueError, match='supports at most 256 values'):
        run(method, data)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(URL, headers=HEADERS, json={'method': method, 'data': data})
    assert response.status_code == 422, response.text
    assert 'supports at most 256 values' in response.json()['detail']
