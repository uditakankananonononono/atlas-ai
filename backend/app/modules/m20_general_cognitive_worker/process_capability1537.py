"""Row 1537 Process Capability: exact Cp/Cpk (within) and Pp/Ppk (overall).

The ledger row has an empty description, so the requirement title is the
whole spec. Delta against engineering_1510_1559.py:167 (_capability): that
float routine uses one population standard deviation, labels it the within
sigma, needs both limits, and returns only Cp and Cpk. This unit uses exact
decimal arithmetic and keeps the two sigmas apart (within = MRbar/1.128,
overall = sample standard deviation), reports Cp/Cpk and Pp/Ppk, accepts
one-sided specifications, and refuses limits that are not ordered. Index
arithmetic over supplied data; normality and stability are assumed, not
tested. No process-acceptance claim.
"""
import re
import unicodedata
from decimal import (Context, Decimal, DecimalException, DivisionByZero, InvalidOperation,
                     Overflow, ROUND_HALF_EVEN, Underflow, localcontext)

PREFIX = 'PROCAP1537'
MIN_POINTS = 2
MAX_POINTS = 500
MAX_ABS = Decimal(10) ** 12
D2 = Decimal('1.128')
PRECISION = 64
PLACES = Decimal('0.000000001')
MAX_STUDY_ID = 128
MAX_NUMBER_CHARS = 80
MAX_SIGNIFICANT = 64
MAX_FRACTION = 64
NUMBER = re.compile(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?', re.ASCII)

BOUNDARY = ('Capability indices computed over the supplied series and specification limits '
            'only. Within-sigma is MRbar/1.128; overall sigma is the sample standard '
            'deviation. Both assume an approximately normal, stable process, which is '
            'neither tested nor established here. No process-acceptance or '
            'qualification claim is made.')


def _fail(code, message):
    raise ValueError(f'{PREFIX}: {code + ": " if code else ""}{message}')


def _context():
    return Context(prec=PRECISION, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
                   capitals=1, clamp=0, flags=[],
                   traps=[InvalidOperation, DivisionByZero, Overflow, Underflow])


def _out(value):
    return format(value.quantize(PLACES, rounding=ROUND_HALF_EVEN).normalize(), 'f')


def _parse(raw, label):
    """Exact input: every check runs on the text before any Decimal operation."""
    subject = 'values require' if label == 'values' else f'{label} requires'
    shape = 'ASCII decimal strings' if label == 'values' else 'an ASCII decimal string'
    if type(raw) is not str:
        _fail('invalid_number', f'{subject} {shape} such as -12.5')
    if len(raw) > MAX_NUMBER_CHARS:
        _fail('number_too_long', f'{subject} at most {MAX_NUMBER_CHARS} characters')
    if not NUMBER.fullmatch(raw):
        _fail('invalid_number', f'{subject} {shape} such as -12.5')
    whole, _, fraction = raw.lstrip('-').partition('.')
    significant = len((whole + fraction).lstrip('0'))
    if significant > MAX_SIGNIFICANT or len(fraction) > MAX_FRACTION:
        _fail('number_precision', f'{subject} at most {MAX_SIGNIFICANT} significant digits '
                                  f'and {MAX_FRACTION} fraction digits')
    parsed = Decimal(raw)
    if parsed.copy_abs() > MAX_ABS:
        _fail('number_range', f'{subject} |value| <= 1000000000000')
    return parsed

_BAD_FORMAT = frozenset(list(range(0x200B, 0x2010)) + list(range(0x202A, 0x202F))
                        + list(range(0x2066, 0x206A)) + [0xFEFF])


def _unsafe_char(c):
    return unicodedata.category(c) in ('Cc', 'Zl', 'Zp') or ord(c) == 127 or ord(c) in _BAD_FORMAT


def _study_id(value):
    if type(value) is not str:
        _fail('invalid_study_id', 'study_id requires non-blank text')
    if len(value) > MAX_STUDY_ID:
        _fail('invalid_study_id', f'study_id exceeds {MAX_STUDY_ID} characters')
    if not value.strip():
        _fail('invalid_study_id', 'study_id requires non-blank text')
    if any(_unsafe_char(c) for c in value):
        _fail('invalid_study_id', 'study_id contains disallowed characters')
    return value


def _spec(payload, key):
    raw = payload.get(key)
    return None if raw is None else _parse(raw, key)


def _indices(mean, sigma, lower, upper):
    cpu = (upper - mean) / (3 * sigma) if upper is not None else None
    cpl = (mean - lower) / (3 * sigma) if lower is not None else None
    both = (upper - lower) / (6 * sigma) if upper is not None and lower is not None else None
    present = [x for x in (cpu, cpl) if x is not None]
    return both, cpu, cpl, min(present)


def _fmt(value):
    return None if value is None else _out(value)


def capability_indices(payload):
    if type(payload) is not dict:
        _fail(None, 'payload requires an object')
    if any(k not in ('study_id', 'values', 'lower_spec', 'upper_spec') for k in payload):
        _fail(None, 'unknown key in payload')
    study_id = _study_id(payload.get('study_id'))
    raw = payload.get('values')
    if type(raw) is not list or not MIN_POINTS <= len(raw) <= MAX_POINTS:
        _fail(None, f'values requires a list of {MIN_POINTS}..{MAX_POINTS} points')
    values = [_parse(x, 'values') for x in raw]
    lower = _spec(payload, 'lower_spec')
    upper = _spec(payload, 'upper_spec')
    if lower is None and upper is None:
        _fail(None, 'at least one of lower_spec, upper_spec is required')
    if lower is not None and upper is not None and not lower < upper:
        _fail(None, 'lower_spec requires lower_spec < upper_spec')
    try:
        with localcontext(_context()):
            result = _compute(study_id, values, lower, upper)
    except DecimalException:
        _fail('arithmetic', 'computation could not complete')
    result.update({'within_sigma_estimator': 'MRbar/1.128',
                   'overall_sigma_estimator': 'sample standard deviation (n-1)',
                   'normality_assumed': True, 'stability_established': False,
                   'process_acceptance_claimed': False, 'boundary': BOUNDARY})
    return result


def _compute(study_id, values, lower, upper):
    n = len(values)
    mean = sum(values, Decimal(0)) / n
    mr_bar = sum((abs(values[i] - values[i - 1]) for i in range(1, n)), Decimal(0)) / (n - 1)
    sigma_within = mr_bar / D2
    sigma_overall = (sum(((x - mean) ** 2 for x in values), Decimal(0)) / (n - 1)).sqrt()
    if sigma_within == 0 or sigma_overall == 0:
        _fail(None, 'capability undefined for zero observed variation')
    cp, cpu, cpl, cpk = _indices(mean, sigma_within, lower, upper)
    pp, ppu, ppl, ppk = _indices(mean, sigma_overall, lower, upper)
    return {
        'study_id': study_id, 'n': n, 'mean': _out(mean),
        'sigma_within': _out(sigma_within), 'sigma_overall': _out(sigma_overall),
        'cp': _fmt(cp), 'cpu': _fmt(cpu), 'cpl': _fmt(cpl), 'cpk': _fmt(cpk),
        'pp': _fmt(pp), 'ppu': _fmt(ppu), 'ppl': _fmt(ppl), 'ppk': _fmt(ppk)}
