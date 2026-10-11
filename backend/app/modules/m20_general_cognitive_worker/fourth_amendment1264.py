"""Row 1264 Fourth Amendment: caller-declared search and seizure bookkeeping.

The ledger row has an empty description, so the requirement title is the whole
spec. Delta against legal_support_1260_1309.py:21 (SPECS row 1264, output key
search_seizure_map) served by analyze_legal_feature at :96: that shared template
passes one free-form row_inputs object through untouched and checks only
authorities, facts and analysis items. This unit adds a typed declaration for
the six questions the row names: government conduct, standing, warrant,
exception, scope and suppression. Each is checked against closed label sets,
bounded, linked to supplied authorities, and reported as declared or open.
It never rules on reasonableness or suppression, never verifies an authority,
and files or contacts no one.
"""
import re
import unicodedata
from datetime import date

PREFIX = 'FOURTH1264'
MAX_TEXT = 200
MAX_LABEL = 32
MAX_AUTHORITIES = 20
MAX_FACTS = 20
MAX_ASSERTIONS = 20
MAX_EXCEPTIONS = 10
MAX_SCOPE = 10
MAX_QUESTIONS = 10
MAX_REFS = 10
_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
ACTORS = ('government', 'private', 'unknown')
ACTIVITIES = ('search', 'seizure', 'search_and_seizure', 'undetermined')
STANDING_BASES = ('property', 'privacy', 'presence', 'other', 'unspecified')
WARRANT_STATUSES = ('none', 'requested', 'issued', 'unknown')
EXCEPTIONS = ('consent', 'plain_view', 'exigency', 'search_incident_to_arrest',
              'automobile', 'inventory', 'border', 'other')
ASSERTED_BY = ('prosecution', 'defense', 'court_record', 'unknown')
LIMIT_SOURCES = ('warrant_text', 'consent_terms', 'exception_boundary', 'unspecified')
TOP_KEYS = frozenset(('matter_id', 'jurisdiction', 'as_of', 'conduct', 'authorities', 'standing',
                      'warrant', 'exceptions', 'scope_items', 'suppression_questions',
                      'sourced_facts', 'assertions'))
BOUNDARY = ('Legal work product for review, not legal advice. Licensed counsel must verify '
            'jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.')


def _fail(code, message):
    raise ValueError(f'{PREFIX}: {code}: {message}')


def _unsafe(ch):
    return unicodedata.category(ch) in ('Cc', 'Cf', 'Zl', 'Zp')


def _text(value, field):
    if type(value) is not str:
        _fail(f'invalid_{field}', f'{field} requires text')
    if len(value) > MAX_TEXT:
        _fail(f'invalid_{field}', f'{field} exceeds {MAX_TEXT} characters')
    if not value.strip():
        _fail(f'invalid_{field}', f'{field} requires non-blank text')
    if any(_unsafe(c) for c in value):
        _fail(f'invalid_{field}', f'{field} contains disallowed characters')
    return value


def _label(value, field, allowed):
    if type(value) is not str:
        _fail(f'invalid_{field}', f'{field} requires a declared label')
    if len(value) > MAX_LABEL:
        _fail(f'invalid_{field}', f'{field} labels exceed {MAX_LABEL} characters')
    if value not in allowed:
        _fail(f'invalid_{field}', f'{field} requires a declared label')
    return value


def _record(value, field, keys):
    if type(value) is not dict:
        _fail(f'invalid_{field}', f'{field} requires an object')
    if len(value) > len(keys):
        _fail('invalid_count', f'{field} exceeds {len(keys)} fields')
    if any(type(k) is not str for k in value) or set(value) - set(keys):
        _fail(f'invalid_{field}', f'{field} has unsupported fields')
    return value


def _list(value, field, cap, minimum=0):
    if type(value) is not list:
        _fail(f'invalid_{field}', f'{field} requires a list')
    if len(value) > cap:
        _fail('invalid_count', f'{field} exceeds {cap} entries')
    if len(value) < minimum:
        _fail('invalid_count', f'{field} requires at least {minimum} entries')
    return value


