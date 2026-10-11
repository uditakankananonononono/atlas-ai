"""S4.1 / c35.sweep - competition sweeper dossier builder (PARKED).

Extracts deadline, fee and eligibility per supplied source and assembles
verbatim dossier sections (rules, past winners, judging criteria) with
source id and char offset, purely offline over supplied text. No fetching,
no login, no apply/submit, no ranking/EV (S4.5), no link indexing or
waiver templates (S4.2). run() always refuses while PARKED; the pure
builder build_dossiers() is the exercised surface.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.modules.c30 import policy

PREFIX = 'APPLY'


def _refuse(reason: str, field: str = '') -> str:
    return PREFIX + '_REFUSED_' + reason + (':' + field if field else '')
PARKED = True

MAX_SOURCES = 200
MAX_TOTAL_CHARS = 2_000_000
MAX_TEXT_CHARS = 200_000

SOURCE_KINDS = ('bookmark_doc', 'starred_mail', 'social_save', 'public_page',
                'private_third_party')
_TOP_KEYS = {'as_of', 'sources'}
_SOURCE_KEYS = {'id', 'kind', 'text', 'url'}

_SUBMIT_LIKE = re.compile(r'(submit|submission|apply|password|token)', re.IGNORECASE)
_ISO_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
_MONTH_DATE = re.compile(
    r'(?:January|February|March|April|May|June|July|August|September|'
    r'October|November|December)\s+\d{1,2},\s+\d{4}')
_FEE_FREE = re.compile(r'\bfree\b', re.IGNORECASE)
_FEE_MONEY = re.compile(r'(?:USD|EUR|GBP)\s*\d+(?:\.\d{2})?|\$\s*\d+(?:\.\d{2})?')
_ELIGIBILITY = re.compile(
    r'\b(?:grades?|ages?|years old|country|citizen|resident)\b', re.IGNORECASE)
_RULES = re.compile(r'\b(?:rules?|requirements?|must)\b', re.IGNORECASE)
_WINNERS = re.compile(r'\b(?:winners?|won|laureate|champion)\b', re.IGNORECASE)
_JUDGING = re.compile(
    r'\b(?:judging|judged|criteria|rubric|scored|scoring)\b', re.IGNORECASE)

_SECTIONS = (('rules', _RULES), ('past_winners', _WINNERS),
             ('judging_criteria', _JUDGING))


def run(request) -> dict:
    raise ValueError(_refuse('PARKED'))


def _lines_with_offsets(text: str):
    lines = []
    offset = 0
    for line in text.splitlines(keepends=True):
        bare = line.rstrip('\r\n')
        lines.append((offset, bare))
        offset += len(line)
    return lines


def _fold(title: str) -> str:
    return ' '.join(title.split()).casefold()


def _parse_deadline(text: str):
    """Return (iso_or_None, flag_or_None). ISO candidate first, then the
    Month D, YYYY candidate; first matching candidate wins. A candidate
    that fails to parse yields deadline_unparsed; no candidate yields
    no_deadline."""
    m = _ISO_DATE.search(text)
    if m:
        try:
            return date.fromisoformat(m.group(0)).isoformat(), None
        except ValueError:
            return None, 'deadline_unparsed'
    m = _MONTH_DATE.search(text)
    if m:
        try:
            parsed = datetime.strptime(m.group(0), '%B %d, %Y').date()
            return parsed.isoformat(), None
        except ValueError:
            return None, 'deadline_unparsed'
    return None, 'no_deadline'


def _parse_fee(text: str):
    if _FEE_FREE.search(text):
        return 'free'
    m = _FEE_MONEY.search(text)
    return m.group(0) if m else None


def _checked_sources(request):
    if type(request) is not dict:
        raise ValueError(_refuse('BAD_TYPE', 'request'))
    for key in request:
        if type(key) is not str:
            raise ValueError(_refuse('BAD_TYPE', 'key'))
    for key in sorted(set(request) - _TOP_KEYS):
        raise ValueError(_refuse('UNKNOWN', key))
    as_of = request.get('as_of')
    as_of_ok = isinstance(as_of, str) and bool(
        re.fullmatch(r'\d{4}-\d{2}-\d{2}', as_of))
    if as_of_ok:
        try:
            date.fromisoformat(as_of)
        except ValueError:
            as_of_ok = False
    if not as_of_ok:
        raise ValueError(_refuse('BAD_TYPE', 'as_of'))
    sources = request.get('sources')
    if type(sources) is not list or not sources:
        raise ValueError(_refuse('NOSOURCE'))
    if len(sources) > MAX_SOURCES:
        raise ValueError(_refuse('OVERSIZE'))
    total = 0
    checked = []
    for s in sources:
        if type(s) is not dict:
            raise ValueError(_refuse('BAD_TYPE', 'source'))
        for key in s:
            if type(key) is not str:
                raise ValueError(_refuse('BAD_TYPE', 'key'))
        for key in s:
            if _SUBMIT_LIKE.search(str(key)):
                raise ValueError(_refuse('SUBMIT'))
        for key in sorted(set(s) - _SOURCE_KEYS):
            raise ValueError(_refuse('UNKNOWN', key))
        kind = s.get('kind')
        if kind not in SOURCE_KINDS:
            raise ValueError(_refuse('BAD_TYPE', 'kind'))
        if kind == 'private_third_party':
            raise ValueError(_refuse('PRIVATE'))
        sid = policy.clean_text(s.get('id'), PREFIX, 'id', 128)
        text = policy.clean_text(s.get('text'), PREFIX, 'text',
                                 MAX_TEXT_CHARS, allow_ws=True)
        url = s.get('url')
        if url is not None:
            url = policy.clean_text(url, PREFIX, 'url', 512)
        total += len(text)
        if total > MAX_TOTAL_CHARS:
            raise ValueError(_refuse('OVERSIZE'))
        checked.append({'id': sid, 'kind': kind, 'text': text, 'url': url})
    return as_of, checked


def build_dossiers(request) -> dict:
    as_of, sources = _checked_sources(request)
    merged = {}
    order = []
    for s in sources:
        lines = _lines_with_offsets(s['text'])
        title = ''
        for _, bare in lines:
            if bare.strip():
                title = bare.strip()
                break
        title = policy.clean_text(title, PREFIX, 'title', 200)
        deadline, flag = _parse_deadline(s['text'])
        key = (_fold(title), deadline or '')
        if key not in merged:
            merged[key] = {
                'title': title, 'deadline': deadline, 'fee': None,
                'flags': [], 'source_ids': [],
                'eligibility': [], 'rules': [], 'past_winners': [],
                'judging_criteria': [],
            }
            order.append(key)
        opp = merged[key]
        opp['source_ids'].append(s['id'])
        if flag:
            opp['flags'] = sorted(set(opp['flags']) | {flag})
        fee = _parse_fee(s['text'])
        if fee is not None and opp['fee'] is None:
            opp['fee'] = fee
        for offset, bare in lines:
            if _ELIGIBILITY.search(bare):
                opp['eligibility'].append(
                    {'source_id': s['id'], 'offset': offset, 'text': bare})
            for name, pattern in _SECTIONS:
                if pattern.search(bare):
                    opp[name].append(
                        {'source_id': s['id'], 'offset': offset, 'text': bare})
    opportunities = []
    for key in order:
        opp = merged[key]
        deadline = opp['deadline']
        if deadline is None:
            status = 'undated'
        elif deadline < as_of:
            status = 'expired'
        else:
            status = 'active'
        record = {
            'title': opp['title'], 'deadline': deadline, 'fee': opp['fee'],
            'flags': opp['flags'], 'source_ids': sorted(opp['source_ids']),
            'status': status,
        }
        for name in ('eligibility', 'rules', 'past_winners',
                     'judging_criteria'):
            record[name] = opp[name] if opp[name] else 'not_in_sources'
        opportunities.append(record)
    opportunities.sort(key=lambda o: (_fold(o['title']), o['deadline'] or ''))
    coverage = {
        'sources_supplied': len(sources),
        'with_deadline': sum(1 for o in opportunities
                             if o['deadline'] is not None),
        'with_fee': sum(1 for o in opportunities if o['fee'] is not None),
        'expired': sum(1 for o in opportunities if o['status'] == 'expired'),
    }
    return {
        'as_of': as_of,
        'parked': PARKED,
        'opportunities': opportunities,
        'coverage': coverage,
        'scope': policy.scope(
            ['supplied-source deadline/fee/eligibility extraction',
             'verbatim dossier sections with source id and char offset',
             'expiry vs as_of', 'dedupe merge by folded title + ISO deadline'],
            ['fetching', 'login', 'apply/submit',
             'ranking or EV scoring (S4.5)', 'link indexing (S4.2)',
             'waiver templates (S4.2)', 'live verification'],
            'supplied-text-only', as_of),
    }
