"""Deterministic local envelope simulation for the owner-row-115 "500,000 accounts per platform" target.

This is a model, not a quota and not an account manager. What it does: given
caller-supplied per-platform inputs, it runs a day-by-day backlog calculation and
reports demand, assumed capacity, calls served and calls left in backlog.

Labels, all enforced in the output:
- Every budget (app_daily_call_budget, per_account_daily_call_budget) is a
  caller-supplied ASSUMPTION. It is not a real platform quota, no platform number
  is built into this module, and nothing here enforces a quota.
- Every account count and activity rate is SYNTHETIC. No account exists, is
  contacted, or is managed.
- There is no external action: no network, no platform API, no adapter, no
  credentials, no clock, no randomness, and no import from the rest of Atlas.
- There is no performance claim. The module reports arithmetic on its inputs only.
  It does not measure speed or throughput of anything.

What it honestly cannot cover:
- Literal 500k live managed accounts per platform

Model, per platform, for day d = 0 .. horizon_days-1:
  active(d)     = min(accounts, ceil(accounts * (d + 1) / ramp_days))
  demand_new(d) = active(d) * actions_per_account_per_day * calls_per_action
  capacity(d)   = min of the supplied budgets: app_daily_call_budget and
                  active(d) * per_account_daily_call_budget
  served(d)     = min(backlog(d-1) + demand_new(d), capacity(d))
  backlog(d)    = backlog(d-1) + demand_new(d) - served(d)
Platforms are independent. Integer arithmetic only.
"""
from __future__ import annotations

from typing import Any, Mapping

MAX_ACCOUNTS = 1_000_000
MAX_PLATFORMS = 32
MAX_HORIZON_DAYS = 366
_MAX_BUDGET_APP = 10 ** 12
_MAX_BUDGET_PER_ACCOUNT = 10 ** 9
_MAX_ACTIONS = 10_000
_MAX_CALLS = 100
GAP = 'Literal 500k live managed accounts per platform'
_KEYS = {'platform', 'accounts', 'actions_per_account_per_day', 'calls_per_action',
         'app_daily_call_budget', 'per_account_daily_call_budget', 'ramp_days'}
_REQUIRED = {'platform', 'accounts', 'actions_per_account_per_day', 'calls_per_action'}


def _int(name: str, value: Any, lo: int, hi: int) -> int:
    if type(value) is not int:  # rejects bool, float and str
        raise ValueError(f'{name} must be an int')
    if not lo <= value <= hi:
        raise ValueError(f'{name} must be between {lo} and {hi}')
    return value


def _normalize(raw: Any) -> dict:
    if not isinstance(raw, Mapping):
        raise ValueError('each platform spec must be a mapping')
    unknown = set(raw) - _KEYS
    if unknown:
        raise ValueError(f'unknown spec keys: {sorted(unknown)}')
    missing = _REQUIRED - set(raw)
    if missing:
        raise ValueError(f'missing spec keys: {sorted(missing)}')
    name = raw['platform']
    if not isinstance(name, str) or not name.strip() or len(name) > 64:
        raise ValueError('platform must be a non-empty string of at most 64 characters')
    out = {
        'platform': name,
        'accounts': _int('accounts', raw['accounts'], 1, MAX_ACCOUNTS),
        'actions_per_account_per_day': _int('actions_per_account_per_day', raw['actions_per_account_per_day'], 0, _MAX_ACTIONS),
        'calls_per_action': _int('calls_per_action', raw['calls_per_action'], 1, _MAX_CALLS),
        'ramp_days': _int('ramp_days', raw.get('ramp_days', 1), 1, MAX_HORIZON_DAYS),
        'app_daily_call_budget': None,
        'per_account_daily_call_budget': None,
    }
    if raw.get('app_daily_call_budget') is not None:
        out['app_daily_call_budget'] = _int('app_daily_call_budget', raw['app_daily_call_budget'], 0, _MAX_BUDGET_APP)
    if raw.get('per_account_daily_call_budget') is not None:
        out['per_account_daily_call_budget'] = _int('per_account_daily_call_budget', raw['per_account_daily_call_budget'],
                                                    0, _MAX_BUDGET_PER_ACCOUNT)
    if out['app_daily_call_budget'] is None and out['per_account_daily_call_budget'] is None:
        raise ValueError('at least one budget assumption is required; none is built in')
    return out


