"""Bounded exact loss-aversion frame audit (row 97).

Not shipped product code. Given a gain frame, a loss frame and a facts
payload, this module runs the exact framing-equivalence and fact-consistency
checks of row 96 and additionally reports the loss-aversion context exactly:
the stated reference lambda 9/4 (losses loom roughly twice as large as
gains, a published reference value from laboratory gamble studies, not a
measurement of this request) and the exact ratio of the largest gain
numeral to the largest loss numeral, reported only when both frames carry a
numeral and a positive loss amount is present, else None. All figures are
exact "p/q" strings; there are no floats, no rounded ratios, no confidence
scores and no deployment verdicts. The audit requires balanced presentation
- both frames must stay visible so the reader, not the bias, decides - and
it refuses missing, blank or mistyped inputs, a float fact delta, a
non-rational fact delta string, unknown keys, and any request to exploit
loss aversion, amplify fear, manipulate, deceive, pressure or coerce, each
with a stated code. It is an audit aid for a human reviewer; it does not
advise on using loss aversion and makes no claim that framing changes any
decision.
"""
from __future__ import annotations

import math
import re
import unicodedata
from fractions import Fraction

_CODE = 'LOSSAV97'
_KEYS = frozenset({'gain_frame', 'loss_frame', 'facts'})
_BANNED_KEYS = ('exploit', 'amplify_fear', 'manipulate', 'deceive', 'pressure', 'coerce')
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
_REFERENCE_LAMBDA = Fraction(9, 4)
_LIMITS = [
    'This module is a bounded exact loss-aversion frame audit aid, not shipped product code.',
    'The reference lambda 9/4 is a published laboratory-gamble reference value, not a measurement of this request.',
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
    """Run one exact loss-aversion frame audit from a JSON-like request."""
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
            _refuse('EXPLOITATION_REQUEST:' + key)
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
    asymmetry = None
    if gain_nums and loss_nums and max(loss_nums) > 0:
        asymmetry = max(gain_nums) / max(loss_nums)
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
        'reference_loss_aversion_lambda': _ratio(_REFERENCE_LAMBDA),
        'frame_asymmetry_ratio': _ratio(asymmetry) if asymmetry is not None else None,
        'loss_aversion_note': 'Losses loom roughly twice as large as gains (reference lambda '
                              '9/4); both frames must stay visible so the reader, not the '
                              'bias, decides.',
        'limits': list(_LIMITS),
    }
