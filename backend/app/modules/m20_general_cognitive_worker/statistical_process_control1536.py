"""Row 1536 Statistical Process Control: exact baseline individuals chart.

The ledger row has an empty description, so the requirement title is the
whole spec. Delta against engineering_1510_1559.py:164 (_spc): that float
routine takes pstdev over every point including the ones it then tests; this
unit uses exact decimal arithmetic and the individuals/moving-range estimate
sigma = MRbar / 1.128, and also flags 8-in-a-row on one side of the centre
line. Baseline statistics over a supplied series only. It makes no claim
about process control state and advises no intervention.
"""
import re
import unicodedata
from decimal import (Context, Decimal, DecimalException, DivisionByZero, InvalidOperation,
                     Overflow, ROUND_HALF_EVEN, Underflow, localcontext)

PREFIX = 'SPC1536'
MIN_POINTS = 2
MAX_POINTS = 500
MAX_ABS = Decimal(10) ** 12
D2 = Decimal('1.128')
SIGMA_LIMIT = 3
RUN_LENGTH = 8
PRECISION = 64
PLACES = Decimal('0.000000001')
MAX_SERIES_ID = 128
MAX_NUMBER_CHARS = 80
MAX_SIGNIFICANT = 64
MAX_FRACTION = 64
NUMBER = re.compile(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?', re.ASCII)

BOUNDARY = ('Baseline individuals-chart statistics over the supplied series only: '
            'sigma is MRbar/1.128 and limits are the centre line plus or minus three '
            'sigma. Flags mark points or runs relative to those baseline numbers. No '
            'claim is made about process control state, and no process intervention '
            'is advised.')


def _fail(code, message):
    raise ValueError(f'{PREFIX}: {code + ": " if code else ""}{message}')


def _context():
    return Context(prec=PRECISION, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
                   capitals=1, clamp=0, flags=[],
                   traps=[InvalidOperation, DivisionByZero, Overflow, Underflow])


def _out(value):
    return format(value.quantize(PLACES, rounding=ROUND_HALF_EVEN).normalize(), 'f')


def _value(raw):
    """Exact input: every check runs on the text before any Decimal operation."""
    shape = 'values require ASCII decimal strings such as -12.5'
    if type(raw) is not str:
        _fail('invalid_number', shape)
    if len(raw) > MAX_NUMBER_CHARS:
        _fail('number_too_long', f'values require at most {MAX_NUMBER_CHARS} characters')
    if not NUMBER.fullmatch(raw):
        _fail('invalid_number', shape)
    whole, _, fraction = raw.lstrip('-').partition('.')
    significant = len((whole + fraction).lstrip('0'))
    if significant > MAX_SIGNIFICANT or len(fraction) > MAX_FRACTION:
        _fail('number_precision', f'values require at most {MAX_SIGNIFICANT} significant digits '
                                  f'and {MAX_FRACTION} fraction digits')
    parsed = Decimal(raw)
    if parsed.copy_abs() > MAX_ABS:
        _fail('number_range', 'values require |value| <= 1000000000000')
    return parsed

_BAD_FORMAT = frozenset(list(range(0x200B, 0x2010)) + list(range(0x202A, 0x202F))
                        + list(range(0x2066, 0x206A)) + [0xFEFF])


def _unsafe_char(c):
    return unicodedata.category(c) in ('Cc', 'Zl', 'Zp') or ord(c) == 127 or ord(c) in _BAD_FORMAT


def _series_id(value):
    if type(value) is not str:
        _fail('invalid_series_id', 'series_id requires non-blank text')
    if len(value) > MAX_SERIES_ID:
        _fail('invalid_series_id', f'series_id exceeds {MAX_SERIES_ID} characters')
    if not value.strip():
        _fail('invalid_series_id', 'series_id requires non-blank text')
    if any(_unsafe_char(c) for c in value):
        _fail('invalid_series_id', 'series_id contains disallowed characters')
    return value


def chart_baseline(payload):
    if type(payload) is not dict:
        _fail(None, 'payload requires an object')
    if any(k not in ('series_id', 'values') for k in payload):
        _fail(None, 'unknown key in payload')
    series_id = _series_id(payload.get('series_id'))
    raw = payload.get('values')
    if type(raw) is not list or not MIN_POINTS <= len(raw) <= MAX_POINTS:
        _fail(None, f'values requires a list of {MIN_POINTS}..{MAX_POINTS} points')
    values = [_value(x) for x in raw]
    try:
        with localcontext(_context()):
            result = _compute(series_id, values)
    except DecimalException:
        _fail('arithmetic', 'computation could not complete')
    result.update({'sigma_estimator': 'MRbar/1.128', 'baseline_only': True,
                   'control_state_claimed': False, 'process_intervention_advised': False,
                   'boundary': BOUNDARY})
    return result


def _compute(series_id, values):
    n = len(values)
    mean = sum(values, Decimal(0)) / n
    ranges = [abs(values[i] - values[i - 1]) for i in range(1, n)]
    mr_bar = sum(ranges, Decimal(0)) / len(ranges)
    sigma = mr_bar / D2
    ucl = mean + SIGMA_LIMIT * sigma
    lcl = mean - SIGMA_LIMIT * sigma
    flags = []
    for i, x in enumerate(values):
        if x < lcl:
            flags.append({'index': i, 'rule': 'beyond_lcl'})
        if x > ucl:
            flags.append({'index': i, 'rule': 'beyond_ucl'})
        if i >= RUN_LENGTH - 1:
            window = values[i - RUN_LENGTH + 1:i + 1]
            if all(y > mean for y in window):
                flags.append({'index': i, 'rule': 'run8_above'})
            if all(y < mean for y in window):
                flags.append({'index': i, 'rule': 'run8_below'})
    return {
        'series_id': series_id, 'n': n, 'center_line': _out(mean),
        'moving_range_mean': _out(mr_bar), 'sigma_hat': _out(sigma),
        'ucl': _out(ucl), 'lcl': _out(lcl), 'flags': flags}
