"""V6 / c30.worldclass - world-class benchmark board.

Records SUPPLIED benchmark runs of Atlas/Claire against SUPPLIED reported
baselines (each with source URL and date) and prints the numbers. Claims are
limited to measured ones: the unit never says Atlas is 'world class' or
beats a named product without the computed margin and the supplied baseline
source. Nothing is run or fetched here; runs and baselines are supplied and
unverified. Stdlib only, deterministic.
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import date
from urllib.parse import urlsplit

from app.modules.c30 import policy

PREFIX = 'PLAN'

MAX_RUNS = 500
MAX_BASELINES = 500
MAX_FIELD = 200
MAX_URL = 2000
EPSILON = 1e-9

_TOP_KEYS = {'as_of', 'runs', 'baselines'}
_RUN_KEYS = {'benchmark', 'metric', 'higher_is_better', 'value', 'run_id',
             'run_date'}
_BASELINE_KEYS = {'benchmark', 'metric', 'name', 'value', 'source_url',
                  'reported_date'}

_SEND = frozenset({'send', 'approve', 'approved', 'approval',
                   'approval_token', 'smtp', 'token', 'email_send', 'sender',
                   'smtp_host', 'smtp_port', 'smtp_user'})
_SPEND = frozenset({'pay', 'purchase', 'spend', 'buy', 'checkout',
                    'card_number'})
_EFFECT = frozenset({'publish', 'post', 'file', 'register', 'submit',
                     'signup', 'sign_up', 'trade'})
_NOCREDS = frozenset({'login', 'password', 'username', 'credentials', 'otp',
                      'api_key', 'access_token', 'refresh_token', 'bearer',
                      'pass', 'passwd'})
_FORBIDDEN = (('SEND', _SEND), ('SPEND', _SPEND), ('EFFECT', _EFFECT),
              ('NOCREDS', _NOCREDS))

_DATE_SHAPE = re.compile(r'\d{4}-\d{2}-\d{2}')


def _refuse(reason: str, field: str = '') -> str:
    return PREFIX + '_REFUSED_' + reason + (':' + field if field else '')


def _children(node):
    return node.items() if type(node) is dict else enumerate(node)


def _admit(node, field, depth, active, budget):
    if depth > 32:
        raise ValueError(_refuse('OVERSIZE', field))
    if type(node) not in (dict, list):
        if isinstance(node, (dict, list)):
            raise ValueError(_refuse('BAD_TYPE', field))
        return
    budget[0] += 1
    if budget[0] > 10000:
        raise ValueError(_refuse('OVERSIZE', field))
    identity = id(node)
    if identity in active:
        raise ValueError(_refuse('BAD_TYPE', 'request'))
    cap = (500 if field in ('runs', 'baselines') else 200) if type(node) is list else 200
    if len(node) > cap:
        raise ValueError(_refuse('OVERSIZE', field))
    if type(node) is dict:
        for key in node:
            if type(key) is not str:
                raise ValueError(_refuse('BAD_TYPE', 'key'))
            if len(key) > 200:
                raise ValueError(_refuse('OVERSIZE', 'key'))
    active.add(identity)
    for key, value in _children(node):
        child_field = key if type(node) is dict and key in ('runs', 'baselines') else field
        _admit(value, child_field, depth + 1, active, budget)
    active.remove(identity)


def _scan_forbidden(node, matches):
    # Admit the complete tree before normalization or collecting any keys.
    # Iterator recursion is depth-bounded and creates no child-copy/list.
    _admit(node, 'request', 0, set(), [0])
    def collect(value):
        if type(value) is dict:
            for key, child in value.items():
                norm = key.casefold().replace('-', '_')
                for cls, table in _FORBIDDEN:
                    if norm in table:
                        matches[cls].add(norm)
                collect(child)
        elif type(value) is list:
            for child in value:
                collect(child)
    collect(node)


def _strict_date(value, field):
    ok = isinstance(value, str) and bool(_DATE_SHAPE.fullmatch(value))
    if ok:
        try:
            date.fromisoformat(value)
        except ValueError:
            ok = False
    if not ok:
        raise ValueError(_refuse('BAD_TYPE', field))


_URL_BAD_CATS = ('Cc', 'Cf', 'Zl', 'Zp', 'Zs')
_FIELD_BAD_CATS = ('Cc', 'Cf', 'Zl', 'Zp')


def _url_bad_chars(text: str) -> bool:
    return any(ord(c) <= 32 or ord(c) == 127
               or unicodedata.category(c) in _URL_BAD_CATS for c in text)


def _field_bad_chars(text: str) -> bool:
    return any(unicodedata.category(c) in _FIELD_BAD_CATS for c in text)


def _field_text(value, name):
    if isinstance(value, str) and len(value) > MAX_FIELD:
        raise ValueError(_refuse('OVERSIZE', name))
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError(_refuse('BAD_TYPE', name))
    if not value.strip():
        raise ValueError(_refuse('EMPTY', name))
    if _field_bad_chars(value):
        raise ValueError(_refuse('BAD_TYPE', name))
    return policy.clean_text(value, PREFIX, name, MAX_FIELD)


def _numeric(value, field):
    if (isinstance(value, bool)
            or not isinstance(value, (int, float))
            or (isinstance(value, float)
                and (math.isnan(value) or math.isinf(value)))):
        raise ValueError(_refuse('BAD_TYPE', field))


def _https_ok(url: str) -> bool:
    if not url.strip():
        return False
    if _url_bad_chars(url):
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme.casefold() != 'https':
        return False
    if parts.username is not None or parts.password is not None:
        return False
    if not parts.hostname:
        return False
    return True


def _validate(request):
    if type(request) is not dict:
        raise ValueError(_refuse('BAD_TYPE', 'request'))
    matches = {cls: set() for cls, _ in _FORBIDDEN}
    _scan_forbidden(request, matches)
    for cls, _ in _FORBIDDEN:
        if matches[cls]:
            raise ValueError(_refuse(cls, sorted(matches[cls])[0]))
    for key in request:
        if not isinstance(key, str):
            raise ValueError(_refuse('BAD_TYPE', 'key'))
    for key in sorted(set(request) - _TOP_KEYS):
        raise ValueError(_refuse('UNKNOWN', 'request'))
    as_of = request.get('as_of')
    _strict_date(as_of, 'as_of')
    runs = request.get('runs')
    baselines = request.get('baselines')
    if not isinstance(runs, list):
        raise ValueError(_refuse('BAD_TYPE', 'runs'))
    if not isinstance(baselines, list):
        raise ValueError(_refuse('BAD_TYPE', 'baselines'))
    if not runs:
        raise ValueError(_refuse('EMPTY', 'runs'))
    if not baselines:
        raise ValueError(_refuse('EMPTY', 'baselines'))
    if len(runs) > MAX_RUNS:
        raise ValueError(_refuse('OVERSIZE', 'runs'))
    if len(baselines) > MAX_BASELINES:
        raise ValueError(_refuse('OVERSIZE', 'baselines'))
    seen_run_ids = set()
    clean_runs = []
    for r in runs:
        if not isinstance(r, dict):
            raise ValueError(_refuse('BAD_TYPE', 'runs'))
        for key in sorted(set(r) - _RUN_KEYS):
            raise ValueError(_refuse('UNKNOWN', 'runs'))
        benchmark = _field_text(r.get('benchmark'), 'benchmark')
        metric = _field_text(r.get('metric'), 'metric')
        hib = r.get('higher_is_better')
        if not isinstance(hib, bool):
            raise ValueError(_refuse('BAD_TYPE', 'runs'))
        _numeric(r.get('value'), 'runs')
        run_id = _field_text(r.get('run_id'), 'run_id')
        if run_id in seen_run_ids:
            raise ValueError(_refuse('BAD_TYPE', 'runs'))
        seen_run_ids.add(run_id)
        run_date = r.get('run_date')
        _strict_date(run_date, 'run_date')
        if run_date > as_of:
            raise ValueError(_refuse('BAD_TYPE', 'run_date'))
        clean_runs.append({'benchmark': benchmark, 'metric': metric,
                           'higher_is_better': hib, 'value': r['value'],
                           'run_id': run_id, 'run_date': run_date})
    seen_baselines = set()
    clean_baselines = []
    for b in baselines:
        if not isinstance(b, dict):
            raise ValueError(_refuse('BAD_TYPE', 'baselines'))
        for key in sorted(set(b) - _BASELINE_KEYS):
            raise ValueError(_refuse('UNKNOWN', 'baselines'))
        benchmark = _field_text(b.get('benchmark'), 'benchmark')
        metric = _field_text(b.get('metric'), 'metric')
        name = _field_text(b.get('name'), 'name')
        _numeric(b.get('value'), 'baselines')
        dup_key = (benchmark, metric, name)
        if dup_key in seen_baselines:
            raise ValueError(_refuse('BAD_TYPE', 'baselines'))
        seen_baselines.add(dup_key)
        url = b.get('source_url')
        if url is not None and not isinstance(url, str):
            raise ValueError(_refuse('BAD_TYPE', 'baselines'))
        if url is not None and len(url) > MAX_URL:
            raise ValueError(_refuse('OVERSIZE', 'source_url'))
        reported_date = b.get('reported_date')
        _strict_date(reported_date, 'reported_date')
        clean_baselines.append({'benchmark': benchmark, 'metric': metric,
                                'name': name, 'value': b['value'],
                                'source_url': url,
                                'reported_date': reported_date})
    return as_of, clean_runs, clean_baselines


def run(request: dict) -> dict:
    as_of, runs, baselines = _validate(request)
    no_source = 0
    future_date = 0
    surviving = []
    for b in baselines:
        if b['source_url'] is None or not _https_ok(b['source_url']):
            no_source += 1
            continue
        if b['reported_date'] > as_of:
            future_date += 1  # future_date drop, never raised
            continue
        surviving.append(b)
    matched_flags = [False] * len(surviving)
    pairs = []
    no_baseline_rows = []
    counts = {'ahead': 0, 'behind': 0, 'tied': 0, 'no_baseline': 0,
              'no_source': no_source}
    for r in runs:
        matched = [(j, b) for j, b in enumerate(surviving)
                   if b['benchmark'] == r['benchmark']
                   and b['metric'] == r['metric']]
        if not matched:
            no_baseline_rows.append({'benchmark': r['benchmark'],
                                     'metric': r['metric'],
                                     'run_id': r['run_id'],
                                     'value': r['value']})
            counts['no_baseline'] += 1
            continue
        for j, b in matched:
            matched_flags[j] = True
            if r['higher_is_better']:
                margin = r['value'] - b['value']
            else:
                margin = b['value'] - r['value']
            flags = []
            if b['value'] != 0:
                relative = round(margin / abs(b['value']), 6)
            else:
                relative = None
                flags.append('baseline_zero')
            if margin > EPSILON:
                verdict = 'ahead'
            elif margin < -EPSILON:
                verdict = 'behind'
            else:
                verdict = 'tied'
            counts[verdict] += 1
            pairs.append({'benchmark': r['benchmark'], 'metric': r['metric'],
                          'run_id': r['run_id'], 'baseline_name': b['name'],
                          'value': r['value'], 'baseline_value': b['value'],
                          'margin': round(margin, 6),
                          'relative_margin': relative, 'flags': flags,
                          'verdict': verdict, 'source_url': b['source_url'],
                          'run_date': r['run_date'],
                          'reported_date': b['reported_date']})
    if not pairs:
        raise ValueError(_refuse('UNMEASURED'))
    matched_n = sum(1 for f in matched_flags if f)
    baseline_coverage = {
        'baselines_supplied': len(baselines),
        'baselines_matched': matched_n,
        'baselines_unmatched': len(surviving) - matched_n,
        'baselines_dropped_by_reason': {'no_source': no_source,
                                        'future_date': future_date},
    }
    return {'pairs': pairs, 'no_baseline_rows': no_baseline_rows,
            'counts': counts, 'baseline_coverage': baseline_coverage,
            'scope': policy.scope(
                ['supplied benchmark run vs supplied baseline pairing',
                 'margin and relative margin with direction and tie epsilon',
                 'verdict ahead/behind/tied from unrounded margin'],
                ['running benchmarks', 'fetching or verifying sources',
                 'publishing or filing results',
                 'any claim beyond measured supplied numbers'],
                'supplied-unverified', as_of)}
