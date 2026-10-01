"""Conservative transcription of explicit source statements, not prediction.

No model, score, inferred eligibility or invented timezone. Source text is data:
script/style content is excluded before transcription by adapters.
"""
from __future__ import annotations

from datetime import datetime
import re

_CUE = r'(?:application deadline|deadline|apply by|applications? (?:close|due))'
_CALENDAR = r'(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?\.?|Oct|Nov|Dec) [0-9]{1,2},? [0-9]{4})'
_DATE = r'(?:[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[Tt][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?(?:[Zz]|[+-][0-9]{2}:?[0-9]{2})?)?|' + _CALENDAR + r')'
_DEADLINE = re.compile(r'\b' + _CUE + r'\s*[:\-]?\s*(?P<date>' + _DATE + r')(?![A-Za-z0-9:+-])', re.I)
_ELIGIBILITY = re.compile(r'(?:^|(?<=[.!?\n]))\s*(?:Eligibility|Eligible applicants|Who can apply|Applicants must|You must|Open to)\b', re.I)


def deadline_evidence(text: str) -> dict:
    result = {'value': None, 'timezone': None, 'precision': 'unknown', 'evidence': [], 'unknowns': []}
    candidates = []
    matches = list(_DEADLINE.finditer(text))
    for index, match in enumerate(matches):
        raw = match['date']
        end = matches[index+1].start() if index+1 < len(matches) else len(text)
        tail = text[match.end():end]
        result['evidence'].append(text[match.start():end].strip())
        # Any additional calendar date, partial date or extension conflicts.
        if re.search(_CALENDAR, tail, re.I) or re.search(r'(?:/|to|through|until|extended)\s*(?:[0-9]{1,2}-[0-9]{1,2}|[A-Za-z]{3,9}\s+[0-9]{1,2}|[0-9]{1,2}\s+[A-Za-z]{3,9})', tail, re.I):
            result['unknowns'].append('conflicting_deadline_statements')
            continue
        # No word-list guessing: unexplained suffix tokens always stay unknown,
        # including across line/sentence breaks. Punctuation alone is harmless.
        if re.search(r'[\w+\-]', tail, re.UNICODE):
            result['unknowns'].append('unsupported_deadline_time_or_timezone')
            continue
        try:
            if re.match(r'[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt]', raw):
                fraction = re.search(r'\.([0-9]+)', raw)
                if fraction and len(fraction[1]) > 6:
                    result['unknowns'].append('unsupported_deadline_fraction_precision')
                    continue
                dt = datetime.fromisoformat(raw.upper().replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    result['unknowns'].append('deadline_timezone_not_stated')
                    continue
                candidates.append((dt.isoformat(), str(dt.tzinfo), 'instant'))
            else:
                normalized = re.sub(r'\bSept\b\.?' , 'Sep', raw, flags=re.I)
                normalized = re.sub(r'\bSep\.', 'Sep', normalized, flags=re.I)
                value = None
                for fmt in ('%Y-%m-%d', '%B %d, %Y', '%B %d %Y', '%b %d, %Y', '%b %d %Y'):
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
    text = f"{row['title']}\n{row.get('description', '')}"
    deadline = deadline_evidence(text)
    statements = []
    contexts = []
    truncated = False
    boundary_unknown = False
    for match in _ELIGIBILITY.finditer(text):
        context = text[match.start():].strip()
        contexts.append(context[:600])
        truncated = truncated or len(context) > 600
        protected = re.sub(r'\b(?:[A-Za-z]\.){2,}|\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr)\.', lambda m: m[0].replace('.', '\x00'), context, flags=re.I)
        sentence = re.split(r'(?<=[.!?])\s+|\n', protected, maxsplit=1)[0].replace('\x00', '.')
        boundary_unknown = boundary_unknown or len(sentence) < len(context)
        statements.append(sentence[:600])
    statements.extend(row.get('eligibility_statements', []))
    unknowns = ['personal_eligibility_not_evaluated', 'entry_cost_not_verified', 'detail_page_not_fetched']
    if not statements:
        unknowns.append('eligibility_not_stated_in_listing')
    if boundary_unknown:
        unknowns.append('eligibility_context_boundary_unknown')
    if truncated:
        unknowns.append('eligibility_evidence_truncated')
    unknowns.extend(row.get('source_unknowns', []))
    unknowns.extend(deadline['unknowns'])
    return dict(row, fetched_at=fetched_at, content_sha256=content_sha256,
                deadline=deadline, eligibility={'evidence': list(dict.fromkeys(statements)),
                                               'verdict': None, 'basis': 'source_statements_only',
                                               'source_context': contexts[0] if contexts else None,
                                               'source_contexts': contexts},
                unknowns=unknowns, evidence_status='public_listing_only')
