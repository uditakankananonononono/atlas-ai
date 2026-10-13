"""Observed ChallengeRocket terms review, not an eligibility decision or consent to submit.

The whole static DOM text (excluding controls/hidden text) is bound to the owner
review. Category excerpts are keyword heuristics, not complete rule extraction.
Unlinked rules, external documents, CSS-only hidden text and changes after a
check remain outside this boundary. No network requests or side effects here.
"""
from __future__ import annotations
import hashlib
import json
import re
from bs4 import BeautifulSoup
from .application_flow import _hidden

REVIEW_TTL_SECONDS = 86400
MAX_HTML_BYTES = 2_000_000
MAX_TEXT_CHARS = 100_000
_PATTERNS = {
    'rules': r'\b(rule|rules|terms|condition|conditions|criteria|requirements)\b',
    'eligibility': r'\b(eligible|eligibility|student|students|age|resident|residency|country|countries)\b',
    'deadline': r'\b(deadline|closing|closes|ends|due|submission date)\b',
    'cost': r'\b(fee|fees|payment|paid|cost|charge|free)\b',
}


def review_required(record):
    return record.opportunity_kind == 'student_platform' and record.opportunity_id == 'challengerocket'


def terms_packet(url: str, html: str) -> dict:
    if len(html.encode('utf-8')) > MAX_HTML_BYTES:
        raise ValueError('competition page exceeds review capture limit')
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup(['script', 'style', 'noscript', 'input', 'textarea', 'select', 'button']):
        node.decompose()
    pieces = []
    for node in soup.find_all(string=True):
        if node.parent is not None and not _hidden(node.parent):
            text = ' '.join(str(node).split())
            if text: pieces.append(text)
    text = '\n'.join(pieces)
    if not text or len(text) > MAX_TEXT_CHARS:
        raise ValueError('competition page has no text or exceeds review text limit')
    # Bind ALL captured text, not only the heuristic excerpts. DOM text order is
    # retained and hidden/control values are excluded from the durable packet.
    digest = hashlib.sha256(json.dumps({'url': url, 'text': text}, sort_keys=True).encode()).hexdigest()
    excerpts = {key: [p for p in pieces if re.search(pattern, p, re.I)] for key, pattern in _PATTERNS.items()}
    return {'source_url': url, 'text': text, 'digest': digest, 'excerpts': excerpts,
            'missing_categories': [key for key, values in excerpts.items() if not values],
            'extraction_basis': 'static_dom_text_with_keyword_heuristic_excerpts',
            'eligibility_verified': False, 'deadline_verified': False,
            'cost_verified': False, 'submitted': False}


def require_review(record, url, html, now):
    if not review_required(record): return
    review = record.competition_review
    packet = terms_packet(url, html)
    if not review or review.get('digest') != packet['digest'] or review.get('source_url') != url:
        raise PermissionError('competition terms are unreviewed or changed; capture and review again')
    at = review.get('reviewed_at')
    if isinstance(at, bool) or not isinstance(at, (int, float)) or not 0 <= now - at < REVIEW_TTL_SECONDS:
        raise PermissionError('competition review expired or has an invalid time; review again')
    if not all(review.get(key) is True for key in ('rules_reviewed', 'eligibility_confirmed', 'deadline_confirmed', 'no_cost_confirmed')):
        raise PermissionError('owner must confirm rules, eligibility, deadline and no-cost entry')
