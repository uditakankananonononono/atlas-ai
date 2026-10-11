"""Bounded humidity-exposure evaluation, ledger row 1549: oracle, endpoints, gaps, traces."""
import copy

import pytest

from app.modules.m20_general_cognitive_worker.humidity_exposure1549 import (
    MAX_OBSERVATIONS, evaluate)

T0 = '2026-10-11T00:00:00+00:00'


def obs(offset_seconds, rh, **extra):
    import datetime
    t = (datetime.datetime(2026, 10, 11, tzinfo=datetime.timezone.utc)
         + datetime.timedelta(seconds=offset_seconds)).isoformat()
    return {'time': t, 'rh': rh, **extra}


def test_single_rectangle_exact():
    out = evaluate({'rh_limit': 60.0,
                    'observations': [obs(0, 80.0), obs(10, 50.0)]})
    assert out['time_above_limit_seconds'] == 10.0
    assert out['time_below_limit_seconds'] == 0.0
    assert out['time_at_limit_seconds'] == 0.0
    assert out['total_duration_seconds'] == 10.0
    assert out['horizon'] == obs(10, 50.0)['time']  # default: last observation


def test_piecewise_buckets_and_exact_endpoint_at_limit():
    out = evaluate({'rh_limit': 60.0, 'observations': [
        obs(0, 80.0),   # above for 10s
        obs(10, 60.0),  # exactly at limit for 10s -> its own bucket, not above
        obs(20, 40.0),  # below for 5s
        obs(25, 90.0),  # above for 5s
        obs(30, 20.0)]})
    assert out['time_above_limit_seconds'] == 15.0
    assert out['time_at_limit_seconds'] == 10.0
    assert out['time_below_limit_seconds'] == 5.0
    assert out['total_duration_seconds'] == 30.0


def test_max_continuous_excursion_vs_disjoint_sum_and_run_reset():
    out = evaluate({'rh_limit': 60.0, 'observations': [
        obs(0, 80.0), obs(10, 30.0), obs(20, 90.0), obs(40, 20.0)]})
    assert out['time_above_limit_seconds'] == 30.0          # disjoint sum 10 + 20
    assert out['max_continuous_excursion_seconds'] == 20.0  # longest single run
    assert out['excursion_count'] == 2
    reset = evaluate({'rh_limit': 60.0, 'observations': [
        obs(0, 80.0), obs(10, 60.0), obs(15, 80.0), obs(30, 20.0)]})
    assert reset['max_continuous_excursion_seconds'] == 15.0  # at-limit breaks the run
    assert reset['excursion_count'] == 2


def test_horizon_extension_and_refusals():
    extended = evaluate({'rh_limit': 60.0, 'horizon': obs(30, 0)['time'],
                         'observations': [obs(0, 80.0), obs(10, 50.0)]})
    assert extended['time_above_limit_seconds'] == 10.0
    assert extended['time_below_limit_seconds'] == 20.0  # last value holds to declared horizon
    assert extended['extrapolated_past_horizon'] is False
    with pytest.raises(ValueError):  # horizon before last observation
        evaluate({'rh_limit': 60.0, 'horizon': obs(5, 0)['time'],
                  'observations': [obs(0, 80.0), obs(10, 50.0)]})
    with pytest.raises(ValueError):  # observation past declared horizon
        evaluate({'rh_limit': 60.0, 'horizon': obs(10, 0)['time'],
                  'observations': [obs(0, 80.0), obs(20, 50.0)]})
    with pytest.raises(ValueError):  # zero-duration evaluation
        evaluate({'rh_limit': 60.0, 'horizon': obs(0, 0)['time'], 'observations': [obs(0, 80.0)]})


