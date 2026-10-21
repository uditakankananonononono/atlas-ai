"""Row 880 bounded belief revision over caller-declared beliefs and evidence (BELIEF880).

The caller declares prior belief weights and signed evidence. The mechanism
applies one declared deterministic rule: revised weight = prior + signed
evidence strengths, clamped to [0, 1000], rendered as exact reduced
Fractions of the declared scale. It verifies no truth, computes no
probability, and infers no unstated belief. Everything outside the declared
surface is refused with a "BELIEF880:" prefixed ValueError.
"""
from __future__ import annotations

from fractions import Fraction

MAX_BELIEFS = 64
MAX_EVIDENCE = 256
MAX_TEXT = 200
MAX_WEIGHT = 1000
MAX_STRENGTH = 100
RETRACT_BELOW = 100  # declared retraction threshold on the 0..1000 scale

INTERPRETATION = 'caller-declared beliefs and evidence only; exact additive revision on a declared scale'

LIMITS = [
    'Revised weights are deterministic arithmetic over declared numbers on a declared 0..1000 scale, not probabilities or degrees of real belief.',
    'Evidence is accepted as declared; its truth, provenance and sufficiency are never verified by this unit.',
    'A retraction flag marks the declared weight crossing the declared threshold; no mind is changed and no action is taken.',
]


def _fail(code):
    raise ValueError('BELIEF880:' + code)


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        _fail(field + ' must be nonblank text up to 200 characters')
    return value.strip()


def _int(value, field, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        _fail('%s must be an integer %d..%d' % (field, lo, hi))
    return value


def revise(request):
    """Apply declared evidence to declared priors; refuse anything else."""
    if not isinstance(request, dict):
        _fail('request must be a mapping')
    if set(request) != {'beliefs', 'evidence'}:
        _fail('request must have exactly beliefs and evidence')
    beliefs = request['beliefs']
    if not isinstance(beliefs, list) or not 1 <= len(beliefs) <= MAX_BELIEFS:
        _fail('beliefs must be a list of 1..64 records')
    evidence = request['evidence']
    if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE:
        _fail('evidence must be a list of at most 256 records')
    priors = {}
    order = []
    for i, b in enumerate(beliefs):
        if not isinstance(b, dict) or set(b) != {'id', 'statement', 'prior'}:
            _fail('belief %d must have exactly id, statement, prior' % i)
        bid = _text(b['id'], 'belief id')
        if bid in priors:
            _fail('duplicate belief id')
        priors[bid] = {'id': bid, 'statement': _text(b['statement'], 'belief statement'),
                       'prior': _int(b['prior'], 'belief prior', 0, MAX_WEIGHT)}
        order.append(bid)
    seen_ev = set()
    deltas = {bid: 0 for bid in order}
    for i, e in enumerate(evidence):
        if not isinstance(e, dict) or set(e) != {'id', 'belief_id', 'direction', 'strength'}:
            _fail('evidence %d must have exactly id, belief_id, direction, strength' % i)
        eid = _text(e['id'], 'evidence id')
        if eid in seen_ev:
            _fail('duplicate evidence id')
        seen_ev.add(eid)
        bid = _text(e['belief_id'], 'evidence belief_id')
        if bid not in priors:
            _fail('evidence references unknown belief')
        direction = e['direction']
        if direction not in ('supports', 'refutes'):
            _fail('evidence direction must be supports or refutes')
        strength = _int(e['strength'], 'evidence strength', 0, MAX_STRENGTH)
        deltas[bid] += strength if direction == 'supports' else -strength
    revised = []
    for bid in order:
        b = priors[bid]
        raw = b['prior'] + deltas[bid]
        clamped = min(MAX_WEIGHT, max(0, raw))
        share = Fraction(clamped, MAX_WEIGHT)
        revised.append({
            'id': bid, 'statement': b['statement'],
            'prior': b['prior'], 'signed_evidence': deltas[bid],
            'revised': clamped,
            'revised_share': '%d/%d' % (share.numerator, share.denominator),
            'clamped': clamped != raw,
            'status': ('retracted' if clamped < RETRACT_BELOW and b['prior'] >= RETRACT_BELOW
                       else 'below_threshold' if clamped < RETRACT_BELOW
                       else 'strengthened' if deltas[bid] > 0
                       else 'weakened' if deltas[bid] < 0 else 'unchanged'),
        })
    return {
        'beliefs': revised,
        'belief_count': len(revised),
        'evidence_count': len(evidence),
        'retracted_ids': [r['id'] for r in revised if r['status'] == 'retracted'],
        'retraction_threshold': RETRACT_BELOW,
        'scale': MAX_WEIGHT,
        'evidence_truth_verified': False,
        'interpretation': INTERPRETATION,
        'limits': list(LIMITS),
    }
