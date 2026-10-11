"""Bounded exact anchoring-reference audit (row 95).

Not shipped product code. Given an objective value and an evidence range
(exact integers or "p/q" rational strings), this module computes, with
exact Fraction arithmetic, the evidence-clamped reference point, the range
midpoint, the sorted expected settlement zone, and an explicitly labelled
heuristic adjustment band of (range / 4) - a stated heuristic, not a
measurement. All numbers are exact "p/q" strings; there are no floats, no
confidence scores and no deployment verdicts. An objective outside the
evidence range yields a stated rejection rather than a clamped anchor,
because an unsupported reference point cannot anchor honestly. Inverted
ranges, missing or non-rational values, unknown keys, and any request to
deceive, mislead, bluff, fabricate, inflate or misrepresent are refused
with a stated code. It is an audit aid for a human reviewer checking
whether a proposed reference point is supported by the stated evidence
range; it does not advise on negotiation strategy and it makes no claim
about where a negotiation will settle.
"""
from __future__ import annotations

import re
from fractions import Fraction

_CODE = 'ANCHOR95'
_KEYS = frozenset({'objective_value', 'evidence_low', 'evidence_high'})
_BANNED_KEYS = ('deceive', 'mislead', 'bluff', 'fabricate', 'inflate', 'misrepresent')
MAX_VALUE_STR_LEN = 64
MAX_INT_ABS = 10**18 - 1
MAX_KEY_ECHO = 128
_VALUE_RE = re.compile(r'^-?[0-9]{1,18}(/[0-9]{1,18})?$')
_LIMITS = [
    'This module is a bounded exact anchoring-reference audit aid, not shipped product code.',
    'The adjustment band is (range / 4), a stated heuristic, not a measurement.',
    'Anchor pull varies widely by counterparty; no settlement outcome is predicted.',
    'A reference point outside the stated evidence range is rejected, not clamped.',
]


def _refuse(code: str) -> None:
    raise ValueError('%s:%s' % (_CODE, code))


def _value(v, name: str) -> Fraction:
    if v is None:
        _refuse('MISSING:' + name)
    if isinstance(v, bool):
        _refuse('BAD_TYPE:value')
    if isinstance(v, int):
        if abs(v) > MAX_INT_ABS:
            _refuse('BAD_TYPE:value')
        return Fraction(v)
    if isinstance(v, str):
        if len(v) > MAX_VALUE_STR_LEN:
            _refuse('BAD_TYPE:value')
        if not _VALUE_RE.fullmatch(v):
            _refuse('BAD_TYPE:value')
        den = v.partition('/')[2]
        if den and int(den) == 0:
            _refuse('BAD_TYPE:value')
        return Fraction(v)
    _refuse('BAD_TYPE:value')


def _ratio(w: Fraction) -> str:
    return '%d/%d' % (w.numerator, w.denominator)


def run(request: dict) -> dict:
    """Run one exact anchoring-reference audit from a JSON-like request."""
    if not isinstance(request, dict):
        _refuse('BAD_TYPE:request')
    for key in request:
        if type(key) is not str:
            _refuse('BAD_TYPE:key')
    for key in sorted(request):
        if key in _BANNED_KEYS:
            _refuse('DECEPTIVE_ANCHOR:' + key)
        if key not in _KEYS:
            _refuse('UNKNOWN_KEY:%r' % (key[:MAX_KEY_ECHO],))
    objective = _value(request.get('objective_value'), 'objective_value')
    low = _value(request.get('evidence_low'), 'evidence_low')
    high = _value(request.get('evidence_high'), 'evidence_high')
    if low > high:
        _refuse('INVERTED_RANGE')
    in_range = low <= objective <= high
    midpoint = (low + high) / 2
    anchor = objective if in_range else None
    out = {
        'evidence_based_anchor': _ratio(anchor) if anchor is not None else None,
        'anchor_in_evidence_range': in_range,
        'range': [_ratio(low), _ratio(high)],
        'range_midpoint': _ratio(midpoint),
        'heuristic_adjustment_band': _ratio((high - low) / 4),
        'expected_settlement_zone': sorted([_ratio(midpoint), _ratio(anchor)],
                                           key=Fraction) if anchor is not None else None,
        'rationale_required': True,
        'limits': list(_LIMITS),
    }
    if not in_range:
        out['rejection'] = 'Objective outside the evidence range cannot anchor honestly.'
    return out
