"""SOCIAL98: exact checks over caller-declared social-proof counts.

Takes supplied counts (observed_count of sample_size, a source and a date) and
returns exact proportions, a Wilson interval rounded outward to six decimals,
caller-rule checks and a plain disclosure of the supplied numbers. It does not
fetch, verify evidence, predict effects or advise.
"""
import copy
import re
from datetime import date
from fractions import Fraction
from math import floor, ceil, isqrt

LIMITS = {'claim': 500, 'source': 200, 'sample_size': 1000000000, 'min_sample': 1000000000,
          'max_age_days': 3650, 'z_min': 1, 'z_max': 5, 'z_digits': 7}
KEYS = ('claim', 'evidence', 'as_of', 'min_sample', 'max_age_days', 'z')
EVIDENCE_KEYS = ('source', 'as_of', 'observed_count', 'sample_size')
_SCALE = 10 ** 6
_Z = re.compile(r'[0-9]{1,7}(?:/[0-9]{1,7})?')
_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')


class Social98Error(ValueError):
    pass


def _refuse(text):
    raise Social98Error('SOCIAL98: ' + text)


def _text(value, label, limit):
    if (type(value) is not str or not value.strip() or len(value) > limit
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        _refuse(label + ' must be a nonblank string of at most %d characters without control characters' % limit)
    return value


def _int(value, low, high, message):
    if type(value) is not int or not low <= value <= high:
        _refuse(message)
    return value


def _date(value, label):
    if type(value) is str and _DATE.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    _refuse(label + ' must be an ASCII YYYY-MM-DD calendar date')


def _z(value):
    message = 'z must be a rational string p or p/q with 1 <= z <= 5 and components of at most 7 digits'
    if type(value) is not str or not _Z.fullmatch(value):
        _refuse(message)
    parts = value.split('/')
    if len(parts) == 2 and int(parts[1]) == 0:
        _refuse(message)
    z = Fraction(value)
    if not LIMITS['z_min'] <= z <= LIMITS['z_max']:
        _refuse(message)
    return z


def _grid(value):
    return '%d.%06d' % (value // _SCALE, value % _SCALE)


def _wilson(k, n, z):
    """Wilson score interval; the square root is rounded up so the interval encloses the exact one."""
    p = Fraction(k, n)
    z2 = z * z
    centre = p + z2 / (2 * n)
    denominator = 1 + z2 / n
    radicand = z2 * (p * (1 - p) / n + z2 / (4 * n * n))
    scaled = radicand * _SCALE * _SCALE
    root = isqrt(floor(scaled))
    while Fraction(root * root) < scaled:
        root += 1
    root = Fraction(root, _SCALE)
    low = max(0, floor((centre - root) / denominator * _SCALE))
    high = min(_SCALE, ceil((centre + root) / denominator * _SCALE))
    return [_grid(low), _grid(high)]


def evaluate_social_proof(packet):
    """Check supplied counts against caller rules; returns exact results or raises Social98Error."""
    if type(packet) is not dict:
        _refuse('packet must be a dict')
    if set(packet) not in (set(KEYS), set(KEYS) | {'claimed_percent'}):
        _refuse('packet keys must be claim, evidence, as_of, min_sample, max_age_days, z and optional claimed_percent')
    claim = _text(packet['claim'], 'claim', LIMITS['claim'])
    evidence = packet['evidence']
    if type(evidence) is not dict or set(evidence) != set(EVIDENCE_KEYS):
        _refuse('evidence keys must be exactly source, as_of, observed_count, sample_size')
    source = _text(evidence['source'], 'source', LIMITS['source'])
    evidence_date = _date(evidence['as_of'], 'evidence as_of')
    n = _int(evidence['sample_size'], 1, LIMITS['sample_size'], 'sample_size must be an integer within 1..1000000000')
    k = _int(evidence["observed_count"], 0, n, 'observed_count must be an integer within 0..sample_size')
    packet_date = _date(packet['as_of'], 'as_of')
    min_sample = _int(packet['min_sample'], 1, LIMITS['min_sample'], 'min_sample must be an integer within 1..1000000000')
    max_age = _int(packet['max_age_days'], 0, LIMITS['max_age_days'], 'max_age_days must be an integer within 0..3650')
    z = _z(packet['z'])
    claimed = packet.get('claimed_percent')
    if claimed is not None:
        _int(claimed, 0, 100, 'claimed_percent must be an integer within 0..100')
    age = (packet_date - evidence_date).days
    if age < 0:
        _refuse('evidence as_of is after packet as_of')
    percent = (200 * k + n) // (2 * n)
    rules = {'min_sample_met': n >= min_sample,
             'claim_consistent': None if claimed is None else claimed == percent,
             'evidence_fresh': age <= max_age}
    blocked = []
    if rules['claim_consistent'] is False:
        blocked.append('claim_mismatch')
    if not rules['evidence_fresh']:
        blocked.append('evidence_stale')
    if not rules['min_sample_met']:
        blocked.append('min_sample_not_met')
    allowed = not blocked
    return {
        'claim': claim,
        'evidence': {'source': source, 'as_of': evidence['as_of'], 'observed_count': k, 'sample_size': n, 'age_days': age},
        'proportion': str(Fraction(k, n)),
        'percent_rounded': percent,
        'z': str(z),
        'wilson_interval': _wilson(k, n, z),
        'rules': rules,
        'blocked_reasons': sorted(blocked),
        'deployment_allowed': allowed,
        'disclosure': '%d of %d responses from %s as of %s.' % (k, n, source, evidence['as_of']) if allowed else None,
        'scope': 'caller_declared_counts_only',
        'real_world_effect_verified': False,
        'limits': copy.deepcopy(LIMITS),
        'boundary': 'Declared counts and caller rules only. Not a measure of real-world effect, a prediction, advice, evidence verification or permission to act; the disclosure states only the supplied counts.',
    }