def _simulate_one(spec: dict, horizon_days: int) -> dict:
    d_calls = spec['actions_per_account_per_day'] * spec['calls_per_action']
    backlog = peak = total_demand = total_served = over = 0
    first_over = None
    days = []
    active = 0
    served = 0
    for day in range(horizon_days):
        active = min(spec['accounts'], -(-spec['accounts'] * (day + 1) // spec['ramp_days']))
        demand = active * d_calls
        caps = []
        if spec['app_daily_call_budget'] is not None:
            caps.append(spec['app_daily_call_budget'])
        if spec['per_account_daily_call_budget'] is not None:
            caps.append(active * spec['per_account_daily_call_budget'])
        capacity = min(caps)
        available = backlog + demand
        served = min(available, capacity)
        backlog = available - served
        peak = max(peak, backlog)
        total_demand += demand
        total_served += served
        if demand > capacity:
            over += 1
            if first_over is None:
                first_over = day
        days.append({'day': day, 'active_accounts': active, 'demand_new': demand, 'capacity': capacity,
                     'served': served, 'backlog_end': backlog})
    return {
        'platform': spec['platform'],
        'synthetic_accounts': spec['accounts'],
        'assumptions': {
            'label': 'ASSUMPTION',
            'actions_per_account_per_day': spec['actions_per_account_per_day'],
            'calls_per_action': spec['calls_per_action'],
            'app_daily_call_budget': spec['app_daily_call_budget'],
            'per_account_daily_call_budget': spec['per_account_daily_call_budget'],
            'ramp_days': spec['ramp_days'],
        },
        'days': days,
        'summary': {
            'total_demand': total_demand, 'total_served': total_served, 'final_backlog': backlog,
            'peak_backlog': peak, 'days_over_capacity': over, 'first_day_over_capacity': first_over,
            'saturated': backlog > 0,
            'per_account_served_last_day': served // active,  # floor division of synthetic numbers
        },
    }


def simulate_envelope(specs: Any, *, horizon_days: int) -> dict:
    """Run the model for 1..MAX_PLATFORMS platform specs. Output is sorted by platform name."""
    horizon = _int('horizon_days', horizon_days, 1, MAX_HORIZON_DAYS)
    if not isinstance(specs, list) or not specs:
        raise ValueError('specs must be a non-empty list')
    if len(specs) > MAX_PLATFORMS:
        raise ValueError(f'at most {MAX_PLATFORMS} platforms')
    normalized = [_normalize(s) for s in specs]
    names = [s['platform'] for s in normalized]
    if len(set(names)) != len(names):
        raise ValueError('duplicate platform name')
    platforms = [_simulate_one(s, horizon) for s in sorted(normalized, key=lambda s: s['platform'])]
    return {
        'horizon_days': horizon,
        'platforms': platforms,
        'totals': {
            'accounts': sum(p['synthetic_accounts'] for p in platforms),
            'total_demand': sum(p['summary']['total_demand'] for p in platforms),
            'total_served': sum(p['summary']['total_served'] for p in platforms),
            'final_backlog': sum(p['summary']['final_backlog'] for p in platforms),
        },
        'budgets_are_assumptions': True,
        'counts_are_synthetic': True,
        'external_actions_taken': 0,
        'not_claimed': [GAP, 'Budgets here are caller-supplied assumptions, not real platform quotas.',
                        'No performance or throughput is measured or claimed.'],
    }


def steady_state_account_limit(spec: Any) -> dict:
    """Largest synthetic account count whose steady daily demand fits the assumed budgets.

    limit is None when the assumptions put no bound on it (no demand, or only a
    per-account budget that already covers each account's demand).
    """
    s = _normalize(spec)
    d_calls = s['actions_per_account_per_day'] * s['calls_per_action']
    app, per = s['app_daily_call_budget'], s['per_account_daily_call_budget']
    if d_calls == 0:
        limit, reason = None, 'no demand'
    elif per is not None and d_calls > per:
        limit, reason = 0, 'per_account_budget_below_per_account_demand'
    elif app is not None:
        limit, reason = app // d_calls, 'app_daily_call_budget'
    else:
        limit, reason = None, 'only a per-account budget was assumed; no platform-wide cap'
    return {'platform': s['platform'], 'limit': limit, 'reason': reason, 'label': 'ASSUMPTION-derived, synthetic'}