def _date(value, field):
    if type(value) is not str:
        _fail(f'invalid_{field}', f'{field} requires text')
    if len(value) != 10:
        _fail(f'invalid_{field}', f'{field} requires an ISO date')
    if not _DATE.fullmatch(value):
        _fail(f'invalid_{field}', f'{field} requires an ISO date')
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(f'invalid_{field}', f'{field} requires an ISO date')


def _refs(value, field, known):
    refs = _list(value, field, MAX_REFS)
    for r in refs:
        if type(r) is not str:
            _fail('invalid_reference', f'{field} must name supplied authorities')
        if len(r) > MAX_TEXT:
            _fail('invalid_reference', f'{field} references exceed {MAX_TEXT} characters')
        if r not in known:
            _fail('invalid_reference', f'{field} must name supplied authorities')
    if len(set(refs)) != len(refs):
        _fail('invalid_reference', f'{field} must name distinct authorities')
    return list(refs)


def map_fourth_amendment(payload):
    """Return the declared-versus-open map for one matter; never a legal conclusion."""
    if type(payload) is not dict:
        _fail('invalid_payload', 'payload requires an object')
    if len(payload) > len(TOP_KEYS):
        _fail('invalid_count', f'payload exceeds {len(TOP_KEYS)} fields')
    if any(type(k) is not str for k in payload) or set(payload) - TOP_KEYS:
        _fail('invalid_payload', 'payload has unsupported fields')
    for key in ('matter_id', 'jurisdiction', 'as_of', 'conduct', 'authorities'):
        if key not in payload:
            _fail(f'invalid_{key}', f'{key} is required')
    matter = _text(payload['matter_id'], 'matter_id')
    jurisdiction = _text(payload['jurisdiction'], 'jurisdiction')
    as_of_text = payload['as_of']
    as_of = _date(as_of_text, 'as_of')

    authorities, known, stale = [], set(), []
    for raw in _list(payload['authorities'], 'authorities', MAX_AUTHORITIES, 1):
        raw = _record(raw, 'authorities', ('id', 'citation', 'source', 'last_checked'))
        for k in ('id', 'citation', 'source', 'last_checked'):
            if k not in raw:
                _fail('invalid_authorities', 'authorities entries require id, citation, source and last_checked')
        aid = _text(raw['id'], 'authorities')
        if aid in known:
            _fail('invalid_authorities', 'authorities require distinct ids')
        checked = _date(raw['last_checked'], 'authorities')
        authorities.append({'id': aid, 'citation': _text(raw['citation'], 'authorities'),
                            'source': _text(raw['source'], 'authorities'),
                            'last_checked': raw['last_checked'], 'independently_verified': False})
        known.add(aid)
        if checked < as_of:
            stale.append(aid)

    c = _record(payload['conduct'], 'conduct', ('actor', 'activity', 'description'))
    for k in ('actor', 'activity', 'description'):
        if k not in c:
            _fail('invalid_conduct', 'conduct requires actor, activity and description')
    conduct = {'actor': _label(c['actor'], 'conduct', ACTORS),
               'activity': _label(c['activity'], 'conduct', ACTIVITIES),
               'description': _text(c['description'], 'conduct')}

    standing = None
    if 'standing' in payload:
        s = _record(payload['standing'], 'standing', ('claimant_label', 'basis'))
        if set(s) != {'claimant_label', 'basis'}:
            _fail('invalid_standing', 'standing requires claimant_label and basis')
        standing = {'claimant_label': _text(s['claimant_label'], 'standing'),
                    'basis': _label(s['basis'], 'standing', STANDING_BASES)}

    warrant = None
    if 'warrant' in payload:
        w = _record(payload['warrant'], 'warrant', ('status', 'authority_ids'))
        if 'status' not in w:
            _fail('invalid_warrant', 'warrant requires status')
        warrant = {'status': _label(w['status'], 'warrant', WARRANT_STATUSES),
                   'authority_ids': _refs(w.get('authority_ids', []), 'warrant', known)}

    exceptions = []
    for e in _list(payload.get('exceptions', []), 'exceptions', MAX_EXCEPTIONS):
        e = _record(e, 'exceptions', ('name', 'asserted_by', 'authority_ids'))
        if 'name' not in e or 'asserted_by' not in e:
            _fail('invalid_exceptions', 'exceptions entries require name and asserted_by')
        exceptions.append({'name': _label(e['name'], 'exceptions', EXCEPTIONS),
                           'asserted_by': _label(e['asserted_by'], 'exceptions', ASSERTED_BY),
                           'authority_ids': _refs(e.get('authority_ids', []), 'exceptions', known)})

    scope = []
    for item in _list(payload.get('scope_items', []), 'scope_items', MAX_SCOPE):
        item = _record(item, 'scope_items', ('item', 'limit_source'))
        if set(item) != {'item', 'limit_source'}:
            _fail('invalid_scope_items', 'scope_items entries require item and limit_source')
        scope.append({'item': _text(item['item'], 'scope_items'),
                      'limit_source': _label(item['limit_source'], 'scope_items', LIMIT_SOURCES)})

    questions = []
    for q in _list(payload.get('suppression_questions', []), 'suppression_questions', MAX_QUESTIONS):
        q = _record(q, 'suppression_questions', ('question', 'authority_ids'))
        if 'question' not in q:
            _fail('invalid_suppression_questions', 'suppression_questions entries require question')
        questions.append({'question': _text(q['question'], 'suppression_questions'),
                          'authority_ids': _refs(q.get('authority_ids', []), 'suppression_questions', known)})

    facts = []
    for f in _list(payload.get('sourced_facts', []), 'sourced_facts', MAX_FACTS):
        f = _record(f, 'sourced_facts', ('text', 'source_ids'))
        if set(f) != {'text', 'source_ids'}:
            _fail('invalid_sourced_facts', 'sourced_facts entries require text and source_ids')
        refs = _refs(f['source_ids'], 'sourced_facts', known)
        if not refs:
            _fail('invalid_sourced_facts', 'sourced_facts entries require at least one source')
        facts.append({'text': _text(f['text'], 'sourced_facts'), 'source_ids': refs})
    assertions = [_text(a, 'assertions')
                  for a in _list(payload.get('assertions', []), 'assertions', MAX_ASSERTIONS)]

    undeclared = []
    if standing is None:
        undeclared.append('standing')
    if warrant is None:
        undeclared.append('warrant')
    if not exceptions:
        undeclared.append('exception')
    if not scope:
        undeclared.append('scope')
    if not questions:
        undeclared.append('suppression')
    unlinked = []
    if warrant is not None and warrant['status'] in ('requested', 'issued') and not warrant['authority_ids']:
        unlinked.append('warrant')
    unlinked += [f"exception:{e['name']}" for e in exceptions if not e['authority_ids']]
    unlinked += [f'suppression_question:{i + 1}' for i, q in enumerate(questions) if not q['authority_ids']]
    blocked = bool(undeclared or unlinked or stale or conduct['actor'] != 'government')
    return {
        'status': 'declared_bookkeeping_only', 'row': 1264, 'matter_id': matter,
        'jurisdiction': jurisdiction, 'as_of': as_of_text,
        'conduct': conduct, 'standing': standing, 'warrant': warrant, 'exceptions': exceptions,
        'scope_items': scope, 'suppression_questions': questions,
        'sourced_facts': facts, 'user_assertions': assertions, 'authorities': authorities,
        'government_actor_declared': conduct['actor'] == 'government',
        'open_elements': undeclared, 'needs_authority_link': unlinked, 'stale_authority_ids': stale,
        'review_state': 'incomplete' if blocked else 'counsel_review_required',
        'legal_conclusion': None, 'reasonableness_decided': False, 'suppression_decided': False,
        'authority_independently_verified': False, 'filing_or_external_effect': False,
        'requires_licensed_counsel': True, 'boundary': BOUNDARY,
    }
