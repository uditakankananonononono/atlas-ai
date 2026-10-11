"""Row 1538 Measurement Systems Analysis: balanced crossed gauge R&R from raw repeats.

The ledger row has an empty description, so the requirement title is the
whole spec. Delta against engineering_1510_1559.py:172 (_msa): that routine
adds three variance numbers the caller already computed. This unit takes the
raw repeat measurements of a balanced parts x operators x repeats study and
derives the variance components itself with a two-factor ANOVA (operator and
part crossed, with interaction), in exact decimal arithmetic. Negative
estimates are reported as zero and listed. It makes no gauge-approval claim.
"""
import re
import unicodedata
from decimal import (Context, Decimal, DecimalException, DivisionByZero, InvalidOperation,
                     Overflow, ROUND_HALF_EVEN, Underflow, localcontext)

PREFIX = 'MEASYS1538'
MIN_CELLS = 4
MAX_CELLS = 1000
MIN_PARTS, MAX_PARTS = 2, 50
MIN_OPERATORS, MAX_OPERATORS = 2, 20
MIN_REPEATS, MAX_REPEATS = 2, 20
MAX_ABS = Decimal(10) ** 12
PRECISION = 64
PLACES = Decimal('0.000000001')
MAX_TEXT = 128
MAX_NUMBER_CHARS = 80
MAX_SIGNIFICANT = 64
MAX_FRACTION = 64
NUMBER = re.compile(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?', re.ASCII)
_BAD_FORMAT = frozenset(list(range(0x200B, 0x2010)) + list(range(0x202A, 0x202F))
                        + list(range(0x2066, 0x206A)) + [0xFEFF])

BOUNDARY = ('Variance components are computed from the supplied repeat measurements with a '
            'balanced crossed two-factor ANOVA; negative estimates are reported as zero and '
            'listed. Normal, independent errors are assumed and not tested. No gauge '
            'approval, acceptance threshold or capability claim is made.')


def _fail(code, message):
    raise ValueError(f'{PREFIX}: {code + ": " if code else ""}{message}')


def _context():
    return Context(prec=PRECISION, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
                   capitals=1, clamp=0, flags=[],
                   traps=[InvalidOperation, DivisionByZero, Overflow, Underflow])


def _out(value):
    return format(value.quantize(PLACES, rounding=ROUND_HALF_EVEN).normalize(), 'f')


def _unsafe_char(c):
    return unicodedata.category(c) in ('Cc', 'Zl', 'Zp') or ord(c) == 127 or ord(c) in _BAD_FORMAT


def _text(value, field):
    code = f'invalid_{field}'
    if type(value) is not str:
        _fail(code, f'{field} requires non-blank text')
    if len(value) > MAX_TEXT:
        _fail(code, f'{field} exceeds {MAX_TEXT} characters')
    if not value.strip():
        _fail(code, f'{field} requires non-blank text')
    if any(_unsafe_char(c) for c in value):
        _fail(code, f'{field} contains disallowed characters')
    return value


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


def gauge_rr_study(payload):
    if type(payload) is not dict:
        _fail(None, 'payload requires an object')
    if any(k not in ('study_id', 'measurements') for k in payload):
        _fail(None, 'unknown key in payload')
    study_id = _text(payload.get('study_id'), 'study_id')
    raw = payload.get('measurements')
    if type(raw) is not list or not MIN_CELLS <= len(raw) <= MAX_CELLS:
        _fail(None, f'measurements requires a list of {MIN_CELLS}..{MAX_CELLS} records')
    cells = {}
    for row in raw:
        if type(row) is not dict:
            _fail(None, 'measurement requires an object')
        if any(k not in ('part', 'operator', 'values') for k in row):
            _fail(None, 'unknown key in measurement')
        part = _text(row.get('part'), 'part')
        operator = _text(row.get('operator'), 'operator')
        vals = row.get('values')
        if type(vals) is not list or not MIN_REPEATS <= len(vals) <= MAX_REPEATS:
            _fail(None, f'values requires a list of {MIN_REPEATS}..{MAX_REPEATS} decimal strings')
        key = (part, operator)
        if key in cells:
            _fail(None, 'duplicate cell for one part and one operator')
        cells[key] = [_value(x) for x in vals]
    repeats = {len(v) for v in cells.values()}
    if len(repeats) != 1:
        _fail(None, 'unbalanced study: every cell requires the same number of values')
    r = repeats.pop()
    parts = sorted({k[0] for k in cells})
    operators = sorted({k[1] for k in cells})
    if not MIN_PARTS <= len(parts) <= MAX_PARTS:
        _fail(None, f'parts requires {MIN_PARTS}..{MAX_PARTS} distinct parts')
    if not MIN_OPERATORS <= len(operators) <= MAX_OPERATORS:
        _fail(None, f'operators requires {MIN_OPERATORS}..{MAX_OPERATORS} distinct operators')
    if len(cells) != len(parts) * len(operators):
        _fail(None, 'incomplete study: every part requires every operator')
    p, o = len(parts), len(operators)
    try:
        with localcontext(_context()):
            result = _compute(study_id, cells, parts, operators, r)
    except DecimalException:
        _fail('arithmetic', 'computation could not complete')
    return result


def _compute(study_id, cells, parts, operators, r):
    p, o = len(parts), len(operators)
    cell_mean = {k: sum(v, Decimal(0)) / r for k, v in cells.items()}
    part_mean = {a: sum((cell_mean[(a, b)] for b in operators), Decimal(0)) / o for a in parts}
    op_mean = {b: sum((cell_mean[(a, b)] for a in parts), Decimal(0)) / p for b in operators}
    grand = sum(part_mean.values(), Decimal(0)) / p
    ss_part = o * r * sum(((m - grand) ** 2 for m in part_mean.values()), Decimal(0))
    ss_op = p * r * sum(((m - grand) ** 2 for m in op_mean.values()), Decimal(0))
    ss_int = r * sum(((cell_mean[(a, b)] - part_mean[a] - op_mean[b] + grand) ** 2
                      for a in parts for b in operators), Decimal(0))
    ss_err = sum(((x - cell_mean[k]) ** 2 for k, v in cells.items() for x in v), Decimal(0))
    ms_part = ss_part / (p - 1)
    ms_op = ss_op / (o - 1)
    ms_int = ss_int / ((p - 1) * (o - 1))
    ms_err = ss_err / (p * o * (r - 1))
    raw = {'interaction': (ms_int - ms_err) / r,
           'operator': (ms_op - ms_int) / (p * r),
           'part_to_part': (ms_part - ms_int) / (o * r)}
    truncated = [k for k in ('interaction', 'operator', 'part_to_part') if raw[k] < 0]
    comp = {k: max(v, Decimal(0)) for k, v in raw.items()}
    comp['repeatability'] = ms_err
    comp['reproducibility'] = comp['operator'] + comp['interaction']
    comp['gage_rr'] = comp['repeatability'] + comp['reproducibility']
    comp['total'] = comp['gage_rr'] + comp['part_to_part']
    if comp['total'] == 0:
        _fail(None, 'study undefined for zero observed variation')
    order = ('repeatability', 'interaction', 'operator', 'reproducibility',
             'part_to_part', 'gage_rr', 'total')
    variances = {k: _out(comp[k]) for k in order}
    deviations = {k: _out(comp[k].sqrt()) for k in order}
    percent = {k: _out(100 * comp[k] / comp['total'])
               for k in ('repeatability', 'reproducibility', 'gage_rr', 'part_to_part')}
    grand_out = _out(grand)
    return {'study_id': study_id, 'parts': p, 'operators': o, 'replicates': r,
            'grand_mean': grand_out, 'variance_components': variances,
            'standard_deviations': deviations, 'percent_contribution': percent,
            'truncated_components': truncated,
            'method': 'balanced crossed two-factor ANOVA, variance components from mean squares',
            'gauge_approval_claimed': False, 'boundary': BOUNDARY}
