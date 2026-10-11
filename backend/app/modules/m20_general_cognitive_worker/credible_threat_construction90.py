"""Row 90 bounded credible-consequence gate audit (CREDIB90).

Caller-supplied declarations only: a stated consequence and three
self-attested booleans (lawful, proportionate, authorized), plus optional
declared basis references. Every caller-echoed string is raw-length-capped
and refused on control, separator or format characters (Cc, Zl, Zp, Cf);
strings are echoed verbatim, never stripped, normalized or sanitized. The mechanism evaluates the gate exactly as a
conjunction with per-condition echo and sorted blocked reasons. It never
drafts, improves, or communicates any threat: wording is marked
human-authorship-required. No scores, no confidence. Requests carrying
harm-intent keys are refused with a "CREDIB90:" prefixed ValueError. Delta
vs the landed heuristic in negotiation_behavior_0085_0109.py: the float
credibility score and confidence number are removed, blocked reasons are
sorted deterministically, and a declared-basis list is validated exactly.
"""
from __future__ import annotations

import unicodedata

MAX_CONSEQUENCE = 500
MAX_BASIS = 32

_BANNED_KEYS = ('harm', 'injure', 'coerce', 'punish', 'retaliate', 'violence')
_CONDITIONS = ('lawful', 'proportionate', 'authorized')
_FIELDS = ('consequence', 'lawful', 'proportionate', 'authorized', 'basis')

LIMITS = [
    'Conditions are self-attested booleans; this unit does not verify legality, proportionality or authority against any law or contract.',
    'The gate records a declared conjunction only; it is not a judgement that any consequence is credible, effective or advisable.',
    'No threat text is drafted, improved, routed or delivered; wording remains human-authored and human-reviewed.',
    'Caller-echoed strings are raw-length-capped and refused if they carry control, separator or format characters (Unicode Cc, Zl, Zp, Cf, which includes DEL); the audit refuses rather than sanitizes.',
    'Harm-intent requests are refused; only declared lawful, proportionate, authorized consequences pass.',
    'Not a replacement for the landed credible-threat heuristic; this is a bounded exact delta over declarations.',
]


_BANNED_CHAR_CATEGORIES = frozenset({'Cc', 'Zl', 'Zp', 'Cf'})


def _fail(msg: str):
    raise ValueError(f'CREDIB90:{msg}')


def _text(value, label, blank_code):
    if not isinstance(value, str):
        _fail('BAD_TYPE:' + label)
    if len(value) > MAX_CONSEQUENCE:
        _fail('OVERSIZE:' + label)
    if not value.strip():
        _fail(blank_code)
    for ch in value:
        if unicodedata.category(ch) in _BANNED_CHAR_CATEGORIES:
            _fail('UNCLEAN:' + label)
    return value


def run(request: dict) -> dict:
    """Evaluate the declared credibility gate exactly; refuse harm intent."""
    if not isinstance(request, dict):
        _fail('BAD_TYPE:request')
    for key in request:
        if key not in _FIELDS:
            if key in _BANNED_KEYS:
                _fail('HARM_REQUEST:' + key)
            _fail(f'UNKNOWN_KEY:{key!r}')
    if 'consequence' not in request:
        _fail('MISSING:consequence')
    consequence = _text(request['consequence'], 'consequence', 'EMPTY:consequence')

    conditions = {}
    for field in _CONDITIONS:
        value = request.get(field)
        if not isinstance(value, bool):
            _fail('BAD_TYPE:' + field)
        conditions[field] = value

    basis = request.get('basis', [])
    if not isinstance(basis, list):
        _fail('BAD_TYPE:basis')
    if len(basis) > MAX_BASIS:
        _fail('OVERSIZE:basis')
    seen = set()
    for entry in basis:
        _text(entry, 'basis_entry', 'BAD_TYPE:basis_entry')
        if entry in seen:
            _fail('DUPLICATE:basis')
        seen.add(entry)

    blocked = sorted('not_' + f for f in _CONDITIONS if not conditions[f])
    return {
        'declared_consequence': consequence,
        'conditions': conditions,
        'gate': 'blocked' if blocked else 'pass',
        'blocked_reasons': blocked,
        'basis_count': len(basis),
        'wording': 'human_authored_required',
        'limits': list(LIMITS),
    }
