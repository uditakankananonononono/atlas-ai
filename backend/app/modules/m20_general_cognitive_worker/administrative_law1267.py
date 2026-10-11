"""Row 1267: declared administrative-law review bookkeeping, no legal analysis.

Offline, stateless, stdlib-only. Supplied text and authority references are data;
they do not authorize actions or establish truth, currency or legal relevance.
"""
from copy import deepcopy
from datetime import date
from urllib.parse import urlsplit
from unicodedata import category

DOMAINS = ('delegation', 'procedure', 'record', 'deference', 'remedy')
DISCLAIMER = 'Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.'
MAX_ITEMS = 200
MAX_TEXT = 4000


def _refuse(code):
    raise ValueError('ADMINI1267:' + code)


def _object(value, required, optional=()):
    if type(value) is not dict:
        _refuse('SCHEMA')
    if len(value) > len(required) + len(optional):
        _refuse('SCHEMA')
    for key in value:
        _text(key)
    if not set(required) <= set(value) or set(value) - set(required) - set(optional):
        _refuse('SCHEMA')
    return value


def _text(value):
    if type(value) is not str or len(value) > MAX_TEXT:
        _refuse('TEXT')
    if any(category(char) in {'Cc', 'Cf', 'Zl', 'Zp'} for char in value):
        _refuse('TEXT')
    if not value.strip():
        _refuse('TEXT')
    return value.strip()


def _date(value):
    if type(value) is not str:
        _refuse('DATE')
    if len(value) != 10:
        _refuse('DATE')
    # Dates are a fixed-format scalar: malformed/control input maps to DATE.
    if any((char not in '0123456789' if index not in (4, 7) else char != '-')
           for index, char in enumerate(value)):
        _refuse('DATE')
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _refuse('DATE')
    if parsed.isoformat() != value:
        _refuse('DATE')
    return parsed


def _list(value):
    if type(value) is not list or len(value) > MAX_ITEMS:
        _refuse('COLLECTION')
    return value


def _url(value):
    value = _text(value)
    try:
        parsed = urlsplit(value)
        port = parsed.port
        valid = (parsed.scheme == 'https' and parsed.hostname and not parsed.username
                 and not parsed.password and not parsed.query and not parsed.fragment
                 and not any(c.isspace() or ord(c) < 32 for c in value)
                 and port in (None, 443))
    except ValueError:
        valid = False
    if not valid:
        _refuse('SOURCE_URL')
    return value


def _refs(value):
    result = [_text(item) for item in _list(value)]
    if len(set(result)) != len(result):
        _refuse('DUPLICATE_REF')
    return result


