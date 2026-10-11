"""METROL1533: exact uncertainty budget arithmetic over caller-declared standard uncertainties.

Root-sum-square of sensitivity-weighted standard uncertainties under a stated
uncorrelated-inputs assumption, with a declared coverage factor. All arithmetic
is exact integer arithmetic. The traceability chain is echoed, never verified.
No calibration, accreditation or compliance authority.
"""
import re
import unicodedata
from math import isqrt

MAX_ITEMS = 64
MAX_CHAIN = 16
MAX_TEXT = 128
MAX_UNIT = 16
MAX_K = 10 * 10 ** 6
KINDS = ('type_a', 'type_b')
ASSUMPTION = 'uncorrelated_inputs'
_SIGNED = re.compile(r'(-?)([0-9]{1,12})(?:\.([0-9]{1,6}))?')
_UNSIGNED = re.compile(r'([0-9]{1,12})(?:\.([0-9]{1,6}))?')
_FIELDS = {'id', 'standard_uncertainty', 'sensitivity', 'kind', 'source_ref'}
_STATEMENT = ('The combined standard uncertainty is the root sum of squares of the sensitivity-weighted standard '
              'uncertainties and assumes the declared inputs are uncorrelated; the caller states this and it is not checked.')
_BOUNDARY = ('Arithmetic over declared standard uncertainties only. No coverage probability is claimed for the '
             'coverage factor. The traceability chain is echoed, not verified. Not a calibration, an accreditation, '
             'a compliance finding or a measurement result.')


_HIDDEN_RANGES = ((0x200B, 0x200F), (0x202A, 0x202E), (0x2066, 0x2069), (0xFEFF, 0xFEFF))


def _hidden(char):
    """Unicode control (Cc, includes DEL), line or paragraph separator (Zl, Zp) or bidi and format character."""
    code = ord(char)
    return (unicodedata.category(char) in ('Cc', 'Zl', 'Zp')
            or any(low <= code <= high for low, high in _HIDDEN_RANGES))


def _fail(code):
    raise ValueError('METROL1533:' + code)


def _text(value, field, limit=MAX_TEXT):
    if (type(value) is not str or len(value) > limit or not value.strip()
            or any(_hidden(c) for c in value)):
        _fail('invalid_text:' + field)
    return value


def _micro(value, code, signed):
    pattern = _SIGNED if signed else _UNSIGNED
    match = pattern.fullmatch(value) if type(value) is str else None
    if match is None:
        _fail(code)
    groups = match.groups()
    negative = signed and groups[0] == '-'
    whole, frac = groups[-2], groups[-1] or ''
    number = int(whole) * 10 ** 6 + int(frac.ljust(6, '0'))
    return -number if negative else number


def _fmt(value, places=6):
    scale = 10 ** places
    return '%s%d.%0*d' % ('-' if value < 0 else '', abs(value) // scale, places, abs(value) % scale)


def _bounds(square, exponent):
    """Floor and ceiling of sqrt(square * 10**-exponent) in millionths (exponent >= 12)."""
    divisor = 10 ** (exponent - 12)
    low = isqrt(square // divisor)
    high = low
    while high * high * divisor < square:
        high += 1
    return low, high


def compute_uncertainty_budget(packet):
    """Return an exact uncertainty budget or raise ValueError with a METROL1533: code."""
    if type(packet) is not dict:
        _fail('invalid_packet')
    if set(packet) != {'unit', 'assumption', 'coverage_factor', 'components', 'traceability_chain'}:
        _fail('unknown_fields:packet')
    unit = _text(packet['unit'], 'unit', MAX_UNIT)
    if type(packet['assumption']) is not str or packet['assumption'] != ASSUMPTION:
        _fail('invalid_assumption')
    k = _micro(packet['coverage_factor'], 'invalid_coverage_factor', False)
    if not 0 < k <= MAX_K:
        _fail('invalid_coverage_factor')
    chain = packet['traceability_chain']
    if type(chain) is not list or len(chain) > MAX_CHAIN:
        _fail('invalid_count:traceability_chain')
    chain = [_text(item, 'traceability_chain') for item in chain]
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
        if type(row['kind']) is not str or row['kind'] not in KINDS:
            _fail('invalid_kind')
        u = _micro(row['standard_uncertainty'], 'invalid_number:standard_uncertainty', False)
        c = _micro(row['sensitivity'], 'invalid_number:sensitivity', True)
        ref = _text(row['source_ref'], 'source_ref')
        parsed.append((key, row['kind'], u, c, abs(c) * u, ref))
    parsed.sort(key=lambda r: r[0])
    square = sum(r[4] ** 2 for r in parsed)          # units of 1e-24
    low, high = _bounds(square, 24)
    elow, ehigh = _bounds(k * k * square, 36)
    return {
        'unit': unit,
        'coverage_factor': _fmt(k),
        'coverage_factor_as_given': packet['coverage_factor'],
        'combined_standard_uncertainty': {'squared': _fmt(square, 24),
                                          'bounds': [_fmt(low), _fmt(high)]},
        'expanded_uncertainty': {'bounds': [_fmt(elow), _fmt(ehigh)]},
        'contributions': [{'id': r[0], 'kind': r[1], 'source_ref': r[5], 'standard_uncertainty': _fmt(r[2]),
                           'sensitivity': _fmt(r[3]), 'contribution': _fmt(r[4], 12)} for r in parsed],
        'assumption': ASSUMPTION,
        'statement': _STATEMENT,
        'traceability_chain': chain,
        'traceability_status': 'echoed_not_verified',
        'traceability_verified': False,
        'calibration_authority': False,
        'requires_metrologist_review': True,
        'scope': 'declared_standard_uncertainties_arithmetic_only',
        'boundary': _BOUNDARY,
    }
