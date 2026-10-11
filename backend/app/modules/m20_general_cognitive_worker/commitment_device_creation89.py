"""Row 89 bounded commitment-device structure audit (COMMIT89).

Caller-supplied declarations only: a goal, a strict ISO deadline, strict ISO check-in
dates, and whether the device is owner-revocable. The mechanism audits the
declared structure exactly (counts, exact ratio, day spacing, property
checklist) and refuses coercive or irrevocable requests. No strength scores,
no adherence estimates, no efficacy claims: structure is reported, nothing
is predicted. Everything outside the declared schema is refused with a
"COMMIT89:" prefixed ValueError. Delta vs the landed heuristic in
negotiation_behavior_0085_0109.py: no weighted scores or estimate intervals;
exact date arithmetic and an explicit property checklist instead.
"""
from __future__ import annotations

import re
from datetime import date
from fractions import Fraction

MAX_CHECKINS = 64
MAX_GOAL = 200

_BANNED_KEYS = ('enforce', 'coerce', 'irrevocable', 'lock', 'punish')
_FIELDS = ('goal', 'deadline', 'checkins', 'reversible', 'self_selected_penalty')

LIMITS = [
    'This audit reports the declared structure only; nothing is measured or predicted about adherence or behavior.',
    'A commitment device remains revocable by its owner; coercive, enforced or irrevocable requests are refused.',
    'Dates are calendar arithmetic over supplied strict YYYY-MM-DD strings (raw length capped, ASCII digits only); no reminder is scheduled and no party is notified.',
    'The penalty value is not echoed; the output reports only whether a penalty was declared (penalty_declared, a boolean). It is never created, enforced or escalated.',
    'Not a replacement for the landed commitment-device heuristic; this is a bounded exact structural delta.',
]


def _fail(msg: str):
    raise ValueError(f'COMMIT89:{msg}')


_DATE_RE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
MAX_DATE_LEN = 64


def _date(value, label, code='BAD_DATE'):
    if not isinstance(value, str):
        _fail('BAD_TYPE:' + label)
    if len(value) > MAX_DATE_LEN:
        _fail('OVERSIZE:' + label)
    if not _DATE_RE.fullmatch(value):
        _fail(f'{code}:{label}')
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(f'{code}:{label}')


def run(request: dict) -> dict:
    """Audit a declared commitment-device structure; refuse coercion."""
    if not isinstance(request, dict):
        _fail('BAD_TYPE:request')
    for key in request:
        if key not in _FIELDS:
            if key in _BANNED_KEYS:
                _fail('COERCE_REQUEST:' + key)
            _fail(f'UNKNOWN_KEY:{key!r}')
    goal = request.get('goal')
    if not isinstance(goal, str):
        _fail('BAD_TYPE:goal')
    if not goal.strip():
        _fail('EMPTY:goal')
    if len(goal) > MAX_GOAL:
        _fail('OVERSIZE:goal')
    deadline = _date(request.get('deadline'), 'deadline')
    reversible = request.get('reversible', True)
    if not isinstance(reversible, bool):
        _fail('BAD_TYPE:reversible')
    if not reversible:
        _fail('IRREVOCABLE')
    penalty = request.get('self_selected_penalty')
    if penalty is not None and not isinstance(penalty, str):
        _fail('BAD_TYPE:penalty')

    raw = request.get('checkins', [])
    if not isinstance(raw, list):
        _fail('BAD_TYPE:checkins')
    if len(raw) > MAX_CHECKINS:
        _fail('OVERSIZE:checkins')
    checkins = []
    seen = set()
    for item in raw:
        day = _date(item, 'checkin')
        if day in seen:
            _fail('DUPLICATE:checkin')
        seen.add(day)
        checkins.append(day)
    checkins.sort()

    before = sum(1 for c in checkins if c <= deadline)
    after = len(checkins) - before
    ratio = Fraction(before, len(checkins)) if checkins else Fraction(0, 1)
    spacing = (checkins[-1] - checkins[0]).days if checkins else 0
    checklist = {
        'has_goal': True,
        'has_deadline': True,
        'has_checkins': bool(checkins),
        'all_checkins_before_deadline': after == 0,
        'owner_revocable': reversible,
        'penalty_declared': penalty is not None,
    }
    required = ('has_goal', 'has_deadline', 'has_checkins', 'all_checkins_before_deadline',
                'owner_revocable')
    missing = [k for k in required if not checklist[k]]
    return {
        'goal': goal,
        'deadline': deadline.isoformat(),
        'checkins': [c.isoformat() for c in checkins],
        'checkin_count': len(checkins),
        'checkins_before_deadline': before,
        'checkins_after_deadline': after,
        'coverage_ratio': f'{ratio.numerator}/{ratio.denominator}',
        'first_to_last_spacing_days': spacing,
        'checklist': checklist,
        'missing': missing,
        'verdict': 'structurally_complete' if not missing else 'missing_properties',
        'limits': list(LIMITS),
    }
