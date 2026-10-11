"""TAGUCH1540: orthogonal-array and signal-to-noise bookkeeping over caller-supplied runs.

Decimal-string responses, exact rational arithmetic, logarithms evaluated with the
decimal module (no floats). No robustness certification, optimization or design claim.
"""
import re
import unicodedata
from collections import Counter
import decimal
from decimal import Decimal, ROUND_HALF_EVEN, Context
from fractions import Fraction
from functools import reduce
from itertools import combinations

MAX_FACTORS = 8
MAX_RUNS = 64
MAX_RESPONSES = 16
MAX_LEVEL = 9
MAX_TEXT = 128
GOALS = ('larger', 'smaller', 'nominal')
_NUMBER = re.compile(r'(-?)(0|[1-9][0-9]*)(?:\.([0-9]+))?')   # ASCII digits only, no leading zeros, fullmatch
_FIELDS = {'id', 'levels', 'responses'}
# Emin and Emax are the peer-stated numbers (inherited from the 1536 reading, relayed by Main).
_CTX = Context(prec=60, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
               traps=[decimal.Overflow, decimal.Underflow, decimal.InvalidOperation, decimal.DivisionByZero])
MAX_NUMBER_CHARS = 80
MAX_SIGNIFICANT = 64
MAX_FRACTION = 64
MAX_ABS = 10 ** 12          # inclusive bound on the absolute value of a response
_QUANT = Decimal('0.000001')
_ROUNDING = ('signal_to_noise_db is evaluated to 60 significant digits with the decimal module and then rounded '
             'half-even to six decimals; level means are exact sums of those rounded values, rounded half-even to six decimals.')
_BOUNDARY = ('Bookkeeping over declared runs: signal-to-noise values, factor-level means of those values and a check '
             'that every two-factor level pair of the declared array occurs equally often. This is the '
             'declared array, not matched to any catalogue or standard array. No comparison of settings or design '
             'claim and no test result. Responses and levels are declared by the caller and not verified.')
_ARRAY_NOTE = ('Pairwise balance is checked on the declared array, not matched to any catalogue or standard array; '
               'no standard array name is claimed.')


_HIDDEN_RANGES = ((0x200B, 0x200F), (0x202A, 0x202E), (0x2066, 0x2069), (0xFEFF, 0xFEFF))


def _hidden(char):
    """Unicode control (Cc, includes DEL), line or paragraph separator (Zl, Zp) or bidi and format character."""
    code = ord(char)
    return (unicodedata.category(char) in ('Cc', 'Zl', 'Zp')
            or any(low <= code <= high for low, high in _HIDDEN_RANGES))


def _fail(code):
    raise ValueError('TAGUCH1540:' + code)


def _text(value, field):
    if type(value) is not str or len(value) > MAX_TEXT:
        _fail('invalid_text:' + field)
    if not value.strip() or any(_hidden(c) for c in value):
        _fail('invalid_text:' + field)
    return value


def _value(text):
    if type(text) is not str:
        _fail('invalid_number')
    if len(text) > MAX_NUMBER_CHARS:          # raw length first, before the regex or any copy
        _fail('number_too_long')
    match = _NUMBER.fullmatch(text)
    if match is None:
        _fail('invalid_number')
    whole, frac = match.group(2), match.group(3) or ''
    if len((whole + frac).lstrip('0')) > MAX_SIGNIFICANT or len(frac) > MAX_FRACTION:
        _fail('number_precision')
    value = Fraction(text)
    if abs(value) > MAX_ABS:
        _fail('number_range')
    return value


def _db(multiplier, ratio):
    """multiplier * log10(ratio) to six decimals, half-even, with no negative zero."""
    try:
        value = _CTX.log10(_CTX.divide(Decimal(ratio.numerator), Decimal(ratio.denominator)))
        value = _CTX.multiply(Decimal(multiplier), value).quantize(_QUANT, rounding=ROUND_HALF_EVEN, context=_CTX)
    except decimal.DecimalException:
        _fail('arithmetic')
    return value if value != 0 else Decimal('0.000000')


