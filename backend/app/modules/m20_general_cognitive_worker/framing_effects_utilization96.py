"""Bounded exact framing-equivalence audit (row 96).

Not shipped product code. Given a gain frame, a loss frame and a facts
payload, this module checks - with exact Fraction arithmetic on the numerals
it can extract - whether the two frames state the same numbers and whether
those numbers are consistent with the stated fact delta. Equivalence is
exact list equality, not an epsilon comparison. The audit requires balanced
presentation: it reports both frames together, always selects 'both', and
issues no confidence score and no deployment verdict. Missing, blank or
mistyped frames, a missing, empty or mistyped facts payload, a float or
non-rational fact delta, unknown keys, and any request to exploit,
manipulate, deceive, mislead, coerce or hide are refused with a stated
code. It is an audit aid for a human reviewer checking that equivalent
outcomes are presented with both frames visible; it does not advise which
frame to use, does not measure wording emphasis, and makes no claim that
framing changes any decision.
"""
from __future__ import annotations

import math
import re
import unicodedata
from fractions import Fraction

_CODE = 'FRAMIN96'
_KEYS = frozenset({'gain_frame', 'loss_frame', 'facts'})
_BANNED_KEYS = ('exploit', 'manipulate', 'deceive', 'mislead', 'coerce', 'hide')
MAX_FRAME_LEN = 2000
MAX_NUMERALS = 64
MAX_NUMERAL_DIGITS = 18
MAX_FACTS_KEYS = 64
MAX_FACTS_KEY_LEN = 128
MAX_FACTS_VALUE_LEN = 128
MAX_KEY_ECHO = 128
MAX_DELTA_STR_LEN = 64
MAX_DELTA_INT_ABS = 10**18 - 1
_BANNED_CATS = ('Cc', 'Cf', 'Zl', 'Zp')
_TOKEN = re.compile(
    r'(?:[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?(?![0-9,])|[0-9]+(?:\.[0-9]+)?)')
_DELTA_RE = re.compile(r'-?[0-9]{1,18}(\.[0-9]{1,18})?', re.ASCII)
_DELTA_SHAPE_RE = re.compile(r'-?[0-9]+(\.[0-9]+)?', re.ASCII)
_SCALARS = (str, int, float, bool, type(None))
_LIMITS = [
    'This module is a bounded exact framing-equivalence audit aid, not shipped product code.',
    'Equivalence is checked on extracted numerals only; wording emphasis is not measured.',
    'One-sided framing and exploitation of loss aversion are refused.',
]


def _refuse(code: str) -> None:
    raise ValueError('%s:%s' % (_CODE, code))


def _frame(v, name: str) -> str:
    if v is None:
        _refuse('MISSING:' + name)
    if not isinstance(v, str):
        _refuse('BAD_TYPE:frame')
    if len(v) > MAX_FRAME_LEN:
        _refuse('OVERSIZE:' + name)
    text = v.strip()
    if not text:
        _refuse('EMPTY:frame')
    return text


def _numbers(text: str, name: str) -> list:
    out = []
    for match in _TOKEN.finditer(text):
        tok = match.group(0)
        start = match.start()
        negative = False
        if start > 0 and text[start - 1] == '-':
            negative = start - 1 == 0 or text[start - 2].isspace() or text[start - 2] == '('
        digits = tok.replace(',', '')
        int_part, _, frac_part = digits.partition('.')
        if len(int_part) > MAX_NUMERAL_DIGITS or len(frac_part) > MAX_NUMERAL_DIGITS:
            _refuse('OVERSIZE:' + name)
        value = Fraction(digits)
        out.append(-value if negative else value)
        if len(out) > MAX_NUMERALS:
            _refuse('OVERSIZE:' + name)
    return out


def _delta(v) -> Fraction:
    if isinstance(v, bool):
        _refuse('BAD_TYPE:delta')
    if isinstance(v, int):
        if abs(v) > MAX_DELTA_INT_ABS:
            _refuse('OVERSIZE:delta')
        return Fraction(v)
    if isinstance(v, str):
        if len(v) > MAX_DELTA_STR_LEN:
            _refuse('OVERSIZE:delta')
        if not _DELTA_RE.fullmatch(v):
            if _DELTA_SHAPE_RE.fullmatch(v):
                _refuse('OVERSIZE:delta')
            _refuse('BAD_TYPE:delta')
        return Fraction(v)
    _refuse('BAD_TYPE:delta')


def _ratio(w: Fraction) -> str:
    return '%d/%d' % (w.numerator, w.denominator)


def run(request: dict) -> dict:
    """Run one exact framing-equivalence audit from a JSON-like request."""
    if type(request) is not dict:
        _refuse('BAD_TYPE:request')
    for key in request:
        if type(key) is str and len(key) > MAX_KEY_ECHO:
            _refuse('OVERSIZE:request')
        if type(key) is not str or any(
                unicodedata.category(ch) in _BANNED_CATS for ch in key):
            _refuse('BAD_TYPE:key')
    for key in sorted(request):
        if key in _BANNED_KEYS:
            _refuse('MANIPULATION_REQUEST:' + key)
        if key not in _KEYS:
            _refuse('UNKNOWN_KEY:%r' % (key[:MAX_KEY_ECHO],))
    gain = _frame(request.get('gain_frame'), 'gain_frame')
    loss = _frame(request.get('loss_frame'), 'loss_frame')
    facts = request.get('facts')
    if facts is None:
        _refuse('MISSING:facts')
    if type(facts) is not dict:
        _refuse('BAD_TYPE:facts')
    if not facts:
        _refuse('EMPTY:facts')
    if len(facts) > MAX_FACTS_KEYS:
        _refuse('OVERSIZE:facts')
    for fkey, fval in facts.items():
        if type(fkey) is str and len(fkey) > MAX_FACTS_KEY_LEN:
            _refuse('OVERSIZE:facts')
        if type(fkey) is not str or any(
                unicodedata.category(ch) in _BANNED_CATS for ch in fkey):
            _refuse('BAD_TYPE:facts_key')
        if type(fval) not in _SCALARS:
            _refuse('BAD_TYPE:facts_value')
        if type(fval) is float and not math.isfinite(fval):
            _refuse('BAD_TYPE:facts_value')
        if type(fval) is str and len(fval) > MAX_FACTS_VALUE_LEN:
            _refuse('OVERSIZE:facts')
        if type(fval) is str and any(
                unicodedata.category(ch) in _BANNED_CATS for ch in fval):
            _refuse('BAD_TYPE:facts_value')
    gain_nums = _numbers(gain, 'gain_frame')
    loss_nums = _numbers(loss, 'loss_frame')
    numeric_equivalence = bool(gain_nums) and bool(loss_nums) and \
        sorted(gain_nums) == sorted(loss_nums)
    if 'delta' not in facts or not gain_nums or not loss_nums:
        consistent = None
        facts_checked = False
    else:
        delta = abs(_delta(facts['delta']))
        consistent = any(n == delta for n in gain_nums + loss_nums)
        facts_checked = True
    return {
        'gain_frame': gain,
        'loss_frame': loss,
        'facts': facts,
        'extracted_frame_numbers': {'gain': [_ratio(n) for n in gain_nums],
                                    'loss': [_ratio(n) for n in loss_nums]},
        'numeric_equivalence': numeric_equivalence,
        'consistent_with_facts': consistent,
        'facts_checked': facts_checked,
        'balanced_presentation_required': True,
        'selected_frame': 'both',
        'limits': list(_LIMITS),
    }
