"""Conservative transcription of explicit source statements, not prediction.

No model, score, inferred eligibility or invented timezone. Source text is data:
script/style content is excluded before transcription by adapters.
"""
from __future__ import annotations

from datetime import datetime
import re
import unicodedata

_CUE = r'(?:application deadline|deadline|apply by|(?:applications?|submissions?) (?:close|due)(?: by)?)'
_MONTH = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?'
_CALENDAR = r'(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|' + _MONTH + r'\s+[0-9]{1,2}(?:st|nd|rd|th)?,?\s+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+' + _MONTH + r'\s+[0-9]{4})'
_DATE = r'(?:[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[Tt][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?(?:[Zz]|[+-][0-9]{2}:?[0-9]{2})?)?|' + _CALENDAR + r')'
_DEADLINE = re.compile(r'\b' + _CUE + r'\s*[:\-]?\s*(?:(?:on|is)\s+)?(?P<date>' + _DATE + r')(?![A-Za-z0-9:+-])', re.I)
_ELIGIBILITY = re.compile(r'(?:^|(?<=[.!?\n]))\s*(?:Eligibility\s*:|Requirements\s*:|Eligible applicants\b|Applicants must\s*:?|Students must\b|Must (?:be|have)\b|Only [A-Za-z ]+ (?:may|can) apply\b|Restricted to\b|Not open to\b|Open (?:only )?to\b|Minimum GPA\s*[:0-9]|Age limit\s*:|Citizenship required\b|GPA must be\b|Available to (?:(?:international|undergraduate|graduate|high school) )?students\b)', re.I)