def _mean(values):
    """Mean of signal-to-noise values to six decimals; any decimal signal is the arithmetic refusal."""
    try:
        return _CTX.divide(reduce(_CTX.add, values, Decimal(0)), Decimal(len(values))).quantize(
            _QUANT, rounding=ROUND_HALF_EVEN, context=_CTX)
    except decimal.DecimalException:
        _fail('arithmetic')


def _sn(goal, values):
    n = len(values)
    if goal == 'larger':
        if any(v <= 0 for v in values):
            _fail('undefined_sn')
        return _db(-10, sum(1 / (v * v) for v in values) / n)
    if goal == 'smaller':
        mean_square = sum(v * v for v in values) / n
        if mean_square == 0:
            _fail('undefined_sn')
        return _db(-10, mean_square)
    mean = sum(values) / n
    variance = sum(v * v for v in values) / n - mean * mean
    if n < 2 or mean == 0 or variance <= 0:
        _fail('undefined_sn')
    return _db(10, mean * mean / variance)


def analyze_taguchi_runs(packet):
    """Return exact bookkeeping or raise ValueError with a TAGUCH1540: code."""
    if type(packet) is not dict:
        _fail('invalid_packet')
    if set(packet) != {'goal', 'factors', 'runs'}:
        _fail('unknown_fields:packet')
    goal = packet['goal']
    if type(goal) is not str or goal not in GOALS:
        _fail('invalid_goal')
    factors = packet['factors']
    if type(factors) is not list or not 1 <= len(factors) <= MAX_FACTORS:
        _fail('invalid_count:factors')
    rows = packet['runs']
    if type(rows) is not list or not 1 <= len(rows) <= MAX_RUNS:
        _fail('invalid_count:runs')
    for row in rows:      # every count cap is checked before any text, level or number is parsed
        if type(row) is dict and 'responses' in row:
            resp = row['responses']
            if type(resp) is not list or not 1 <= len(resp) <= MAX_RESPONSES:
                _fail('invalid_count:responses')
    factors = [_text(f, 'factor') for f in factors]
    if len(set(factors)) != len(factors):
        _fail('duplicate_factor')
    parsed, seen = [], set()
    for row in rows:
        if type(row) is not dict:
            _fail('invalid_record:runs')
        if set(row) != _FIELDS:
            _fail('invalid_fields:runs')
        key = _text(row['id'], 'id')
        if key in seen:
            _fail('duplicate_id')
        seen.add(key)
        levels = row['levels']
        if (type(levels) is not list or len(levels) != len(factors)
                or any(type(x) is not int or not 1 <= x <= MAX_LEVEL for x in levels)):
            _fail('invalid_levels')
        values = [_value(x) for x in row['responses']]
        parsed.append((key, list(levels), len(values), _sn(goal, values)))
    parsed.sort(key=lambda r: r[0])
    summaries, balanced_all = [], True
    for index, name in enumerate(factors):
        counts = Counter(r[1][index] for r in parsed)
        balanced = len(set(counts.values())) == 1
        balanced_all = balanced_all and balanced
        sums = {}
        for r in parsed:
            sums.setdefault(r[1][index], []).append(r[3])
        means = {lv: _mean(v) for lv, v in sums.items()}
        summaries.append({'factor': name, 'observed_levels': sorted(counts), 'balanced': balanced,
                          'level_mean_sn': {str(lv): format(means[lv], 'f') for lv in sorted(means)}})
    pairs_ok = True
    for a, b in combinations(range(len(factors)), 2):
        counts = Counter((r[1][a], r[1][b]) for r in parsed)
        full = len({r[1][a] for r in parsed}) * len({r[1][b] for r in parsed})
        if len(counts) != full or len(set(counts.values())) != 1:
            pairs_ok = False
    if not (balanced_all and pairs_ok):
        _fail('not_orthogonal')
    return {
        'goal': goal,
        'run_count': len(parsed),
        'runs': [{'id': r[0], 'levels': list(r[1]), 'response_count': r[2], 'signal_to_noise_db': format(r[3], 'f')}
                 for r in parsed],
        'factor_summaries': summaries,
        'array_status': 'pairwise_balanced',
        'array_note': _ARRAY_NOTE,
        'robustness_certified': False,
        'requires_engineer_review': True,
        'scope': 'declared_runs_array_and_sn_bookkeeping_only',
        'rounding': _ROUNDING,
        'boundary': _BOUNDARY,
    }
