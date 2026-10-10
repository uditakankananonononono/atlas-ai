"""AUTHORED, NOT RUN. Hermetic tests for the deterministic M06 envelope simulation.

All expected numbers are computed by hand in the comments, not by calling the code under test.
"""
import ast
import copy
import json
from pathlib import Path

import pytest

from app.modules.m06_social_media_manager import scale_simulation as sim

SRC = Path(__file__).resolve().parents[2] / 'backend/app/modules/m06_social_media_manager/scale_simulation.py'


def spec(platform='p1', accounts=1000, actions=2, calls=3, app=None, per_account=None, ramp=1):
    d = {'platform': platform, 'accounts': accounts, 'actions_per_account_per_day': actions,
         'calls_per_action': calls, 'ramp_days': ramp}
    if app is not None:
        d['app_daily_call_budget'] = app
    if per_account is not None:
        d['per_account_daily_call_budget'] = per_account
    return d


def one(s, days):
    return sim.simulate_envelope([s], horizon_days=days)['platforms'][0]


# ---- honesty of the module itself -------------------------------------------------

def test_docstring_has_the_named_gap_verbatim_and_the_labels():
    doc = ast.get_docstring(ast.parse(SRC.read_text()))
    assert 'Literal 500k live managed accounts per platform' in doc
    for needle in ('ASSUMPTION', 'SYNTHETIC', 'no external action', 'not a quota'):
        assert needle.lower() in doc.lower(), needle


def test_module_is_pure_stdlib_with_no_network_clock_random_or_atlas_imports():
    tree = ast.parse(SRC.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split('.')[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or '').split('.')[0])
    assert mods <= {'__future__', 'dataclasses', 'typing', 'collections'}, mods


def test_output_labels_budgets_as_assumptions_counts_as_synthetic_and_no_external_actions():
    out = sim.simulate_envelope([spec(app=10000)], horizon_days=1)
    assert out['budgets_are_assumptions'] is True and out['counts_are_synthetic'] is True
    assert out['external_actions_taken'] == 0
    assert 'Literal 500k live managed accounts per platform' in out['not_claimed']
    p = out['platforms'][0]
    assert p['assumptions']['label'] == 'ASSUMPTION' and p['synthetic_accounts'] == 1000
    json.dumps(out)  # JSON-serialisable


# ---- day-by-day backlog arithmetic (hand computed) -----------------------------------

def test_demand_within_budget_is_fully_served_without_backlog():
    # demand/day = 1000*2*3 = 6000 <= 10000
    p = one(spec(app=10000), 3)
    assert [d['demand_new'] for d in p['days']] == [6000] * 3
    assert [d['served'] for d in p['days']] == [6000] * 3
    assert p['summary'] == {**p['summary'], 'total_demand': 18000, 'total_served': 18000,
                            'final_backlog': 0, 'peak_backlog': 0, 'days_over_capacity': 0,
                            'first_day_over_capacity': None, 'saturated': False}


def test_overload_accumulates_backlog():
    # demand/day = 1000*5*2 = 10000, capacity 6000: backlog 4000, 8000, 12000
    p = one(spec(actions=5, calls=2, app=6000), 3)
    assert [d['served'] for d in p['days']] == [6000, 6000, 6000]
    assert [d['backlog_end'] for d in p['days']] == [4000, 8000, 12000]
    s = p['summary']
    assert (s['total_demand'], s['total_served'], s['final_backlog'], s['peak_backlog']) == (30000, 18000, 12000, 12000)
    assert (s['days_over_capacity'], s['first_day_over_capacity'], s['saturated']) == (3, 0, True)


def test_constant_overload_backlog_grows_by_the_same_shortfall_each_day():
    # accounts 10, a=1, c=1, app=7: demand 10 per day, shortfall 3 per day -> backlog 3, 6, 9
    p = one(spec(accounts=10, actions=1, calls=1, app=7), 3)
    assert [d['backlog_end'] for d in p['days']] == [3, 6, 9]


def test_ramp_uses_integer_ceiling_of_active_accounts():
    # accounts 10, ramp 4 days: ceil(10/4)=3, ceil(20/4)=5, ceil(30/4)=8, 10, 10
    p = one(spec(accounts=10, actions=1, calls=1, app=100, ramp=4), 5)
    assert [d['active_accounts'] for d in p['days']] == [3, 5, 8, 10, 10]
    assert p['summary']['total_demand'] == 36


def test_per_account_budget_scales_capacity_with_active_accounts():
    # accounts 100, a=3, c=1 (demand 300), per-account 2 -> capacity 200: backlog 100, then avail 400 served 200 backlog 200
    p = one(spec(accounts=100, actions=3, calls=1, per_account=2), 2)
    assert [d['capacity'] for d in p['days']] == [200, 200]
    assert [d['backlog_end'] for d in p['days']] == [100, 200]