def test_gap_report_and_gap_refusal_no_silent_fill():
    profile = {'rh_limit': 60.0, 'max_gap_seconds': 25,
               'observations': [obs(0, 80.0), obs(10, 50.0), obs(100, 30.0)]}
    out = evaluate(profile)
    assert out['coverage']['largest_gap_seconds'] == 90.0
    assert out['coverage']['gaps'] == [{'start': obs(10, 0)['time'], 'end': obs(100, 0)['time'],
                                        'duration_seconds': 90.0}]
    assert out['gaps_filled'] is False
    with pytest.raises(ValueError):
        evaluate({**profile, 'gap_policy': 'refuse'})
    ok = evaluate({**profile, 'gap_policy': 'refuse', 'max_gap_seconds': 90})
    assert ok['coverage']['largest_gap_seconds'] == 90.0


def test_duplicate_timestamps_refused_even_across_timezone_spellings():
    dup = {'rh_limit': 60.0, 'observations': [obs(0, 80.0), obs(0, 50.0), obs(10, 30.0)]}
    with pytest.raises(ValueError):
        evaluate(dup)
    tz_dup = {'rh_limit': 60.0, 'observations': [
        {'time': '2026-10-11T06:30:00+05:30', 'rh': 80.0},   # 01:00 UTC
        {'time': '2026-10-11T00:00:00+00:00', 'rh': 50.0},
        {'time': '2026-10-11T10:00:00+00:00', 'rh': 30.0}]}
    out = evaluate(tz_dup)  # distinct instants, normalized and ordered
    assert out['total_duration_seconds'] == 36000.0
    tz_same = {'rh_limit': 60.0, 'observations': [
        {'time': '2026-10-11T05:30:00+05:30', 'rh': 80.0},
        {'time': '2026-10-11T00:00:00+00:00', 'rh': 80.0},  # identical instant
        {'time': '2026-10-11T10:00:00+00:00', 'rh': 30.0}]}
    with pytest.raises(ValueError):
        evaluate(tz_same)


def test_naive_timestamps_and_bad_protocol_or_unit_refused():
    with pytest.raises(ValueError):
        evaluate({'rh_limit': 60.0, 'observations': [{'time': '2026-10-11T00:00:00', 'rh': 50.0},
                                                     obs(10, 40.0)]})
    spec = {'rh_limit': 60.0, 'protocol': 'IEC60068-2-78',
            'observations': [obs(0, 50.0, protocol='IEC60068-2-30'), obs(10, 40.0)]}
    with pytest.raises(ValueError):
        evaluate(spec)
    flagged = evaluate({'rh_limit': 60.0, 'protocol': 'IEC60068-2-78',
                        'observations': [obs(0, 50.0), obs(10, 40.0)]})
    assert flagged['intervals'][0]['protocol_declared'] is False
    with pytest.raises(ValueError):
        evaluate({'rh_limit': 60.0, 'observations': [obs(0, 50.0, unit='fraction'), obs(10, 40.0)]})
    with pytest.raises(ValueError):
        evaluate({'rh_limit': 60.0, 'unit': 'fraction', 'observations': [obs(0, 50.0), obs(10, 40.0)]})


def test_rh_bounds_and_limit_bounds():
    for rh in (0.0, 100.0):
        out = evaluate({'rh_limit': 60.0, 'observations': [obs(0, rh), obs(10, rh)]})
        assert out['total_duration_seconds'] == 10.0
    for rh in (-0.1, 100.1, float('nan'), float('inf'), True, '50', None):
        with pytest.raises(ValueError):
            evaluate({'rh_limit': 60.0, 'observations': [obs(0, rh), obs(10, 40.0)]})
    for limit in (-1.0, 100.1, float('nan'), True, '60'):
        with pytest.raises(ValueError):
            evaluate({'rh_limit': limit, 'observations': [obs(0, 50.0), obs(10, 40.0)]})


def test_observation_cap_exact_n_and_n_plus_one():
    many = [obs(i * 10, 50.0) for i in range(MAX_OBSERVATIONS)]
    assert evaluate({'rh_limit': 60.0, 'observations': many})['coverage']['observation_count'] == MAX_OBSERVATIONS
    with pytest.raises(ValueError):
        evaluate({'rh_limit': 60.0, 'observations': many + [obs(MAX_OBSERVATIONS * 10, 50.0)]})


