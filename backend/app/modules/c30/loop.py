"""Zero-effect trusted-fixture recorder. Not a sandbox or measured-time scheduler."""
from __future__ import annotations

import copy
import math
import random
from app.modules.c30 import policy

_FORBIDDEN = {'cash', 'approval_token', 'needs_approval', 'network', 'file_write', 'account'}
_ROW = {'id', 'as_of', 'outcome', 'metric_name', 'direction', 'metric_value', 'tags', 'error', 'order_index'}
_EXP = {'id', 'hypothesis', 'tags', 'expected_metric', 'runner', 'declared_seconds', 'effect', 'priority'}


def _bad(field):
    raise ValueError('PLAN_REFUSED_BAD_TYPE:' + field)


def _text(v, name):
    return policy.clean_text(v, 'PLAN', name, 1000)


def _number(v, field, positive=False):
    try:
        valid = type(v) in (int, float) and math.isfinite(v) and (not positive or v > 0)
    except OverflowError:
        valid = False
    if not valid:
        _bad(field)
    return v


def _tags(v):
    if type(v) is not list or not v or any(type(t) is not str or not t.strip() for t in v) or len(set(v)) != len(v):
        _bad('tags')
    for t in v:
        _text(t, 'tag')


def _prior(rows):
    if type(rows) is not list:
        _bad('prior_log')
    terminal = set()
    for r in rows:
        if type(r) is not dict or set(r) != _ROW:
            _bad('prior_row')
        for k in ('id', 'as_of', 'metric_name'):
            _text(r[k], k)
        _tags(r['tags'])
        if r['direction'] not in ('higher', 'lower') or r['outcome'] not in ('success', 'failure', 'skipped_budget'):
            _bad('prior_row')
        if type(r['order_index']) is not int or r['order_index'] < 0:
            _bad('order_index')
        if r['outcome'] == 'success':
            _number(r['metric_value'], 'metric_value')
            if r['error'] is not None:
                _bad('error')
        else:
            if r['metric_value'] is not None:
                _bad('metric_value')
            if r['outcome'] == 'failure':
                if type(r['error']) is not str or len(r['error']) > 200:
                    _bad('error')
            elif r['error'] is not None:
                _bad('error')
        if r['outcome'] != 'skipped_budget':
            key = (r['id'], r['as_of'])
            if key in terminal:
                _bad('duplicate_terminal')
            terminal.add(key)
    return terminal


def _validate(request):
    if type(request) is not dict or set(request) - {'as_of', 'seed', 'budget', 'prior_log', 'experiments', 'runners'}:
        _bad('request')
    _text(request.get('as_of'), 'as_of')
    seed = request.get('seed')
    if type(seed) is not int or not 0 <= seed < 2**63:
        _bad('seed')
    if 'budget' not in request:
        raise ValueError('PLAN_REFUSED_NOBUDGET')
    b = request['budget']
    if type(b) is not dict or set(b) - {'max_experiments', 'max_total_seconds', 'max_cash'}:
        _bad('budget')
    if 'max_cash' in b and (type(b['max_cash']) not in (int, float) or b['max_cash'] != 0):
        raise ValueError('PLAN_REFUSED_EFFECTFUL:max_cash')
    if type(b.get('max_experiments')) is not int or b['max_experiments'] < 1:
        _bad('max_experiments')
    _number(b.get('max_total_seconds'), 'max_total_seconds', True)
    es, runners = request.get('experiments'), request.get('runners')
    if type(es) is not list or type(runners) is not dict:
        _bad('experiments_or_runners')
    if any(type(k) is not str or not k.strip() or not callable(v) for k, v in runners.items()):
        _bad('runners')
    seen = set()
    for e in es:
        if type(e) is not dict:
            _bad('experiment')
        if _FORBIDDEN & set(e) or e.get('effect') != 'none':
            raise ValueError('PLAN_REFUSED_EFFECTFUL')
        if set(e) - _EXP:
            _bad('experiment_keys')
        m = e.get('expected_metric')
        if not isinstance(e.get('hypothesis'), str) or not e['hypothesis'].strip() or type(m) is not dict or not isinstance(m.get('name'), str) or not m['name'].strip():
            raise ValueError('PLAN_REFUSED_NOHYPOTHESIS')
        if set(m) != {'name', 'direction'} or m['direction'] not in ('higher', 'lower'):
            _bad('expected_metric')
        for k in ('id', 'hypothesis', 'runner'):
            _text(e.get(k), k)
        _text(m['name'], 'metric_name')
        _tags(e.get('tags'))
        _number(e.get('declared_seconds'), 'declared_seconds', True)
        _number(e.get('priority', 0), 'priority')
        if e['runner'] not in runners or e['id'] in seen:
            _bad('runner_or_duplicate_id')
        seen.add(e['id'])
    terminal = _prior(request.get('prior_log', []))
    return terminal