def deadline_evidence(text: str) -> dict:
    result = {'value': None, 'timezone': None, 'precision': 'unknown', 'evidence': [], 'unknowns': []}
    if len(text) > 100000:
        result['unknowns'].append('deadline_input_limit_exceeded')
        return result
    if re.search(r'\b(?:archived|expired listing|last year|applications?[^\n.!?]{0,80}closed)\b', text, re.I):
        result['unknowns'].extend(['historical_or_closed_listing', 'qualified_or_negated_deadline'])
        return result
    candidates = []
    matches = list(_DEADLINE.finditer(text))
    if len(matches) > 256:
        result['unknowns'].append('deadline_input_limit_exceeded')
        return result
    previous_end = 0
    for index, match in enumerate(matches):
        raw = match['date']
        prefix_start = max(previous_end, match.start() - 2048)
        prefix_window = text[prefix_start:match.start()]
        prefix = re.split(r'[.!?;]', prefix_window)[-1].strip()
        if re.search(r'\b(?:no|not(?: the)?|never)[\s.!?;]*$', prefix_window, re.I) or any(unicodedata.category(ch).startswith('S') for ch in prefix_window):
            result['evidence'].append(match.group(0))
            result['unknowns'].append('qualified_or_negated_deadline')
            continue
        previous_end = match.end()
        qualifier_words = re.findall(r'[^\W\d_]+', prefix.casefold(), re.UNICODE)
        if any(word not in {'the', 'application', 'submission', 'applications', 'submissions'} for word in qualifier_words):
            result['evidence'].append(match.group(0))
            result['unknowns'].append('qualified_or_negated_deadline')
            continue
        end = matches[index+1].start() if index+1 < len(matches) else len(text)
        tail = text[match.end():end]
        result['evidence'].append(text[match.start():end].strip())
        # Any additional calendar date, partial date or extension conflicts.
        if re.search(_CALENDAR, tail, re.I) or re.search(r'(?:/|to|through|until|extended)\s*(?:[0-9]{1,2}-[0-9]{1,2}|[A-Za-z]{3,9}\s+[0-9]{1,2}|[0-9]{1,2}\s+[A-Za-z]{3,9})', tail, re.I):
            result['unknowns'].append('conflicting_deadline_statements')
            continue
        if re.search(r'\b(?:provisional|obsolete|unconfirmed|draft|not final|subject to change|may change|tentative|cancelled|canceled|superseded|no longer|withdrawn)\b', tail, re.I):
            result['unknowns'].append('deadline_caveat_unresolved')
            continue
        # Explicit unrelated field boundaries preserve mixed-prose cards;
        # unmarked suffix prose still abstains. Conflicts were checked first.
        tail = re.split(r'(?:[.!?]\s+|\n+)(?=(?:Award|Prize|Eligibility|Eligible applicants|Who can apply|Applicants must|Open to|Posted|Location)\b)', tail, maxsplit=1, flags=re.I)[0]
        # No word-list guessing: unexplained suffix tokens always stay unknown,
        # including across line/sentence breaks. Punctuation alone is harmless.
        if any(not (ch.isspace() or unicodedata.category(ch).startswith('P')) for ch in tail):
            result['unknowns'].append('unsupported_deadline_time_or_timezone')
            continue
        try:
            if re.match(r'[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt]', raw):
                fraction = re.search(r'\.([0-9]+)', raw)
                if fraction and len(fraction[1]) > 6:
                    result['unknowns'].append('unsupported_deadline_fraction_precision')
                    continue
                offset = re.search(r'([+-])([0-9]{2}):?([0-9]{2})$', raw)
                if offset and (int(offset[2]) > 14 or int(offset[3]) >= 60 or (int(offset[2]) == 14 and int(offset[3]) != 0)):
                    result['unknowns'].append('invalid_deadline_timezone_offset')
                    continue
                dt = datetime.fromisoformat(raw.upper().replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    result['unknowns'].append('deadline_timezone_not_stated')
                    continue
                candidates.append((dt.isoformat(), str(dt.tzinfo), 'instant'))
            else:
                normalized = re.sub(r'\bSept\b\.?' , 'Sep', raw, flags=re.I)
                normalized = re.sub(r'\bSep\.', 'Sep', normalized, flags=re.I)
                normalized = re.sub(r'(?<=[0-9])(?:st|nd|rd|th)\b', '', normalized, flags=re.I)
                normalized = re.sub(r'(?<=[A-Za-z])\.(?=\s)', '', normalized)
                normalized = re.sub(r'\s+', ' ', normalized)
                value = None
                for fmt in ('%Y-%m-%d', '%B %d, %Y', '%B %d %Y', '%b %d, %Y', '%b %d %Y', '%d %B %Y', '%d %b %Y'):
                    try:
                        value = datetime.strptime(normalized, fmt).date().isoformat()
                        break
                    except ValueError:
                        pass
                if value is None: raise ValueError('invalid date')
                candidates.append((value, None, 'date'))
        except ValueError:
            result['unknowns'].append('invalid_deadline_date')
    unique = set(candidates)
    if len(unique) == 1 and not result['unknowns']:
        result['value'], result['timezone'], result['precision'] = unique.pop()
        if result['precision'] == 'date':
            result['unknowns'].extend(['deadline_time_not_stated', 'deadline_timezone_not_stated'])
    elif len(unique) > 1:
        result['unknowns'].append('conflicting_deadline_statements')
    if not matches and re.search(r'\b' + _CUE + r'\b', text, re.I):
        result['unknowns'].append('unsupported_deadline_format')
    if result['value'] is None and not result['unknowns']:
        result['unknowns'].append('deadline_not_stated_in_listing')
    result['unknowns'] = list(dict.fromkeys(result['unknowns']))
    return result


def evidence_card(row: dict, *, fetched_at: str, content_sha256: str) -> dict:
    text = f"{row['title']}\n{row.get('evidence_text', row.get('description', ''))}"
    title_risk = re.search(r'\b(?:no deadline|previous deadline|expired|archived|applications? closed)\b', row['title'], re.I)
    deadline = deadline_evidence(row.get('evidence_text', row.get('description', '')))
    if not deadline['evidence'] and not deadline['value']:
        title_deadline = deadline_evidence(row['title'])
        if title_deadline['evidence'] or title_deadline['value']:
            deadline = title_deadline
    if title_risk:
        deadline = {'value': None, 'timezone': None, 'precision': 'unknown', 'evidence': deadline['evidence'], 'unknowns': ['qualified_or_negated_deadline']}
    statements = []
    contexts = []
    truncated = False
    boundary_unknown = False
    for match in _ELIGIBILITY.finditer(text):
        context = text[match.start():].strip()
        if re.match(r'(?:Open to (?:interpretation|discussion)|Applicants must (?:click|visit|read)|Eligibility: (?:not specified|unknown|not stated))\b', context, re.I):
            continue
        # Join label-only line with the following source value, not later fields.
        context = re.sub(r'^([^\n:]+:)\s*\n\s*', r'\1 ', context)
        contexts.append(context[:600])
        truncated = truncated or len(context) > 600
        protected = re.sub(r'\b[A-Z]\.(?=\s+[A-Z][a-z])|\b(?:[A-Za-z]\.){2,}|\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr)\.', lambda m: m[0].replace('.', '\x00'), context, flags=re.I)
        sentence = re.split(r'(?<=[.!?])\s+|\n', protected, maxsplit=1)[0].replace('\x00', '.')
        boundary_unknown = boundary_unknown or len(sentence) < len(context)
        statements.append(sentence[:600])
    statements.extend(row.get('eligibility_statements', []))
    unknowns = ['personal_eligibility_not_evaluated', 'entry_cost_not_verified', 'detail_page_not_fetched']
    if not statements:
        unknowns.append('eligibility_not_found_by_supported_cues')
    if boundary_unknown:
        unknowns.append('eligibility_context_boundary_unknown')
    if truncated:
        unknowns.append('eligibility_evidence_truncated')
    unknowns.extend(row.get('source_unknowns', []))
    unknowns.extend(deadline['unknowns'])
    output = {key: value for key, value in row.items() if key != 'evidence_text'}
    if 'evidence_text' in row:
        output['description_original_length'] = len(row['evidence_text'])
        output['description_truncated'] = len(row['evidence_text']) > 600
        output['description'] = row['evidence_text'][:600]
    return dict(output, fetched_at=fetched_at, content_sha256=content_sha256,
                deadline=deadline, eligibility={'evidence': list(dict.fromkeys(statements)),
                                               'verdict': None, 'basis': 'source_statements_only',
                                               'source_context': contexts[0] if contexts else None,
                                               'source_contexts': contexts},
                unknowns=unknowns, evidence_status='public_listing_only')