def build_review(data):
    """Validate and organize caller declarations; no external truth checks.

    Refuses malformed schemas, dates, URLs and reference graphs. Gaps reflect
    exact supplied date/jurisdiction comparisons, not legal deficiencies.
    """
    required = ('jurisdiction', 'as_of', 'provenance', 'authorities', 'issues')
    optional = ('sourced_facts', 'assertions', 'analysis')
    _object(data, required, optional)
    jurisdiction = _text(data['jurisdiction'])
    as_of = _date(data['as_of'])
    packet = _object(data['provenance'], ('source_label', 'observed_on'))
    provenance = {'source_label': _text(packet['source_label']), 'observed_on': packet['observed_on']}
    if _date(packet['observed_on']) > as_of:
        _refuse('FUTURE_PROVENANCE')
    collections = {name: _list(data.get(name, [])) for name in ('authorities', 'sourced_facts', 'assertions', 'analysis', 'issues')}
    if not collections['authorities']:
        _refuse('AUTHORITY_REQUIRED')
    seen = set()
    supplied = {name: [] for name in collections if name != 'issues'}
    namespaces = {name: set() for name in supplied}
    gaps = []

    def identify(item):
        identifier = _text(item['id'])
        if identifier in seen:
            _refuse('DUPLICATE_ID')
        seen.add(identifier)
        return identifier

    for raw in collections['authorities']:
        keys = ('id', 'title', 'citation', 'source_url', 'jurisdiction', 'effective_on', 'checked_on', 'valid_through')
        _object(raw, keys)
        item = {key: _text(raw[key]) for key in ('title', 'citation', 'jurisdiction')}
        item['id'] = identify(raw)
        item['source_url'] = _url(raw['source_url'])
        effective, checked, end = (_date(raw[key]) for key in ('effective_on', 'checked_on', 'valid_through'))
        if checked > as_of:
            _refuse('FUTURE_PROVENANCE')
        if end < effective:
            _refuse('DATE_ORDER')
        item.update({key: raw[key] for key in ('effective_on', 'checked_on', 'valid_through')})
        item['independently_verified'] = False
        for condition, code in ((item['jurisdiction'] != jurisdiction, 'jurisdiction_mismatch'),
                                (end < as_of, 'declared_expired'),
                                (checked < as_of, 'not_checked_as_of'),
                                (effective > as_of, 'not_yet_effective')):
            if condition:
                gaps.append({'code': code, 'authority_id': item['id']})
        namespaces['authorities'].add(item['id'])
        supplied['authorities'].append(item)

    for name in ('sourced_facts', 'assertions', 'analysis'):
        refs = {'sourced_facts': ('authority_refs',), 'assertions': (),
                'analysis': ('authority_refs', 'fact_refs', 'assertion_refs')}[name]
        for raw in collections[name]:
            _object(raw, ('id', 'text') + refs)
            item = {'id': identify(raw), 'text': _text(raw['text'])}
            item.update({key: _refs(raw[key]) for key in refs})
            if name == 'sourced_facts' and not item['authority_refs']:
                _refuse('FACT_SOURCE_REQUIRED')
            item['status'] = {'sourced_facts': 'supplied_reference_linked_unverified',
                              'assertions': 'caller_assertion_unverified',
                              'analysis': 'caller_analysis_unverified'}[name]
            namespaces[name].add(item['id'])
            supplied[name].append(item)

    domain_map = {domain: [] for domain in DOMAINS}
    ref_names = {'authority_refs': 'authorities', 'fact_refs': 'sourced_facts',
                 'assertion_refs': 'assertions', 'analysis_refs': 'analysis'}

    def validate_refs(item):
        for field, namespace in ref_names.items():
            if field in item and any(ref not in namespaces[namespace] for ref in item[field]):
                _refuse('UNKNOWN_REF')

    for name in ('sourced_facts', 'analysis'):
        for item in supplied[name]:
            validate_refs(item)
    for raw in collections['issues']:
        _object(raw, ('id', 'domain', 'question') + tuple(ref_names))
        item = {'id': identify(raw), 'domain': _text(raw['domain']), 'question': _text(raw['question'])}
        if item['domain'] not in DOMAINS:
            _refuse('DOMAIN')
        item.update({field: _refs(raw[field]) for field in ref_names})
        validate_refs(item)
        if not item['authority_refs']:
            gaps.append({'code': 'issue_without_supplied_authority', 'issue_id': item['id']})
        item['status'] = 'declared_question_for_counsel_review'
        domain_map[item['domain']].append(item)
    for domain in DOMAINS:
        if not domain_map[domain]:
            gaps.append({'code': 'missing_declared_domain', 'domain': domain})
    return deepcopy({
        'feature_id': 1267, 'status': 'declared_administrative_bookkeeping_only',
        'jurisdiction': jurisdiction, 'as_of': as_of.isoformat(), 'provenance': provenance,
        'supplied_material': supplied, 'domain_map': domain_map, 'gaps': gaps,
        'counts': {name: len(items) for name, items in collections.items()},
        'review_state': 'declared_gaps_require_counsel_review' if gaps else 'counsel_review_required',
        'evidence_verified': False, 'named_legal_capability_executed': False,
        'legal_conclusion': None, 'external_effect': False,
        'requires_licensed_counsel': True, 'disclaimer': DISCLAIMER,
    })
