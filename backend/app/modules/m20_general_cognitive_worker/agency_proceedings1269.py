"""Bounded caller-declared agency record bookkeeping. No legal conclusions/I/O."""
from copy import deepcopy
from datetime import date
import re
import unicodedata
from urllib.parse import urlsplit

BOUNDARY = 'Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.'


class AgencyProceedingsError(ValueError):
    """Exact row-tagged refusal, with no input echo."""


def refuse(code):
    raise AgencyProceedingsError('AGENCY1269:' + code)


def text(value):
    if type(value) is not str or not value or len(value) > 2048 or value != value.strip() or any(unicodedata.category(c) in {'Cc','Cf','Zl','Zp'} for c in value):
        refuse('TEXT')
    return value


def shape(value, keys):
    if type(value) is not dict or len(value) != len(keys):
        refuse('SCHEMA')
    if any(type(key) is not str for key in value):
        refuse('SCHEMA')
    if set(value) != set(keys):
        refuse('SCHEMA')
    return value


def sequence(value, minimum=0):
    if type(value) is not list or not minimum <= len(value) <= 128:
        refuse('BOUND')
    return value


def day(value):
    if type(value) is not str or len(value) != 10 or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        refuse('DATE')
    try:
        return date.fromisoformat(value)
    except ValueError:
        refuse('DATE')


def refs(value, available, code):
    sequence(value, 1)
    for item in value:
        text(item)
    if len(set(value)) != len(value):
        refuse('REFS')
    if any(item not in available for item in value):
        refuse(code)


def keyed(items, fields):
    sequence(items)
    keys = set()
    for item in items:
        shape(item, fields)
        key = text(item['key'])
        if key in keys:
            refuse('DUPLICATE')
        keys.add(key)
    return keys


def organize(payload):
    """Validate all declarations, then index record links and flag review issues."""
    shape(payload, ['jurisdiction','as_of','sources','tribunal','records','pleadings',
                    'hearings','exhaustion','assertions','analysis'])
    jurisdiction = text(payload['jurisdiction'])
    as_of = day(payload['as_of'])
    sequence(payload['sources'], 1)
    sources = keyed(payload['sources'], ['key','citation','jurisdiction','checked_on','url'])
    mismatch, stale = [], []
    for source in payload['sources']:
        text(source['citation']);text(source['jurisdiction']);text(source['url'])
        try:
            url = urlsplit(source['url'])
            valid = url.scheme == 'https' and bool(url.hostname) and url.username is None and url.password is None
        except ValueError:
            valid = False
        if not valid:
            refuse('URL')
        checked = day(source['checked_on'])
        if checked > as_of:
            refuse('FUTURE_SOURCE')
        if checked < as_of:
            stale.append(source['key'])
        if source['jurisdiction'] != jurisdiction:
            mismatch.append(source['key'])
    shape(payload['tribunal'], ['label','source_keys'])
    text(payload['tribunal']['label'])
    refs(payload['tribunal']['source_keys'], sources, 'SOURCE_REF')
    records = keyed(payload['records'], ['key','text','source_keys'])
    for record in payload['records']:
        text(record['text']);refs(record['source_keys'], sources, 'SOURCE_REF')
    keyed(payload['pleadings'], ['key','text','record_keys','source_keys'])
    keyed(payload['hearings'], ['key','on','text','record_keys','source_keys'])
    usage = {record['key']: [] for record in payload['records']}
    future = []
    for kind in ['pleadings','hearings']:
        for item in payload[kind]:
            text(item['text'])
            refs(item['source_keys'], sources, 'SOURCE_REF')
            refs(item['record_keys'], records, 'RECORD_REF')
            if kind == 'hearings' and day(item['on']) > as_of:
                future.append(item['key'])
            for key in item['record_keys']:
                usage[key].append(item['key'])
    keyed(payload['exhaustion'], ['key','state','text','source_keys'])
    unknown = []
    for item in payload['exhaustion']:
        text(item['text']);refs(item['source_keys'], sources, 'SOURCE_REF')
        if type(item['state']) is not str or len(item['state']) > 2048 or item['state'] not in {'declared_done','declared_pending','unknown'}:
            refuse('STATE')
        if item['state'] == 'unknown':
            unknown.append(item['key'])
    for assertion in sequence(payload['assertions']):
        text(assertion)
    for analysis in sequence(payload['analysis']):
        shape(analysis, ['text','source_keys'])
        text(analysis['text']);refs(analysis['source_keys'], sources, 'SOURCE_REF')
    return dict(row_id=1269, status='needs_review' if mismatch or stale or future else 'review_required',
        counts={'sources':len(sources),'records':len(records),'pleadings':len(payload['pleadings']),
                'hearings':len(payload['hearings']),'exhaustion_steps':len(payload['exhaustion'])},
        record_usage=usage, unreferenced_record_keys=[key for key,items in usage.items() if not items],
        unknown_exhaustion_steps=unknown, jurisdiction_mismatches=mismatch,
        stale_source_keys=stale, future_hearing_keys=future, supplied=deepcopy(payload),
        evidence_status='caller_supplied_unverified', authority_verified=False,
        exhaustion_decision=None, external_effect=False, requires_counsel_review=True,
        boundary=BOUNDARY)