def test_both_budgets_apply_and_the_smaller_wins():
    # per-account capacity 100*5=500, app 50 -> capacity 50, demand 100
    p = one(spec(accounts=100, actions=1, calls=1, app=50, per_account=5), 1)
    assert p['days'][0]['capacity'] == 50 and p['days'][0]['served'] == 50 and p['days'][0]['backlog_end'] == 50
    p2 = one(spec(accounts=100, actions=1, calls=1, app=5000, per_account=3), 1)
    assert p2['days'][0]['capacity'] == 300


def test_per_account_served_is_a_floor_of_last_day_served_over_active_accounts():
    p = one(spec(accounts=1000, actions=5, calls=2, app=6000), 2)
    assert p['summary']['per_account_served_last_day'] == 6      # 6000 // 1000
    p = one(spec(accounts=7, actions=1, calls=1, app=10), 1)
    assert p['summary']['per_account_served_last_day'] == 1      # 7 // 7


def test_five_hundred_thousand_synthetic_accounts_arithmetic():
    # 500000*2*1 = 1,000,000 demand/day, capacity 900,000: backlog 100,000 then 200,000
    p = one(spec(accounts=500000, actions=2, calls=1, app=900000), 2)
    assert [d['served'] for d in p['days']] == [900000, 900000]
    assert [d['backlog_end'] for d in p['days']] == [100000, 200000]


def test_zero_demand_is_valid_and_serves_nothing():
    p = one(spec(actions=0, app=10), 2)
    assert p['summary']['total_demand'] == 0 and p['summary']['saturated'] is False


def test_zero_budget_serves_nothing_and_backlogs_everything():
    p = one(spec(accounts=10, actions=1, calls=1, app=0), 2)
    assert [d['served'] for d in p['days']] == [0, 0] and p['summary']['final_backlog'] == 20


# ---- steady-state account limit ------------------------------------------------------

def test_steady_state_limit_cases():
    lim = lambda **kw: sim.steady_state_account_limit(spec(**kw))
    assert lim(actions=2, calls=3, app=10000)['limit'] == 1666           # 10000 // 6
    assert lim(actions=3, calls=1, per_account=2)['limit'] == 0          # each account exceeds its own budget
    assert lim(actions=0, calls=1, app=10)['limit'] is None              # no demand
    assert lim(actions=2, calls=1, per_account=5)['limit'] is None       # no platform-wide cap assumed
    assert lim(actions=2, calls=1, app=100, per_account=2)['limit'] == 50
    assert lim(actions=2, calls=1, app=100, per_account=1)['limit'] == 0


# ---- multi platform, determinism, input handling -----------------------------------------

def test_platforms_are_independent_sorted_and_totals_add_up():
    a = spec('zeta', accounts=100, actions=1, calls=1, app=1000)      # demand 100/day
    b = spec('alpha', accounts=200, actions=1, calls=1, app=50)       # demand 200/day, served 50
    out = sim.simulate_envelope([a, b], horizon_days=2)
    assert [p['platform'] for p in out['platforms']] == ['alpha', 'zeta']
    assert out['totals'] == {'accounts': 300, 'total_demand': 600, 'total_served': 300, 'final_backlog': 300}
    assert out == sim.simulate_envelope([b, a], horizon_days=2)


def test_deterministic_and_does_not_mutate_input():
    s = [spec(app=100), spec('p2', per_account=1)]
    before = copy.deepcopy(s)
    assert sim.simulate_envelope(s, horizon_days=4) == sim.simulate_envelope(s, horizon_days=4)
    assert s == before


@pytest.mark.parametrize('bad', [
    spec(),                                       # no budget assumption at all
    spec(app=-1), spec(per_account=-1),
    spec(app=True), spec(app=1.5), spec(app='10'),
    spec(accounts=0), spec(accounts=sim.MAX_ACCOUNTS + 1), spec(accounts=True), spec(accounts=1.0),
    spec(actions=-1), spec(calls=0), spec(ramp=0), spec(ramp=367),
    spec(platform=''), spec(platform=5),
    {**spec(app=10), 'daily_quota': 5},           # unknown key (typo guard)
    {k: v for k, v in spec(app=10).items() if k != 'accounts'},
    'not-a-dict',
])
def test_invalid_specs_are_refused(bad):
    with pytest.raises(ValueError):
        sim.simulate_envelope([bad], horizon_days=1)


@pytest.mark.parametrize('specs,days', [
    ([], 1), ('x', 1), (None, 1),
    ([spec(app=1), spec(app=2)], 1),                                   # duplicate platform
    ([spec(f'p{i}', app=1) for i in range(sim.MAX_PLATFORMS + 1)], 1),
    ([spec(app=1)], 0), ([spec(app=1)], 367), ([spec(app=1)], True), ([spec(app=1)], 1.5),
])
def test_invalid_batches_and_horizons_are_refused(specs, days):
    with pytest.raises(ValueError):
        sim.simulate_envelope(specs, horizon_days=days)


