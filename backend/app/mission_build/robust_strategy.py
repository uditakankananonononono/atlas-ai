"""Finite-scenario minimax-regret strategy choice, not predicted effectiveness."""
from fractions import Fraction
from .exact_math import rational


def optimize(payload):
    rows = payload.get('options')
    scenarios = payload.get('scenarios')
    budget = rational(payload.get('budget'))
    if budget < 0 or type(rows) is not list or not 1 <= len(rows) <= 100:
        raise ValueError('nonnegative budget and 1..100 options required')
    if type(scenarios) is not list or not 1 <= len(scenarios) <= 100:
        raise ValueError('1..100 scenarios required')
    if any(type(s) is not str or not s.strip() or len(s) > 120 for s in scenarios) or len(set(scenarios)) != len(scenarios):
        raise ValueError('distinct scenario identifiers required')
    options = []
    ids = set()
    for row in rows:
        ident = row.get('id')
        if type(ident) is not str or not ident.strip() or len(ident) > 120 or ident in ids:
            raise ValueError('distinct option identifiers required')
        ids.add(ident)
        cost = rational(row.get('cost'))
        if cost < 0:
            raise ValueError('nonnegative cost required')
        outcomes = row.get('utility')
        if type(outcomes) is not dict or set(outcomes) != set(scenarios):
            raise ValueError('exact scenario utility coverage required')
        values = {s: rational(outcomes[s]) for s in scenarios}
        if cost <= budget:
            options.append((ident, cost, values))
    if not options:
        return {'status': 'no_feasible_option', 'choice': None, 'effectiveness_verified': False}
    ideals = {s: max(values[s] for _, _, values in options) for s in scenarios}
    reports = []
    for ident, cost, values in options:
        regret = {s: ideals[s] - values[s] for s in scenarios}
        reports.append({'id': ident, 'cost': str(cost), 'worst_utility': str(min(values.values())),
                        'max_regret': str(max(regret.values())), 'regret': {s: str(v) for s, v in regret.items()}})
    reports.sort(key=lambda r: (Fraction(r['max_regret']), -Fraction(r['worst_utility']), Fraction(r['cost']), r['id']))
    return {'status': 'optimized_supplied_scenarios', 'choice': reports[0]['id'], 'ranking': reports,
            'scenario_ideals': {s: str(v) for s, v in ideals.items()}, 'effectiveness_verified': False,
            'method': 'minimax regret; tie-break worst utility, cost, id',
            'assumptions': 'Utilities are caller assumptions, not measured forecasts. No external action.'}
