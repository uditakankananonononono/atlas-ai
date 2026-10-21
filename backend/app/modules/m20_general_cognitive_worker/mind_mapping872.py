"""Row 872 bounded mind-map radiation over caller-declared associations (MIND872).

The caller supplies the center topic and every spoke. The mechanism only
arranges the declared spokes: it groups them by declared tier, computes
exact reduced weight shares, and orders output deterministically. It
generates no associations, infers no unstated link, and claims no creativity.
Everything outside the declared surface is refused with a "MIND872:"
prefixed ValueError.
"""
from __future__ import annotations

from fractions import Fraction

MAX_SPOKES = 64
MAX_LABEL = 120
MAX_TIER = 4

INTERPRETATION = 'caller-declared associations only; exact arrangement arithmetic, nothing generated'

LIMITS = [
    'Every spoke is caller-supplied; the mechanism radiates nothing by itself and discovers no unstated association.',
    'Weight shares are exact ratios of declared integer weights; no salience, relevance or truth is computed or implied.',
    'A mind map is an arrangement of declarations, not evidence of understanding; no learning, memory or creativity is claimed.',
]


def _fail(code):
    raise ValueError('MIND872:' + code)


def _label(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_LABEL:
        _fail(field + ' must be nonblank text up to 120 characters')
    return value.strip()


def _weight(value):
    if type(value) is not int or not 0 <= value <= 10 ** 6:
        _fail('spoke weight must be an integer 0..10^6')
    return value


def radiate(request):
    """Arrange declared spokes around the declared center; refuse anything else."""
    if not isinstance(request, dict):
        _fail('request must be a mapping')
    if set(request) != {'center', 'spokes'}:
        _fail('request must have exactly center and spokes')
    center = _label(request['center'], 'center')
    spokes = request['spokes']
    if not isinstance(spokes, list) or not 1 <= len(spokes) <= MAX_SPOKES:
        _fail('spokes must be a list of 1..64 records')
    seen = set()
    rows = []
    for i, s in enumerate(spokes):
        if not isinstance(s, dict) or set(s) != {'id', 'label', 'tier', 'weight'}:
            _fail('spoke %d must have exactly id, label, tier, weight' % i)
        sid = _label(s['id'], 'spoke id')
        if sid in seen:
            _fail('duplicate spoke id')
        seen.add(sid)
        text = _label(s['label'], 'spoke label')
        tier = s['tier']
        if type(tier) is not int or not 1 <= tier <= MAX_TIER:
            _fail('spoke tier must be an integer 1..4')
        rows.append({'id': sid, 'label': text, 'tier': tier, 'weight': _weight(s['weight'])})
    total = sum(r['weight'] for r in rows)
    for r in rows:
        share = Fraction(r['weight'], total) if total else Fraction(0, 1)
        r['weight_share'] = '%d/%d' % (share.numerator, share.denominator)
    rows.sort(key=lambda r: (r['tier'], r['label'], r['id']))
    return {
        'center': center,
        'spokes': rows,
        'spoke_count': len(rows),
        'tiers_present': sorted({r['tier'] for r in rows}),
        'total_weight': total,
        'zero_weight_spoke_ids': [r['id'] for r in rows if r['weight'] == 0],
        'associations_generated': 0,
        'interpretation': INTERPRETATION,
        'limits': list(LIMITS),
    }