def test_max_bounds_are_the_documented_values():
    assert sim.MAX_ACCOUNTS == 1_000_000 and sim.MAX_PLATFORMS == 32 and sim.MAX_HORIZON_DAYS == 366
    ok = sim.simulate_envelope([spec(accounts=sim.MAX_ACCOUNTS, app=1)], horizon_days=sim.MAX_HORIZON_DAYS)
    assert len(ok['platforms'][0]['days']) == 366


# ---- R2 pins (added on top of the first delivery; hand computed; AUTHORED, NOT RUN) ----------

GAP_TEXT = 'Literal 500k live managed accounts per platform'
NOT_CLAIMED_2 = 'Budgets here are caller-supplied assumptions, not real platform quotas.'
NOT_CLAIMED_3 = 'No performance or throughput is measured or claimed.'


def test_missing_budgets_raise_and_no_platform_gets_a_built_in_budget():
    msg = 'at least one budget assumption is required; none is built in'
    for name in ('instagram', 'x', 'linkedin', 'p1'):
        with pytest.raises(ValueError, match=msg):
            sim.simulate_envelope([spec(name)], horizon_days=1)
    explicit_none = {**spec(), 'app_daily_call_budget': None, 'per_account_daily_call_budget': None}
    with pytest.raises(ValueError, match=msg):
        sim.simulate_envelope([explicit_none], horizon_days=1)
    with pytest.raises(ValueError, match=msg):
        sim.steady_state_account_limit(spec())
    # a single supplied budget (even 0) is enough, and the other one stays None in the output
    a = one(spec(app=0), 1)['assumptions']
    assert a['app_daily_call_budget'] == 0 and a['per_account_daily_call_budget'] is None
    b = one(spec(per_account=0), 1)['assumptions']
    assert b['app_daily_call_budget'] is None and b['per_account_daily_call_budget'] == 0


def test_the_not_claimed_and_label_strings_are_exact():
    out = sim.simulate_envelope([spec(app=10000)], horizon_days=1)
    assert out['not_claimed'] == [GAP_TEXT, NOT_CLAIMED_2, NOT_CLAIMED_3]
    assert out['platforms'][0]['assumptions']['label'] == 'ASSUMPTION'
    assert sim.steady_state_account_limit(spec(app=100))['label'] == 'ASSUMPTION-derived, synthetic'
    assert sim.GAP == GAP_TEXT


def test_per_account_budget_with_a_ramp_scales_capacity_by_active_accounts():
    # accounts 10, ramp 4, a=2, c=1, per-account 1. active 3,5,8,10,10; demand 6,10,16,20,20; capacity 3,5,8,10,10
    # day0 avail 6 served 3 backlog 3; day1 avail 13 served 5 backlog 8; day2 avail 24 served 8 backlog 16;
    # day3 avail 36 served 10 backlog 26; day4 avail 46 served 10 backlog 36
    p = one(spec(accounts=10, actions=2, calls=1, per_account=1, ramp=4), 5)
    assert [d['active_accounts'] for d in p['days']] == [3, 5, 8, 10, 10]
    assert [d['demand_new'] for d in p['days']] == [6, 10, 16, 20, 20]
    assert [d['capacity'] for d in p['days']] == [3, 5, 8, 10, 10]
    assert [d['served'] for d in p['days']] == [3, 5, 8, 10, 10]
    assert [d['backlog_end'] for d in p['days']] == [3, 8, 16, 26, 36]
    s = p['summary']
    assert (s['total_demand'], s['total_served'], s['final_backlog']) == (72, 36, 36)
    assert (s['days_over_capacity'], s['first_day_over_capacity'], s['per_account_served_last_day']) == (5, 0, 1)


def test_peak_backlog_is_the_maximum_of_the_daily_backlog_series():
    # accounts 10, ramp 2, a=1, c=1, app 7. active 5,10,10; demand 5,10,10
    # day0 avail 5 served 5 backlog 0; day1 avail 10 served 7 backlog 3; day2 avail 13 served 7 backlog 6
    p = one(spec(accounts=10, actions=1, calls=1, app=7, ramp=2), 3)
    assert [d['backlog_end'] for d in p['days']] == [0, 3, 6]
    s = p['summary']
    assert s['peak_backlog'] == max(d['backlog_end'] for d in p['days']) == 6
    assert (s['days_over_capacity'], s['first_day_over_capacity'], s['final_backlog']) == (2, 1, 6)
    # no overload at all: peak stays 0, not some later or earlier value
    assert one(spec(accounts=10, actions=1, calls=1, app=7, ramp=2), 1)['summary']['peak_backlog'] == 0