def _append_record(log, record):
    log.append(record)


def run(request):
    """Run trusted pure fixtures, returning a copied caller log and counted results."""
    terminal = _validate(request)
    es = copy.deepcopy(request['experiments'])
    prior = copy.deepcopy(request.get('prior_log', []))
    as_of = request['as_of']
    log = copy.deepcopy(prior)
    explored = {t for r in prior if r['outcome'] != 'skipped_budget' for t in r['tags']}
    remaining = [e for e in es if (e['id'], as_of) not in terminal]
    remaining.sort(key=lambda e: (not any(t not in explored for t in e['tags']), -e.get('priority', 0), e['id']))
    index = max((r['order_index'] for r in prior), default=-1) + 1
    rng = random.Random(request['seed'])
    used, tried = 0, 0
    new = []
    b = request['budget']
    for e in remaining:
        outcome, value, error = 'skipped_budget', None, None
        if tried < b['max_experiments'] and used + e['declared_seconds'] <= b['max_total_seconds']:
            tried += 1
            used += e['declared_seconds']
            try:
                result = request['runners'][e['runner']](copy.deepcopy(e), rng)
                if type(result) is not dict:
                    raise ValueError('runner result must be dict')
                value = _number(result.get('metric_value'), 'metric_value')
                value = round(float(value), 6)
                outcome = 'success'
            except Exception as exc:
                outcome, value, error = 'failure', None, str(exc)[:200]
        r = {'id': e['id'], 'as_of': as_of, 'outcome': outcome, 'metric_name': e['expected_metric']['name'],
             'direction': e['expected_metric']['direction'], 'metric_value': value,
             'tags': list(e['tags']), 'error': error, 'order_index': index}
        index += 1
        new.append(r)
        _append_record(log, copy.deepcopy(r))
    if log[:len(prior)] != prior or log[len(prior):] != new or len(new) != len(remaining):
        raise ValueError('PLAN_REFUSED_UNRECORDED')
    tags = sorted({t for e in es for t in e['tags']})
    counts = {}
    for t in tags:
        defined = sum(t in e['tags'] for e in es)
        successes = sum(t in r['tags'] and r['outcome'] == 'success' for r in new)
        failures = sum(t in r['tags'] and r['outcome'] == 'failure' for r in new)
        skipped = sum(t in r['tags'] and r['outcome'] == 'skipped_budget' for r in new)
        suppressed = sum(t in e['tags'] and (e['id'], as_of) in terminal for e in es)
        counts[t] = dict(defined=defined, tried_success=successes, tried_failure=failures,
                         skipped_budget=skipped, untried=defined-successes-failures-suppressed)
    groups = {}
    for r in log:
        if r['outcome'] == 'success':
            for t in r['tags']:
                groups.setdefault((t, r['metric_name'], r['direction']), []).append(r['metric_value'])
    stats = []
    for (tag, name, direction), values in sorted(groups.items()):
        best, worst = (max(values), min(values)) if direction == 'higher' else (min(values), max(values))
        stats.append(dict(tag=tag, metric_name=name, direction=direction, best=best, worst=worst, count=len(values)))
    return dict(log=log, tried=tried, succeeded=sum(r['outcome']=='success' for r in new),
                failed=sum(r['outcome']=='failure' for r in new), skipped=sum(r['outcome']=='skipped_budget' for r in new),
                suppressed_replays=len(es)-len(remaining), defined=len(es), declared_seconds_used=round(used,6),
                tag_counts=counts, metric_stats=stats, text=f'tried {tried} of {len(es)} defined experiments',
                scope=policy.scope(['tag novelty ordering', 'copied attempt log', 'declared-unit budgets', 'replay suppression', 'tag counts'],
                                   ['sandbox or purity verification', 'preemptive timing', 'learning policy', 'persistence', 'effects'],
                                   'supplied trusted fixtures and caller history', as_of))
