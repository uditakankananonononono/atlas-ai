"""Bounded exact integrative-bargaining priority audit (row 94).

Not shipped product code. Given one issue list and each party's stated
priority weights (exact integers or "p/q" rational strings), this module
computes, with exact Fraction arithmetic, each party's normalized priority
per issue, the efficient holder per issue (with ties reported as 'tie',
never silently assigned), per-issue complementarity, the deterministic
tradeoff order, and exact joint-gain and logrolling-vs-naive figures as
exact "p/q" strings. It reports no confidence scores, no probability
estimates and no rounded floats. A zero-sum party, misaligned lengths,
negative or non-rational weights, duplicate or oversize issue lists, and
any request to deceive, mislead, hide, conceal, exploit or manipulate the
counterparty are refused with a stated code. It is an audit aid for a human
reviewer comparing stated priorities; it does not advise on negotiation
strategy and its efficient-holder output is a mechanical property of the
declared numbers, not a claim that any agreement is achievable or fair.
"""
from __future__ import annotations

import re
import unicodedata
from fractions import Fraction

_CODE = 'INTEGR94'
_KEYS = frozenset({'issues', 'party_a_weights', 'party_b_weights'})
_BANNED_KEYS = ('deceive', 'mislead', 'hide', 'conceal', 'exploit', 'manipulate')
MAX_ISSUES = 64
MAX_KEYS = 64
MAX_KEY_LEN = 128
_KEY_BANNED_CATS = ('Cc', 'Cf', 'Zl', 'Zp')
MAX_INT_WEIGHT = 10**18 - 1
MAX_WEIGHT_STR_LEN = 40
_WEIGHT_RE = re.compile(r'^[0-9]{1,18}(/[0-9]{1,18})?$')
_LIMITS = [
    'This module is a bounded exact integrative-bargaining audit aid, not shipped product code.',
    'Weights are stated priorities normalized exactly per party; ordinal misstatements change the allocation.',
    'A tie is reported as tie; the audit never picks a holder on equal priorities.',
    'Logrolling analysis compares declared numbers only; it never manufactures issues or concessions.',
]


def _refuse(code: str) -> None:
    raise ValueError('%s:%s' % (_CODE, code))


def _issues(v) -> list:
    if type(v) is not list:
        _refuse('BAD_TYPE:issues')
    if not v:
        _refuse('EMPTY:issues')
    if len(v) > MAX_ISSUES:
        _refuse('OVERSIZE:issues')
    for issue in v:
        if not isinstance(issue, str) or not issue.strip():
            _refuse('BAD_TYPE:issue')
    if len(set(v)) != len(v):
        _refuse('DUPLICATE:issue')
    return list(v)


def _weight(v) -> Fraction:
    if isinstance(v, bool):
        _refuse('BAD_TYPE:weight')
    if isinstance(v, int):
        if v < 0:
            _refuse('NEGATIVE:weight')
        if v > MAX_INT_WEIGHT:
            _refuse('OVERSIZE:weight')
        return Fraction(v)
    if isinstance(v, str):
        if len(v) > MAX_WEIGHT_STR_LEN:
            _refuse('BAD_TYPE:weight')
        if not _WEIGHT_RE.fullmatch(v):
            _refuse('BAD_TYPE:weight')
        den = v.partition('/')[2]
        if den and int(den) == 0:
            _refuse('BAD_TYPE:weight')
        return Fraction(v)
    _refuse('BAD_TYPE:weight')


def _weights(v, n: int) -> list:
    if type(v) is not list or len(v) != n:
        _refuse('LENGTH_MISMATCH')
    return [_weight(x) for x in v]


def _ratio(w: Fraction) -> str:
    return '%d/%d' % (w.numerator, w.denominator)


def run(request: dict) -> dict:
    """Run one exact integrative-bargaining audit from a JSON-like request."""
    if type(request) is not dict:
        _refuse('BAD_TYPE:request')
    if len(request) > MAX_KEYS:
        _refuse('OVERSIZE:keys')
    for key in request:
        if type(key) is not str or len(key) > MAX_KEY_LEN or any(
                unicodedata.category(ch) in _KEY_BANNED_CATS for ch in key):
            _refuse('BAD_TYPE:key')
    for key in sorted(request):
        if key in _BANNED_KEYS:
            _refuse('DECEPTION_REQUEST:' + key)
    for key in sorted(request):
        if key not in _KEYS:
            _refuse('UNKNOWN_KEY:%r' % (key,))
    issues = _issues(request.get('issues'))
    a_w = _weights(request.get('party_a_weights'), len(issues))
    b_w = _weights(request.get('party_b_weights'), len(issues))
    a_sum = sum(a_w, Fraction(0))
    b_sum = sum(b_w, Fraction(0))
    if a_sum == 0:
        _refuse('ZERO_SUM:party_a')
    if b_sum == 0:
        _refuse('ZERO_SUM:party_b')
    allocation = []
    joint = Fraction(0)
    naive = Fraction(0)
    gain_total = Fraction(0)
    tie_count = 0
    for issue, a, b in zip(issues, a_w, b_w):
        a_n = a / a_sum
        b_n = b / b_sum
        if a_n > b_n:
            holder = 'party_a'
        elif b_n > a_n:
            holder = 'party_b'
        else:
            holder = 'tie'
            tie_count += 1
        comp = abs(a_n - b_n)
        joint += max(a_n, b_n)
        naive += (a_n + b_n) / 2
        gain_total += comp
        allocation.append({'issue': issue, 'a_priority': _ratio(a_n), 'b_priority': _ratio(b_n),
                           'efficient_holder': holder, 'complementarity': _ratio(comp)})
    ranked = sorted(allocation, key=lambda r: (-Fraction(r['complementarity']), r['issue']))
    return {
        'efficient_allocation': allocation,
        'tradeoff_order': [{'issue': r['issue'], 'complementarity': r['complementarity']}
                           for r in ranked],
        'joint_gain_potential': _ratio(gain_total),
        'logrolling_gain_vs_naive_split': _ratio(joint - naive),
        'purely_distributive': gain_total == 0,
        'tie_count': tie_count,
        'limits': list(_LIMITS),
    }