def test_demand_equal_to_capacity_is_not_overload_and_one_more_call_is():
    # accounts 10, a=5, c=2 -> demand 100 per day
    eq = one(spec(accounts=10, actions=5, calls=2, app=100), 3)['summary']
    assert (eq['final_backlog'], eq['peak_backlog'], eq['days_over_capacity']) == (0, 0, 0)
    assert (eq['first_day_over_capacity'], eq['saturated'], eq['total_served']) == (None, False, 300)
    over = one(spec(accounts=10, actions=5, calls=2, app=99), 3)['summary']
    assert (over['final_backlog'], over['days_over_capacity'], over['first_day_over_capacity']) == (3, 3, 0)
    assert over['saturated'] is True
    # steady-state boundary: 100 // 10 = 10 accounts fit, 99 // 10 = 9
    assert sim.steady_state_account_limit(spec(actions=5, calls=2, app=100))['limit'] == 10
    assert sim.steady_state_account_limit(spec(actions=5, calls=2, app=99))['limit'] == 9
    # per-account budget equal to per-account demand is not "below" it
    assert sim.steady_state_account_limit(spec(actions=2, calls=1, per_account=2, app=100))['limit'] == 50


def test_per_account_served_last_day_divides_by_that_days_active_accounts():
    # accounts 10, ramp 4, a=4, c=1, app 7. active 3,5,8; demand 12,20,32; served 7 every day
    # last day served 7: horizon 1 -> 7 // 3 = 2; horizon 2 -> 7 // 5 = 1; horizon 3 -> 7 // 8 = 0
    s = spec(accounts=10, actions=4, calls=1, app=7, ramp=4)
    assert [one(s, h)['summary']['per_account_served_last_day'] for h in (1, 2, 3)] == [2, 1, 0]


@pytest.mark.parametrize('kw', [
    {'app': 10 ** 12}, {'per_account': 10 ** 9, 'accounts': 1}, {'actions': 10_000, 'accounts': 1, 'app': 1},
    {'calls': 100, 'accounts': 1, 'app': 1}, {'accounts': 1, 'app': 1, 'actions': 0, 'calls': 1}, {'app': 0, 'ramp': 366},
])
def test_inclusive_limits_are_accepted(kw):
    sim.simulate_envelope([spec(**kw)], horizon_days=1)


@pytest.mark.parametrize('kw', [
    {'app': 10 ** 12 + 1}, {'per_account': 10 ** 9 + 1}, {'actions': 10_001, 'app': 1},
    {'calls': 101, 'app': 1}, {'calls': 0, 'app': 1}, {'accounts': 0, 'app': 1}, {'ramp': 0, 'app': 1},
    {'ramp': 367, 'app': 1}, {'actions': -1, 'app': 1},
])
def test_values_just_outside_limits_are_refused(kw):
    with pytest.raises(ValueError):
        sim.simulate_envelope([spec(**kw)], horizon_days=1)


def test_private_limit_constants_have_the_documented_values():
    assert (sim._MAX_BUDGET_APP, sim._MAX_BUDGET_PER_ACCOUNT, sim._MAX_ACTIONS, sim._MAX_CALLS) == (10 ** 12, 10 ** 9, 10_000, 100)


def test_platform_name_rules_blank_whitespace_only_and_length():
    for bad in ('', ' ', '   ', '\t'):
        with pytest.raises(ValueError):
            sim.simulate_envelope([spec(bad, app=1)], horizon_days=1)
    sim.simulate_envelope([spec('a' * 64, app=1)], horizon_days=1)
    with pytest.raises(ValueError):
        sim.simulate_envelope([spec('a' * 65, app=1)], horizon_days=1)


def test_lower_bounds_of_one_and_the_horizon_edges():
    p = one(spec(accounts=1, actions=1, calls=1, app=1, ramp=1), 1)
    assert p['days'][0]['active_accounts'] == 1 and p['summary']['total_served'] == 1
    assert len(one(spec(app=1), 366)['days']) == 366


def test_ramp_days_defaults_to_one_when_omitted():
    s = {'platform': 'p1', 'accounts': 40, 'actions_per_account_per_day': 1, 'calls_per_action': 1,
         'app_daily_call_budget': 1000}
    p = one(s, 2)
    assert p['assumptions']['ramp_days'] == 1
    assert [d['active_accounts'] for d in p['days']] == [40, 40]


def test_specs_must_be_a_nonempty_list():
    with pytest.raises(ValueError, match='non-empty list'):
        sim.simulate_envelope([], horizon_days=1)
    with pytest.raises(ValueError, match='non-empty list'):
        sim.simulate_envelope((spec(app=1),), horizon_days=1)
    assert len(sim.simulate_envelope([spec(app=1)], horizon_days=1)['platforms']) == 1
