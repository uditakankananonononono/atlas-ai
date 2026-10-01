"""Conservative transcription of explicit source statements, not prediction.

No model, score, inferred eligibility or invented timezone. Source text is data:
script/style content is excluded before transcription by adapters.
"""
from __future__ import annotations

from datetime import datetime
import re

_CUE = r'(?:application deadline|deadline|apply by|applications? (?:close|due))'
_DATE = r'(?:\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)?|(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec) \d{1,2},? \d{4})'
_DEADLINE = re.compile(r'\b' + _CUE + r'\s*[:\-]?\s*(?P<date>' + _DATE + r')', re.I)
_ELIGIBILITY = re.compile(r'(?:^|(?<=[.!?\n]))\s*((?:Eligibility|Eligible applicants|Who can apply|Applicants must|You must|Open to)\b[^\n.!?]*(?:[.!?]|$))', re.I)


def deadline_evidence(text: str) -> dict:
    result = {'value': None, 'timezone': None, 'precision': 'unknown', 'evidence': [], 'unknowns': []}
    candidates = []
    for match in _DEADLINE.finditer(text):
        raw = match['date']
        tail = text[match.end():match.end() + 60]
        statement = match.group(0).strip()
        result['evidence'].append(statement)
        # A range, a second deadline, a locale-specific time or unspecified clock
        # time cannot safely be turned into a single instant/date.
        if re.match(r'\s*(?:to\b|through\b|until\b|[-–]|at\b|\d{1,2}:|(?:UTC|GMT|EST|EDT|PST|PDT|IST)\b)', tail, re.I):
            result['unknowns'].append('unsupported_deadline_time_or_range')
            continue
        try:
            if 'T' in raw:
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    result['unknowns'].append('deadline_timezone_not_stated')
                    continue
                candidates.append((dt.isoformat(), str(dt.tzinfo), 'instant'))
            else:
                value = None
                for fmt in ('%Y-%m-%d', '%B %d, %Y', '%B %d %Y', '%b %d, %Y', '%b %d %Y'):
                    try:
                        value = datetime.strptime(raw, fmt).date().isoformat()
                        break
                    except ValueError:
                        pass
                if value is None:
                    raise ValueError('invalid date')
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
    if result['value'] is None and not result['unknowns']:
        result['unknowns'].append('deadline_not_stated_in_listing')
    return result


def evidence_card(row: dict, *, fetched_at: str, content_sha256: str) -> dict:
    text = f"{row['title']}\n{row.get('description', '')}"
    deadline = deadline_evidence(text)
    statements = [match[1].strip() for match in _ELIGIBILITY.finditer(text)]
    statements.extend(row.get('eligibility_statements', []))
    unknowns = ['personal_eligibility_not_evaluated', 'entry_cost_not_verified', 'detail_page_not_fetched']
    if not statements:
        unknowns.append('eligibility_not_stated_in_listing')
    unknowns.extend(deadline['unknowns'])
    return dict(row, fetched_at=fetched_at, content_sha256=content_sha256,
                deadline=deadline, eligibility={'evidence': list(dict.fromkeys(statements)),
                                               'verdict': None, 'basis': 'source_statements_only'},
                unknowns=unknowns, evidence_status='public_listing_only')
