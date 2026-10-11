"""Row705: bounded caller-supplied ADR bookkeeping, without side effects."""
from __future__ import annotations

import unicodedata

_REQUIRED = ('title', 'context', 'decision', 'consequences')
_ALLOWED = frozenset(_REQUIRED + ('status', 'alternatives', 'supersedes'))
_STATUSES = ('proposed', 'accepted', 'rejected', 'deprecated', 'superseded')


def _refuse(reason: str) -> None:
    raise ValueError('ARCHIT705: ' + reason)


def _text(value: object, field: str, cap: int) -> str:
    if type(value) is not str:
        _refuse(field + ' must be nonblank safe text')
    if len(value) > cap:
        _refuse(field + ' raw length exceeds ' + str(cap))
    if not value.strip() or any(unicodedata.category(c) in ('Cc', 'Cf', 'Zl', 'Zp') for c in value):
        _refuse(field + ' must be nonblank safe text')
    return value


def _items(value: object, field: str, required: bool) -> list[str]:
    if type(value) is not list:
        _refuse(field + ' must be a list')
    if len(value) > 32:
        _refuse(field + ' count exceeds 32')
    if required and not value:
        _refuse(field + ' must not be empty')
    return [_text(item, field + '[' + str(index) + ']', 1000) for index, item in enumerate(value)]


def architecture_decision_records705(data: object) -> dict:
    """Return a detached record; accepted is a supplied label, never approval."""
    if type(data) is not dict:
        _refuse('input must be a dict')
    # Cardinality check bounds subsequent key scanning, including arbitrary keys.
    if len(data) > len(_ALLOWED) or any(type(key) is not str or key not in _ALLOWED for key in data):
        _refuse('unknown fields')
    for field in _REQUIRED:
        if field not in data:
            _refuse('missing ' + field)
    title = _text(data['title'], 'title', 200)
    context = _text(data['context'], 'context', 4000)
    decision = _text(data['decision'], 'decision', 4000)
    status = data.get('status', 'proposed')
    if type(status) is not str:
        _refuse('status must be a declared ADR status')
    if len(status) > 10:
        _refuse('status raw length exceeds 10')
    if status not in _STATUSES:
        _refuse('status must be a declared ADR status')
    alternatives = _items(data.get('alternatives', []), 'alternatives', False)
    consequences = _items(data['consequences'], 'consequences', True)
    supersedes = data.get('supersedes')
    if supersedes is not None:
        supersedes = _text(supersedes, 'supersedes', 200)
    return {
        'record': {'title': title, 'status': status, 'context': context,
                   'decision': decision, 'alternatives': alternatives,
                   'consequences': consequences, 'supersedes': supersedes},
        'counts': {'alternatives': len(alternatives), 'consequences': len(consequences)},
        'scope': 'caller_supplied_adr_bookkeeping_only',
        'immutable_history_required': True,
        'history_immutability_enforced': False,
        'architecture_validated': False,
        'repository_behavior_verified': False,
        'release_authorized': False,
        'evidence_verified': False,
        'human_review_required': True,
    }
