"""QUALC1534: exact pass/fail bookkeeping of declared measurements against declared spec limits.

Decimal-string inputs, exact integer comparison, limits inclusive. No disposition
authority: nothing is accepted, rejected or released here.
"""
import re
import unicodedata

MAX_ITEMS = 256
MAX_TEXT = 128
MAX_UNIT = 16
_SIGNED = re.compile(r'(-?)([0-9]{1,12})(?:\.([0-9]{1,6}))?')
_FIELDS = {'id', 'value'}
_BOUNDARY = ('Bookkeeping of declared measurements against declared specification limits only. The unit is a label: no conversion is applied and mixed units are not detected. Any disposition of '
             'nonconforming items requires human approval and is not made here. Measurement values and limits are '
             'not verified, and no capability, process or release finding is made.')


_HIDDEN_RANGES = ((0x200B, 0x200F), (0x202A, 0x202E), (0x2066, 0x2069), (0xFEFF, 0xFEFF))


def _hidden(char):
    """Unicode control (Cc, includes DEL), line or paragraph separator (Zl, Zp) or bidi and format character."""
    code = ord(char)
    return (unicodedata.category(char) in ('Cc', 'Zl', 'Zp')
            or any(low <= code <= high for low, high in _HIDDEN_RANGES))


def _fail(code):
    raise ValueError('QUALC1534:' + code)


def _text(value, field, limit=MAX_TEXT):
    if (type(value) is not str or len(value) > limit or not value.strip()
            or any(_hidden(c) for c in value)):
        _fail('invalid_text:' + field)
    return value


def _micro(value, field):
    match = _SIGNED.fullmatch(value) if type(value) is str else None
    if match is None:
        _fail('invalid_number:' + field)
    sign, whole, frac = match.groups()
    number = int(whole) * 10 ** 6 + int((frac or '').ljust(6, '0'))
    return -number if sign == '-' else number


def _fmt(value):
    return '%s%d.%06d' % ('-' if value < 0 else '', abs(value) // 10 ** 6, abs(value) % 10 ** 6)


def evaluate_spec_conformance(packet):
    """Return exact conformance bookkeeping or raise ValueError with a QUALC1534: code."""
    if type(packet) is not dict:
        _fail('invalid_packet')
    if set(packet) != {'unit', 'lower_spec', 'upper_spec', 'measurements'}:
        _fail('unknown_fields:packet')
    rows = packet['measurements']
    if type(rows) is not list or not 1 <= len(rows) <= MAX_ITEMS:
        _fail('invalid_count:measurements')
    unit = _text(packet['unit'], 'unit', MAX_UNIT)
    lower = _micro(packet['lower_spec'], 'lower_spec')
    upper = _micro(packet['upper_spec'], 'upper_spec')
    if lower > upper:
        _fail('spec_order')
    parsed, seen = [], set()
    for row in rows:
        if type(row) is not dict:
            _fail('invalid_record:measurements')
        if set(row) != _FIELDS:
            _fail('invalid_fields:measurements')
        key = _text(row['id'], 'id')
        if key in seen:
            _fail('duplicate_id')
        seen.add(key)
        parsed.append((key, _micro(row['value'], 'value')))
    parsed.sort(key=lambda r: r[0])
    items, bad = [], []
    for key, value in parsed:
        if value < lower:
            status, reason = 'nonconforming_below_lower_spec', 'below_lower_spec'
        elif value > upper:
            status, reason = 'nonconforming_above_upper_spec', 'above_upper_spec'
        else:
            status, reason = 'conforming', None
        items.append({'id': key, 'value': _fmt(value), 'status': status})
        if reason:
            bad.append({'id': key, 'value': _fmt(value), 'reason': reason})
    total = len(parsed)
    good = total - len(bad)
    values = [r[1] for r in parsed]
    return {
        'unit': unit,
        'lower_spec': _fmt(lower),
        'upper_spec': _fmt(upper),
        'total': total,
        'conforming': good,
        'nonconforming': len(bad),
        'conforming_fraction': {'numerator': good, 'denominator': total,
                                'decimal_floor_6': _fmt(good * 10 ** 6 // total)},
        'observed_min': _fmt(min(values)),
        'observed_max': _fmt(max(values)),
        'items': items,
        'nonconforming_items': bad,
        'disposition': 'none_assigned',
        'disposition_requires_approval': True,
        'disposition_authority': False,
        'scope': 'declared_measurements_vs_declared_specs_bookkeeping_only',
        'boundary': _BOUNDARY,
    }
