"""Bounded declared ATDD agreement bookkeeping (row 688).

Not shipped product code. Given a caller-supplied feature, acceptance
criteria, examples, stakeholders and declared agreements, this unit keeps
exact bookkeeping over the DECLARED agreement state: which stakeholders
have declared agreement, which criteria carry at least one example, and
which examples point at criteria that do not exist. Every agreement flag is
caller-declared and is never verified; the unit never executes acceptance
tests, never runs caller code or any external tool, and makes no coverage,
quality or release-authority claim. It refuses missing, blank, mistyped,
duplicated or oversize inputs, unknown keys, and any key that asks for
execution, deployment, release or certification, each with a stated code.
It is a bookkeeping aid for a human reviewer; the recorded agreement is the
caller's declaration, not an observed fact.
"""
from __future__ import annotations

import unicodedata

_CODE = 'ACCEPT688'
_KEYS = frozenset({'feature', 'acceptance_criteria', 'examples', 'stakeholders', 'agreed_by'})
_EXECUTION_KEYS = ('execute', 'run_tests', 'deploy', 'release', 'certify')
MAX_FEATURE_LEN = 512
MAX_TEXT_LEN = 512
MAX_ID_LEN = 128
MAX_NAME_LEN = 128
MAX_CRITERIA = 128
MAX_EXAMPLES = 256
MAX_STAKEHOLDERS = 64
MAX_AGREED = 64
MAX_KEY_ECHO = 128
MAX_REQUEST_KEYS = 64
_BANNED_CATS = ('Cc', 'Cf', 'Zl', 'Zp')
_LIMITS = [
    'This unit is bounded declared ATDD agreement bookkeeping, not shipped product code.',
    'Agreement flags are caller-declared and never verified by this unit.',
    'It never executes acceptance tests, caller code, a repository suite, or any external tool.',
    'Bookkeeping is over caller-supplied criteria, examples and stakeholders only; no coverage, quality or release-authority claim is made.',
]


def _refuse(code: str) -> None:
    raise ValueError('%s:%s' % (_CODE, code))


def _screen(text: str) -> bool:
    return any(unicodedata.category(ch) in _BANNED_CATS for ch in text)


def _str_field(v, name: str, max_len: int) -> str:
    if v is None:
        _refuse('MISSING:' + name)
    if type(v) is not str:
        _refuse('BAD_TYPE:' + name)
    if len(v) > max_len:
        _refuse('OVERSIZE:' + name)
    if _screen(v):
        _refuse('BAD_TYPE:' + name)
    text = v.strip()
    if not text:
        _refuse('EMPTY:' + name)
    return text


def _str_list(v, name: str, max_items: int, item_name: str, dup_name: str) -> list:
    if v is None:
        _refuse('MISSING:' + name)
    if type(v) is not list:
        _refuse('BAD_TYPE:' + name)
    if len(v) > max_items:
        _refuse('OVERSIZE:' + name)
    out = []
    for item in v:
        out.append(_str_field(item, item_name, MAX_NAME_LEN))
    if len(set(out)) != len(out):
        _refuse('DUPLICATE:' + dup_name)
    return out


_ENTRY_KEYS = {'criterion': frozenset({'id', 'text'}),
               'example': frozenset({'criterion_id', 'text'})}


def _entry(v, name: str) -> dict:
    if type(v) is not dict:
        _refuse('BAD_TYPE:' + name)
    if len(v) > 2:
        _refuse('OVERSIZE:' + name)
    for key in v:
        if type(key) is not str or key not in _ENTRY_KEYS[name]:
            _refuse('UNKNOWN_FIELD:' + name)
    return v


def run(request: dict) -> dict:
    """Run one declared ATDD agreement bookkeeping pass from a JSON-like request."""
    if type(request) is not dict:
        _refuse('BAD_TYPE:request')
    if len(request) > MAX_REQUEST_KEYS:
        _refuse('OVERSIZE:request')
    for key in request:
        if type(key) is str and len(key) > MAX_KEY_ECHO:
            _refuse('OVERSIZE:request')
        if type(key) is not str or _screen(key):
            _refuse('BAD_TYPE:key')
    for key in sorted(request):
        if key in _EXECUTION_KEYS:
            _refuse('EXECUTION_REQUEST:' + key)
        if key not in _KEYS:
            _refuse('UNKNOWN_KEY')

    feature = _str_field(request.get('feature'), 'feature', MAX_FEATURE_LEN)

    criteria_raw = request.get('acceptance_criteria')
    if criteria_raw is None:
        _refuse('MISSING:acceptance_criteria')
    if type(criteria_raw) is not list:
        _refuse('BAD_TYPE:acceptance_criteria')
    if not criteria_raw:
        _refuse('EMPTY:acceptance_criteria')
    if len(criteria_raw) > MAX_CRITERIA:
        _refuse('OVERSIZE:acceptance_criteria')
    criteria = []
    for entry in criteria_raw:
        entry = _entry(entry, 'criterion')
        cid = _str_field(entry.get('id'), 'criterion_id', MAX_ID_LEN)
        ctext = _str_field(entry.get('text'), 'criterion_text', MAX_TEXT_LEN)
        criteria.append({'id': cid, 'text': ctext})
    criterion_ids = [c['id'] for c in criteria]
    if len(set(criterion_ids)) != len(criterion_ids):
        _refuse('DUPLICATE:criterion_id')

    examples_raw = request.get('examples')
    if examples_raw is None:
        _refuse('MISSING:examples')
    if type(examples_raw) is not list:
        _refuse('BAD_TYPE:examples')
    if len(examples_raw) > MAX_EXAMPLES:
        _refuse('OVERSIZE:examples')
    examples = []
    for entry in examples_raw:
        entry = _entry(entry, 'example')
        eid = _str_field(entry.get('criterion_id'), 'example_criterion_id', MAX_ID_LEN)
        etext = _str_field(entry.get('text'), 'example_text', MAX_TEXT_LEN)
        examples.append({'criterion_id': eid, 'text': etext})

    stakeholders = _str_list(request.get('stakeholders'), 'stakeholders', MAX_STAKEHOLDERS,
                             'stakeholder', 'stakeholder')
    if not stakeholders:
        _refuse('EMPTY:stakeholders')

    agreed_raw = request.get('agreed_by')
    if agreed_raw is None:
        agreed_by = []
    else:
        if type(agreed_raw) is not list:
            _refuse('BAD_TYPE:agreed_by')
        if len(agreed_raw) > MAX_AGREED:
            _refuse('OVERSIZE:agreed_by')
        agreed_by = [_str_field(x, 'agreement', MAX_NAME_LEN) for x in agreed_raw]
        if len(set(agreed_by)) != len(agreed_by):
            _refuse('DUPLICATE:agreement')

    known = set(stakeholders)
    linked = {e['criterion_id'] for e in examples}
    return {
        'feature': feature,
        'criteria_count': len(criteria),
        'example_count': len(examples),
        'stakeholders': stakeholders,
        'agreed_by': agreed_by,
        'pending_agreement': sorted(known - set(agreed_by)),
        'unlisted_agreements': sorted(set(agreed_by) - known),
        'agreement_complete': known <= set(agreed_by),
        'uncovered_criterion_ids': sorted(set(criterion_ids) - linked),
        'orphan_example_criterion_ids': sorted(linked - set(criterion_ids)),
        'executable_before_implementation': True,
        'tests_executed': False,
        'caller_declared_agreement': True,
        'limits': list(_LIMITS),
    }