def test_source_ids_order_echo_and_input_not_mutated():
    profile = {'rh_limit': 60.0, 'observations': [
        obs(20, 30.0, source='chamber-b', id='m3'),
        obs(0, 80.0, source='chamber-a', id='m1'),
        obs(10, 90.0, source='chamber-a', id='m2')]}
    snapshot = copy.deepcopy(profile)
    out = evaluate(profile)
    assert profile == snapshot  # non-mutation
    assert [(i['source'], i['id'], i['source_index']) for i in out['intervals']] == [
        ('chamber-a', 'm1', 1), ('chamber-a', 'm2', 2), ('chamber-b', 'm3', 0)]
    assert out['time_above_limit_seconds'] == 20.0


def test_measured_outcome_comparison_exact_and_tamper_detection():
    profile = {'rh_limit': 60.0, 'observations': [obs(0, 80.0), obs(10, 50.0), obs(30, 20.0)]}
    good = evaluate({**profile, 'measured': {'time_above_limit': 10.0 / 3600,
                                             'max_continuous_excursion': 10.0 / 3600,
                                             'time_unit': 'hours'}})
    assert all(field['matches'] for field in good['measured_comparison'].values())
    bad = evaluate({**profile, 'measured': {'time_above_limit': 11.0, 'time_unit': 'seconds'}})
    assert bad['measured_comparison']['time_above_limit']['matches'] is False
    assert bad['measured_comparison']['time_above_limit']['computed'] == 10.0
    with pytest.raises(ValueError):
        evaluate({**profile, 'measured': {'time_above_limit': 1.0, 'time_unit': 'days'}})


def test_mutant_sensitivity_comparison_and_integration():
    base = {'rh_limit': 60.0, 'observations': [obs(0, 80.0), obs(10, 50.0), obs(20, 30.0)]}
    out = evaluate(base)
    mutant = copy.deepcopy(base)
    mutant['observations'][1]['rh'] = 70.0  # flips second interval above the limit
    m = evaluate(mutant)
    assert m['time_above_limit_seconds'] == out['time_above_limit_seconds'] + 10.0
    assert m['time_below_limit_seconds'] == 0.0
    tampered = evaluate({'rh_limit': 60.0, 'observations': [obs(0, 80.0), obs(10, 80.0), obs(25, 80.0)]})
    assert tampered['excursion_count'] == 1  # uninterrupted single run
    assert tampered['max_continuous_excursion_seconds'] == 25.0


def test_independent_rectangle_integrator_base_comparison():
    import datetime
    profile = {'rh_limit': 55.0, 'observations': [
        obs(0, 80.0), obs(7, 40.0), obs(19, 55.0), obs(23, 90.0), obs(50, 10.0)]}
    out = evaluate(profile)
    fmt = datetime.datetime.fromisoformat
    times = [fmt(o['time']).timestamp() for o in profile['observations']]
    rhs = [o['rh'] for o in profile['observations']]
    above = below = at = 0.0
    run = best = 0.0
    for i in range(len(times) - 1):
        dt = times[i + 1] - times[i]
        if rhs[i] > 55.0:
            above += dt
            run += dt
            best = max(best, run)
        elif rhs[i] < 55.0:
            below += dt
            run = 0.0
        else:
            at += dt
            run = 0.0
    assert out['time_above_limit_seconds'] == above
    assert out['time_below_limit_seconds'] == below
    assert out['time_at_limit_seconds'] == at
    assert out['max_continuous_excursion_seconds'] == best


def test_no_physical_test_degradation_or_certification_claims():
    out = evaluate({'rh_limit': 60.0, 'observations': [obs(0, 80.0), obs(10, 40.0)]})
    assert out['physical_test_performed'] is False
    assert out['degradation_or_lifetime_modeled'] is False
    assert out['certification_issued'] is False
    assert out['endpoint_convention']
    for key in out:
        assert 'executed' not in key and 'certified' not in key.replace('certification_issued', '')
