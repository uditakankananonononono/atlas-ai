"""Conservative transcription of explicit source statements, not prediction.

No model, score, inferred eligibility or invented timezone. Source text is data:
script/style content is excluded before transcription by adapters.

KNOWN LIMITS (2026-10-01): English finite grammar, not universal safety.
Titles "Tentative application date" / "Never apply" can leave an accepted date.
Newline/fullwidth-colon Contact and "Open to Contact:" forms can contaminate
eligibility excerpts. Verdict is always null; inspect retained source context.
Do not use this as autonomous application/eligibility/deadline authorization.
"""
from __future__ import annotations

from datetime import datetime
import re
import unicodedata
import json

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
    calendar_dates = list(re.finditer(_CALENDAR, text, re.I))
    if len(calendar_dates) > 1:
        result['unknowns'].append('conflicting_deadline_statements')
        return result
    previous_end = 0
    for index, match in enumerate(matches):
        raw = match['date']
        prefix_start = previous_end
        prefix_window = text[prefix_start:match.start()]
        prefix = prefix_window.strip()
        if re.search(r'\b(?:no|not|never)\b', prefix_window, re.I) or any((ch.isalpha() and not ch.isascii()) or unicodedata.category(ch).startswith('S') for ch in prefix_window):
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
        result['evidence'].append(text[match.start():end].strip()[:600])
        # Any additional calendar date, partial date or extension conflicts.
        if re.search(_CALENDAR, tail, re.I) or re.search(r'(?:/|to|through|until|extended)\s*(?:[0-9]{1,2}-[0-9]{1,2}|[A-Za-z]{3,9}\s+[0-9]{1,2}|[0-9]{1,2}\s+[A-Za-z]{3,9})', tail, re.I):
            result['unknowns'].append('conflicting_deadline_statements')
            continue
        if re.search(r'\b(?:provisional|obsolete|unconfirmed|draft|not final|subject to change|may change|tentative|cancelled|canceled|superseded|no longer|withdrawn)\b', tail, re.I):
            result['unknowns'].append('deadline_caveat_unresolved')
            continue
        # Explicit unrelated field boundaries preserve mixed-prose cards;
        # unmarked suffix prose still abstains. Conflicts were checked first.
        # No field-boundary cutting. Additional prose makes this non-standalone.
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
    if deadline['unknowns'] == ['deadline_not_stated_in_listing']:
        title_deadline = deadline_evidence(row['title'])
        if title_deadline['evidence'] or title_deadline['value']:
            deadline = title_deadline
    # A title with deadline-like vocabulary or unknown-script tokens is not a
    # safe generic heading. Preserve every earlier safety reason when abstaining.
    title_uncertain = (any(ch.isalpha() and not ch.isascii() for ch in row['title']) or
                       re.search(r'\b(?:no|not|invalid|deadline|previous|archived|expired|cancelled|canceled|withdrawn|obsolete)\b', row['title'], re.I))
    title_is_field = bool(_DEADLINE.fullmatch(row['title'].strip().rstrip('.')))
    if len(re.findall(_CALENDAR, text, re.I)) > 1:
        deadline['value'], deadline['timezone'], deadline['precision'] = None, None, 'unknown'
        deadline['unknowns'].append('conflicting_deadline_statements')
    if title_risk or (title_uncertain and not title_is_field):
        deadline['value'], deadline['timezone'], deadline['precision'] = None, None, 'unknown'
        deadline['unknowns'].append('title_context_unknown')
    deadline['unknowns'] = list(dict.fromkeys(deadline['unknowns']))
    statements = []
    contexts = []
    truncated = False
    boundary_unknown = False
    eligibility_limited = len(text) > 100000
    cue_matches = list(_ELIGIBILITY.finditer(text[:100001])) if not eligibility_limited else []
    if len(cue_matches) > 16:
        eligibility_limited = True
        cue_matches = []
    for index, match in enumerate(cue_matches):
        end = cue_matches[index+1].start() if index+1 < len(cue_matches) else len(text)
        context = text[match.start():end].strip()
        contexts.append(context[:600])
        truncated = truncated or len(context) > 600
        protected = re.sub(r'\b[A-Z]\.(?=\s+[A-Z][a-z])|\b(?:[A-Za-z]\.){2,}|\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr)\.', lambda m: m[0].replace('.', '\x00'), context[:601], flags=re.I)
        lines = protected.splitlines()
        first = lines[0].strip() if lines else ''
        if re.fullmatch(r'(?:Eligibility|Requirements|Applicants must|Open to)\s*:?', first, re.I):
            value = lines[1].strip() if len(lines) > 1 else ''
            if not value or re.match(r'[^:]{1,80}:', value):
                boundary_unknown = True
                continue
            first += ' ' + value
        sentence = re.split(r'(?<=[.!?])\s+', first, maxsplit=1)[0].replace('\x00', '.')
        if ':' in sentence and ':' in sentence.split(':', 1)[1]:
            continue
        # Evidence excerpts require explicit requirement-bearing vocabulary, not
        # merely a cue header or an invitation to inspect another page.
        if re.search(r'\b(?:unknown|not stated|not specified|see|website|brochure|click|download|guide|calculation|discussion|interpretation|preview|example|demo|save|fun|read|visit|quick|filters)\b', sentence, re.I):
            continue
        if not re.search(r'\b(?:students?|undergraduates?|graduates?|minors?|juniors?|seniors?|citizens?|citizenship|residents?|enrolled|GPA|age|aged|years?|18|doctoral|lab|full-time)\b', sentence, re.I):
            continue
        boundary_unknown = boundary_unknown or len(sentence) < len(context)
        statements.append(sentence[:600])
    statements.extend(row.get('eligibility_statements', []))
    unknowns = ['personal_eligibility_not_evaluated', 'entry_cost_not_verified', 'detail_page_not_fetched']
    if eligibility_limited:
        unknowns.append('eligibility_input_limit_exceeded')
    if not statements:
        unknowns.append('eligibility_not_found_by_supported_cues')
    if boundary_unknown:
        unknowns.append('eligibility_context_boundary_unknown')
    if truncated:
        unknowns.append('eligibility_evidence_truncated')
    unknowns.extend(row.get('source_unknowns', []))
    unknowns.extend(deadline['unknowns'])
    allowed = {'title','description','url','source_url','platform','opportunity_kind'}
    output = {key: value[:2048] if isinstance(value, str) else None for key, value in row.items() if key in allowed}
    if any(isinstance(value, str) and len(value) > 2048 for key, value in row.items() if key in {'url','source_url'}):
        unknowns.append('url_display_truncated_not_actionable')
    output['title_original_length'] = len(row['title'])
    output['title'] = row['title'][:300]
    output['title_truncated'] = len(row['title']) > 300
    output['description_original_length'] = len(row.get('evidence_text', row.get('description', '')))
    output['description'] = row.get('description', '')[:600]
    output['description_truncated'] = output['description_original_length'] > 600
    if 'evidence_text' in row:
        output['description_original_length'] = len(row['evidence_text'])
        output['description_truncated'] = len(row['evidence_text']) > 600
        output['description'] = row['evidence_text'][:600]
    card = dict(output, fetched_at=fetched_at, content_sha256=content_sha256,
                deadline=deadline, eligibility={'evidence': list(dict.fromkeys(statements)),
                                               'verdict': None, 'basis': 'source_statements_only',
                                               'source_context': text[cue_matches[0].start():cue_matches[0].start()+600].strip() if cue_matches else None,
                                               'source_contexts': contexts},
                unknowns=unknowns, evidence_status='public_listing_only')

    if len(json.dumps(card, ensure_ascii=True).encode()) > 20000:
        card['eligibility']['evidence'] = []
        card['eligibility']['source_context'] = None
        card['eligibility']['source_contexts'] = []
        card['deadline']['evidence'] = []
        card['deadline']['value'] = None
        card['unknowns'].append('card_output_limit_exceeded')
    if len(json.dumps(card, ensure_ascii=True).encode()) > 20000:
        # Last-resort small schema, never leak caller-supplied oversized fields.
        return {'title': output['title'][:300], 'platform': str(output.get('platform',''))[:80],
                'deadline': {'value': None, 'timezone': None, 'precision': 'unknown', 'evidence': [],
                             'unknowns': list(dict.fromkeys(deadline['unknowns'] + ['card_output_limit_exceeded']))},
                'eligibility': {'evidence': [], 'verdict': None, 'basis': 'output_limit'},
                'unknowns': ['card_output_limit_exceeded'], 'evidence_status': 'unavailable_output_limit'}
    return card
