"""TOLER1531: exact 1D tolerance stack arithmetic over caller-declared values.

Signed components with bilateral tolerances; worst-case sums and an optional
RSS under a stated independence assumption. All arithmetic is exact in
millionths. No geometry, GD&T, capability, inspection or release claim.
"""
import re
import unicodedata
from math import isqrt

MAX_ITEMS = 64
MAX_TEXT = 128
MAX_NUMBER_CHARS = 20
UNITS = frozenset(('mm', 'cm', 'm', 'inch'))
ASSUMPTIONS = ('worst_case_only', 'rss_independent')
_SIGNED = re.compile(r'(-?)([0-9]{1,12})(?:\.([0-9]{1,6}))?')
_UNSIGNED = re.compile(r'([0-9]{1,12})(?:\.([0-9]{1,6}))?')
_STATEMENT = ('RSS assumes independent components whose declared tolerances are treated as equal-confidence '
              'bounds; the caller states this assumption and it is not checked.')
_FIELDS = {'id', 'sign', 'nominal', 'plus', 'minus', 'source_ref'}


_HIDDEN_RANGES = ((0x200B, 0x200F), (0x202A, 0x202E), (0x2066, 0x2069), (0xFEFF, 0xFEFF))


def _hidden(char):
    """Unicode control (Cc, includes DEL), line or paragraph separator (Zl, Zp) or bidi and format character."""
    code = ord(char)
    return (unicodedata.category(char) in ('Cc', 'Zl', 'Zp')
            or any(low <= code <= high for low, high in _HIDDEN_RANGES))


def _fail(code):
    raise ValueError('TOLER1531:' + code)


def _text(value, field):
    if type(value) is not str or len(value) > MAX_TEXT:
        _fail('invalid_text:' + field)
    if not value.strip() or any(_hidden(c) for c in value):
        _fail('invalid_text:' + field)
    return value


def _micro(value, field, signed):
    if type(value) is not str or len(value) > MAX_NUMBER_CHARS:
        _fail('invalid_number:' + field)
    pattern = _SIGNED if signed else _UNSIGNED
    match = pattern.fullmatch(value)
    if match is None:
        _fail('invalid_number:' + field)
    groups = match.groups()
    negative = signed and groups[0] == '-'
    whole, frac = groups[-2], groups[-1] or ''
    number = int(whole) * 10 ** 6 + int(frac.ljust(6, '0'))
    return -number if negative else number


def _fmt(value, places=6):
    scale = 10 ** places
    return '%s%d.%0*d' % ('-' if value < 0 else '', abs(value) // scale, places, abs(value) % scale)


def _bounds(squares):
    """Floor and ceiling square root in millionths of a sum of squares in 1e-12 units."""
    root = isqrt(squares)
    return root, root if root * root == squares else root + 1


def analyze_tolerance_stack(packet):
    """Return exact stack results or raise ValueError with a TOLER1531: code."""
    if type(packet) is not dict:
        _fail('invalid_packet')
    if set(packet) not in ({'unit', 'components', 'assumption'}, {'unit', 'components', 'assumption', 'limits'}):
        _fail('unknown_fields:packet')
    if type(packet['unit']) is not str or packet['unit'] not in UNITS:
        _fail('unsupported_unit')
    if type(packet['assumption']) is not str or packet['assumption'] not in ASSUMPTIONS:
        _fail('invalid_assumption')
    rows = packet['components']
    if type(rows) is not list or not 1 <= len(rows) <= MAX_ITEMS:
        _fail('invalid_count:components')
    parsed, seen = [], set()
    for row in rows:
        if type(row) is not dict:
            _fail('invalid_record:components')
        if set(row) != _FIELDS:
            _fail('invalid_fields:components')
        key = _text(row['id'], 'id')
        if key in seen:
            _fail('duplicate_id')
        seen.add(key)
        if type(row['sign']) is not int or row['sign'] not in (1, -1):
            _fail('invalid_sign')
        nominal = _micro(row['nominal'], 'nominal', True)
        plus = _micro(row['plus'], 'plus', False)
        minus = _micro(row['minus'], 'minus', False)
        ref = _text(row['source_ref'], 'source_ref')
        sign = row['sign']
        parsed.append((key, sign * nominal, plus if sign > 0 else minus, minus if sign > 0 else plus, ref))
    limits = None
    if 'limits' in packet:
        raw = packet['limits']
        if type(raw) is not dict or set(raw) != {'min', 'max'}:
            _fail('invalid_limits')
        limits = (_micro(raw['min'], 'limits', True), _micro(raw['max'], 'limits', True))
        if limits[0] > limits[1]:
            _fail('limits_order')
    parsed.sort(key=lambda row: row[0])
    nominal = sum(row[1] for row in parsed)
    upper = sum(row[2] for row in parsed)
    lower = sum(row[3] for row in parsed)
    result = {
        'unit': packet['unit'],
        'nominal_stack': _fmt(nominal),
        'worst_case': {'upper_deviation': _fmt(upper), 'lower_deviation': _fmt(lower),
                       'max': _fmt(nominal + upper), 'min': _fmt(nominal - lower)},
        'rss': None,
        'limits_check': None,
        'contributions': [{'id': r[0], 'signed_nominal': _fmt(r[1]), 'upper': _fmt(r[2]), 'lower': _fmt(r[3]),
                           'source_ref': r[4]} for r in parsed],
        'scope': 'linear_1d_declared_values_only',
        'physically_verified': False,
        'requires_engineer_review': True,
        'boundary': ('Arithmetic over declared one-dimensional values only. Not geometry, GD&T, process capability, '
                     'inspection, certification, a simulation or a physical test, and not release authority.'),
    }
    rss_conservative = None
    if packet['assumption'] == 'rss_independent':
        up_sq = sum(r[2] ** 2 for r in parsed)
        low_sq = sum(r[3] ** 2 for r in parsed)
        up_lo, up_hi = _bounds(up_sq)
        low_lo, low_hi = _bounds(low_sq)
        result['rss'] = {
            'assumption': 'rss_independent', 'distribution_assumption': 'independent components, RSS leg only', 'statement': _STATEMENT,
            'upper_deviation_squared': _fmt(up_sq, 12), 'lower_deviation_squared': _fmt(low_sq, 12),
            'upper_deviation_bounds': [_fmt(up_lo), _fmt(up_hi)],
            'lower_deviation_bounds': [_fmt(low_lo), _fmt(low_hi)],
            'max_bounds': [_fmt(nominal + up_lo), _fmt(nominal + up_hi)],
            'min_bounds': [_fmt(nominal - low_hi), _fmt(nominal - low_lo)],
        }
        rss_conservative = (nominal - low_hi, nominal + up_hi)
    if limits is not None:
        result['limits_check'] = {
            'min': _fmt(limits[0]), 'max': _fmt(limits[1]),
            'worst_case_within_limits': nominal - lower >= limits[0] and nominal + upper <= limits[1],
            'rss_within_limits': None if rss_conservative is None else (
                rss_conservative[0] >= limits[0] and rss_conservative[1] <= limits[1]),
        }
    return result
