"""Bounded humidity-exposure evaluation, ledger row 1549 Humidity Testing.

Evaluates sourced, timezone-aware, timestamped relative-humidity observations
against a predeclared exposure specification. The model is piecewise constant
with a left-closed endpoint convention: an observation's RH holds from its own
timestamp until the next observation's timestamp, and the final observation
holds until the declared horizon (default: the last observation's timestamp).
No interpolation, no extrapolation past the declared horizon, no silently
filled gaps. This is bookkeeping over supplied measurements, NOT a physical
humidity test, a material degradation or lifetime model, or certification.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

MAX_OBSERVATIONS = 4096

BOUNDARY = ('Piecewise-constant bookkeeping over supplied timestamped humidity observations; '
            'not a physical humidity test, material degradation or lifetime model, or certification.')

_TIME_UNITS = {'seconds': 1.0, 'minutes': 60.0, 'hours': 3600.0}


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a numeric value')
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f'{name} must be finite')
    return v


def _timestamp(value, name):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be an ISO-8601 timestamp string with explicit offset')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'{name} must be an ISO-8601 timestamp: {value!r}') from exc
    if parsed.tzinfo is None:
        raise ValueError(f'{name} must declare a timezone offset; naive timestamps are refused')
    return parsed.astimezone(timezone.utc)


def evaluate(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError('input must be an object')
    limit = _finite(data.get('rh_limit'), 'rh_limit')
    if not 0 <= limit <= 100:
        raise ValueError('rh_limit must lie in [0, 100] percent')
    unit = data.get('unit', 'percent')
    if unit != 'percent':
        raise ValueError("only percent relative humidity is supported; other units stay unverified")
    protocol = data.get('protocol')
    if protocol is not None and not isinstance(protocol, str):
        raise ValueError('protocol must be a string when declared')
    gap_policy = data.get('gap_policy', 'report')
    if gap_policy not in ('report', 'refuse'):
        raise ValueError("gap_policy must be 'report' or 'refuse'")
    max_gap = None
    if 'max_gap_seconds' in data:
        max_gap = _finite(data['max_gap_seconds'], 'max_gap_seconds')
        if max_gap <= 0:
            raise ValueError('max_gap_seconds must be > 0')

    raw_observations = data.get('observations')
    if not isinstance(raw_observations, list) or not 1 <= len(raw_observations) <= MAX_OBSERVATIONS:
        raise ValueError(f'observations require 1..{MAX_OBSERVATIONS} entries')
    observations = []
    for index, raw in enumerate(raw_observations):
        if not isinstance(raw, dict):
            raise ValueError('each observation must be an object')
        rh = _finite(raw.get('rh'), 'observation rh')
        if not 0 <= rh <= 100:
            raise ValueError('observation rh must lie in [0, 100] percent')
        obs_unit = raw.get('unit', 'percent')
        if obs_unit != 'percent':
            raise ValueError(f"observation unit {obs_unit!r} unsupported; only percent is evaluated")
        obs_protocol = raw.get('protocol')
        if protocol is not None and obs_protocol is not None and obs_protocol != protocol:
            raise ValueError(f"observation protocol {obs_protocol!r} does not match declared spec protocol {protocol!r}")
        source = raw.get('source')
        obs_id = raw.get('id')
        for label, value in (('source', source), ('id', obs_id)):
            if value is not None and not isinstance(value, str):
                raise ValueError(f'observation {label} must be a string when supplied')
        observations.append({'instant': _timestamp(raw.get('time'), 'observation time'),
                             'rh': rh, 'source': source, 'id': obs_id,
                             'protocol_declared': obs_protocol is not None,
                             'source_index': index})

    horizon = _timestamp(data['horizon'], 'horizon') if 'horizon' in data else None
    observations.sort(key=lambda o: (o['instant'], o['source_index']))
    for earlier, later in zip(observations, observations[1:]):
        if earlier['instant'] == later['instant']:
            raise ValueError(f'duplicate observation instant after timezone normalization: '
                             f'{earlier["instant"].isoformat()}')
    first = observations[0]['instant']
    last = observations[-1]['instant']
    if horizon is None:
        horizon = last
    if horizon < last:
        raise ValueError('horizon precedes the last observation; refusing to truncate supplied data')
    if horizon < first or horizon == first:
        raise ValueError('zero-duration evaluation refused: horizon must lie after the first observation')

    intervals = []
    points = [o['instant'] for o in observations] + [horizon]
    for i, obs in enumerate(observations):
        start, end = points[i], points[i + 1]
        duration = (end - start).total_seconds()
        state = 'above' if obs['rh'] > limit else 'below' if obs['rh'] < limit else 'at_limit'
        intervals.append({'start': start.isoformat(), 'end': end.isoformat(),
                          'duration_seconds': duration, 'rh': obs['rh'], 'state': state,
                          'source': obs['source'], 'id': obs['id'],
                          'protocol_declared': obs['protocol_declared'],
                          'source_index': obs['source_index']})

    above = math.fsum(i['duration_seconds'] for i in intervals if i['state'] == 'above')
    below = math.fsum(i['duration_seconds'] for i in intervals if i['state'] == 'below')
    at_limit = math.fsum(i['duration_seconds'] for i in intervals if i['state'] == 'at_limit')
    best_run = run = 0.0
    excursion_count = 0
    in_run = False
    for interval in intervals:
        if interval['state'] == 'above':
            run += interval['duration_seconds']
            if not in_run:
                excursion_count += 1
                in_run = True
            best_run = max(best_run, run)
        else:
            run = 0.0
            in_run = False

    gaps = []
    if max_gap is not None:
        for interval in intervals:
            if interval['duration_seconds'] > max_gap:
                gaps.append({'start': interval['start'], 'end': interval['end'],
                             'duration_seconds': interval['duration_seconds']})
    if gaps and gap_policy == 'refuse':
        raise ValueError(f'coverage gap(s) exceed declared max_gap_seconds={max_gap}: '
                         f'{len(gaps)} gap(s), largest {max(g["duration_seconds"] for g in gaps)}s')

    measured_comparison = None
    if 'measured' in data:
        measured = data['measured']
        if not isinstance(measured, dict):
            raise ValueError('measured must be an object of supplied outcome values')
        time_unit = measured.get('time_unit', 'seconds')
        if time_unit not in _TIME_UNITS:
            raise ValueError(f"measured time_unit must be one of {sorted(_TIME_UNITS)}")
        factor = _TIME_UNITS[time_unit]
        computed = {'time_above_limit': above, 'time_below_limit': below,
                    'time_at_limit': at_limit, 'max_continuous_excursion': best_run}
        measured_comparison = {}
        for field, actual in computed.items():
            if field not in measured:
                continue
            supplied = _finite(measured[field], f'measured.{field}')
            measured_comparison[field] = {'supplied': supplied, 'time_unit': time_unit,
                                          'computed': actual, 'matches': supplied * factor == actual}

    return {
        'scope': 'bounded_humidity_exposure_1549',
        'rh_limit': limit,
        'unit': 'percent',
        'protocol': protocol,
        'endpoint_convention': 'left-closed piecewise constant: an observation holds from its own '
                               'timestamp until the next observation, the last until the declared horizon',
        'horizon': horizon.isoformat(),
        'total_duration_seconds': (horizon - first).total_seconds(),
        'time_above_limit_seconds': above,
        'time_below_limit_seconds': below,
        'time_at_limit_seconds': at_limit,
        'max_continuous_excursion_seconds': best_run,
        'excursion_count': excursion_count,
        'intervals': intervals,
        'coverage': {'observation_count': len(observations),
                     'largest_gap_seconds': max((i['duration_seconds'] for i in intervals), default=0.0),
                     'max_gap_seconds': max_gap, 'gap_policy': gap_policy, 'gaps': gaps},
        'measured_comparison': measured_comparison,
        'gaps_filled': False,
        'extrapolated_past_horizon': False,
        'physical_test_performed': False,
        'degradation_or_lifetime_modeled': False,
        'certification_issued': False,
        'boundary': BOUNDARY,
    }
