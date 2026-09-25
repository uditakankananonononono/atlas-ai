"""Evidence-first analysis of public student opportunity listings.

These operations only transform source-backed discovery records. No account
access, submission, eligibility claim, deadline inference or money action.
Unknown facts stay unknown; text extraction requires an explicit nearby cue.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import re

from .student_platforms import BY_ID, PlatformUnavailable, discover

DATE_RE = r'(\d{4}-\d{2}-\d{2}|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})'
STOPWORDS = {'the', 'and', 'for', 'of', 'with', 'to', 'in', 'a', 'an', 'scholarship', 'hackathon', 'internship', 'program', 'opportunity'}


def _date(text: str) -> date | None:
    text = re.sub(r'\s+', ' ', text).strip()
    for fmt in ('%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%B %d %Y', '%b %d %Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def extract_deadline(text: str) -> dict:
    """1. Explicit 'apply by/deadline' date, never a posting or event date."""
    m = re.search(r'\b(?:application deadline|deadline|apply by|applications? (?:close|due))\s*[:\-]?\s*' + DATE_RE, text, re.I)
    return {'value': _date(m.group(1)).isoformat(), 'evidence': m.group(0)} if m and _date(m.group(1)) else {'value': None, 'evidence': None}


def extract_award(text: str) -> dict:
    """2. Explicit award amount, not a tuition fee or arbitrary dollar figure."""
    m = re.search(r'\b(?:award|prize|scholarship amount|stipend)\s*[:\-]?\s*(USD|US\$|\$|INR|₹|EUR|€|GBP|£)\s*([\d,]+)(?:\s*([kKmM]))?', text, re.I)
    if not m:
        return {'amount': None, 'currency': None, 'evidence': None}
    currency = {'USD': 'USD', 'US$': 'USD', '$': 'USD', 'INR': 'INR', '₹': 'INR', 'EUR': 'EUR', '€': 'EUR', 'GBP': 'GBP', '£': 'GBP'}[m.group(1).upper() if m.group(1).isascii() else m.group(1)]
    amount = int(m.group(2).replace(',', '')) * {'K': 1000, 'M': 1000000}.get((m.group(3) or '').upper(), 1)
    return {'amount': amount, 'currency': currency, 'evidence': m.group(0)}


def extract_delivery(text: str) -> dict:
    """3. Explicit remote/online/in-person delivery marker."""
    m = re.search(r'\b(remote|virtual|online|in-person|on-site|hybrid)\b', text, re.I)
    return {'value': ({'virtual': 'online', 'on-site': 'in-person'}.get(m.group(1).lower(), m.group(1).lower()) if m else None), 'evidence': m.group(0) if m else None}


def extract_student_level(text: str) -> dict:
    """4. Exact student-level mentions without claiming actual eligibility."""
    levels = {'high school': r'\b(?:high school|secondary school)\b', 'undergraduate': r'\b(?:undergrad(?:uate)?|bachelor.s)\b',
              'graduate': r'\b(?:graduate students?|postgrad(?:uate)?)\b', 'phd': r'\b(?:phd|doctoral)\b'}
    return {'levels': [level for level, pattern in levels.items() if re.search(pattern, text, re.I)], 'basis': 'text_mentions_not_eligibility'}


def extract_region(text: str) -> dict:
    """5. Constrained, explicit region mentions, not geographic eligibility."""
    regions = {'India': r'\bIndia\b', 'United States': r'\b(?:United States|U\.S\.A\.)\b', 'Africa': r'\bAfrica\b',
               'Europe': r'\bEurope\b', 'Worldwide': r'\b(?:worldwide|global)\b'}
    return {'mentions': [region for region, pattern in regions.items() if re.search(pattern, text, re.I)], 'basis': 'text_mentions_not_eligibility'}


def canonical_link(url: str) -> str:
    """6. Remove fragment/tracking query; retain functional query parameters."""
    u = urlsplit(url)
    if u.scheme != 'https' or not u.hostname or u.username or u.password:
        raise ValueError('HTTPS link required')
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}]
    return urlunsplit(('https', u.netloc.lower(), u.path.rstrip('/') or '/', urlencode(q), ''))


def stable_id(item: dict) -> str:
    """7. Stable content key across rescans and tracking-link changes."""
    return sha256(canonical_link(item['url']).encode()).hexdigest()[:24]


def annotate(item: dict) -> dict:
    """8. Source-derived evidence card, including every unknown field."""
    if item.get('platform') not in BY_ID or not item.get('source_url') == BY_ID[item['platform']].url:
        raise ValueError('platform/source provenance mismatch')
    text = f"{item.get('title', '')} {item.get('description', '')}"
    result = dict(item)
    result['url'] = canonical_link(item['url'])
    result['id'] = stable_id(result)
    result['deadline'] = extract_deadline(text)
    result['award'] = extract_award(text)
    result['delivery'] = extract_delivery(text)
    result['student_level'] = extract_student_level(text)
    result['region'] = extract_region(text)
    result['evidence_status'] = 'text_mentions_only'
    return result


def deduplicate(items: list[dict]) -> list[dict]:
    """9. Merge exact canonical URLs; keep distinct same-title listings."""
    output: dict[str, dict] = {}
    for item in items:
        key = canonical_link(item['url'])
        if key not in output:
            output[key] = dict(item, url=key, seen_on=[item['platform']])
        else:
            output[key]['seen_on'] = sorted(set(output[key]['seen_on']) | {item['platform']})
            if len(item.get('description', '')) > len(output[key].get('description', '')):
                output[key]['description'] = item['description']
    return list(output.values())


def filter_kind(items: list[dict], kind: str) -> list[dict]:
    """10. Kind filter based on source category, not generated classification."""
    return [item for item in items if item['opportunity_kind'] == kind]


def filter_platform(items: list[dict], platform: str) -> list[dict]:
    """11. Narrow to one provider's actual results."""
    return [item for item in items if item['platform'] == platform or platform in item.get('seen_on', [])]


def filter_terms(items: list[dict], terms: list[str], *, require_all: bool = False) -> list[dict]:
    """12. Positive keyword query over title and bounded excerpt."""
    terms = [x.strip().casefold() for x in terms if x.strip()]
    return [i for i in items if (all if require_all else any)(x in f"{i['title']} {i.get('description', '')}".casefold() for x in terms)] if terms else items


def exclude_terms(items: list[dict], terms: list[str]) -> list[dict]:
    """13. Negative keyword filter for irrelevant opportunities."""
    blocked = [x.strip().casefold() for x in terms if x.strip()]
    return [i for i in items if not any(x in f"{i['title']} {i.get('description', '')}".casefold() for x in blocked)]


def deadline_window(items: list[dict], start: date, end: date, *, include_unknown: bool = False) -> list[dict]:
    """14. Explicit deadline window; unknown optionally retained and labeled."""
    if end < start: raise ValueError('end before start')
    return [i for i in items if (i['deadline']['value'] is None and include_unknown) or (i['deadline']['value'] is not None and start <= date.fromisoformat(i['deadline']['value']) <= end)]


def exclude_expired(items: list[dict], *, today: date | None = None) -> list[dict]:
    """15. Hide known expired deadlines, retain unknowns as unknown."""
    today = today or datetime.now(timezone.utc).date()
    return [i for i in items if not i['deadline']['value'] or date.fromisoformat(i['deadline']['value']) >= today]


def minimum_award(items: list[dict], amount: int, currency: str, *, include_unknown: bool = False) -> list[dict]:
    """16. No cross-currency comparisons and no guessed missing amounts."""
    if amount < 0: raise ValueError('amount must be nonnegative')
    return [i for i in items if (i['award']['amount'] is None and include_unknown) or (i['award']['currency'] == currency and i['award']['amount'] is not None and i['award']['amount'] >= amount)]


def filter_delivery(items: list[dict], mode: str, *, include_unknown: bool = False) -> list[dict]:
    """17. Delivery-mode filter, explicit evidence only."""
    return [i for i in items if i['delivery']['value'] == mode or (include_unknown and i['delivery']['value'] is None)]


def filter_level_mentions(items: list[dict], level: str, *, include_unknown: bool = False) -> list[dict]:
    """18. Level-mention filter. Not an eligibility verdict."""
    return [i for i in items if level in i['student_level']['levels'] or (include_unknown and not i['student_level']['levels'])]


def filter_region_mentions(items: list[dict], region: str, *, include_unknown: bool = False) -> list[dict]:
    """19. Region-mention filter. Not a geographic eligibility verdict."""
    return [i for i in items if region in i['region']['mentions'] or (include_unknown and not i['region']['mentions'])]


def source_breakdown(items: list[dict]) -> dict:
    """20. Count by source/kind and unknown deadlines/awards."""
    return {'by_platform': dict(Counter(i['platform'] for i in items)),
            'by_kind': dict(Counter(i['opportunity_kind'] for i in items)),
            'deadline_unknown': sum(i['deadline']['value'] is None for i in items),
            'award_unknown': sum(i['award']['amount'] is None for i in items), 'total': len(items)}


def search_and_analyze(platform_ids: list[str], query: str = '', *, per_platform: int = 25) -> dict:
    """Apply 1-20 to actual public listings with isolated source failures."""
    if not platform_ids or len(platform_ids) > 5 or len(platform_ids) != len(set(platform_ids)):
        raise ValueError('choose 1-5 distinct platforms')
    if len(query) > 200 or not 1 <= per_platform <= 100:
        raise ValueError('query or per_platform out of bounds')
    if any(x not in BY_ID for x in platform_ids):
        raise ValueError('unknown platform')
    items, failures, launches = [], [], []
    for platform in platform_ids:
        try:
            result = discover(platform, query, limit=per_platform)
            if result['mode'] == 'launch_only':
                launches.append({'platform': platform, 'url': result['launch_url'], 'reason': result['reason']})
            else:
                items.extend(annotate(item) for item in result['items'])
        except PlatformUnavailable as exc:
            failures.append({'platform': platform, 'error': str(exc)})
    items = deduplicate(items)
    return {'items': items, 'breakdown': source_breakdown(items), 'launch_only': launches,
            'failures': failures, 'scanned_at': datetime.now(timezone.utc).isoformat(),
            'limits': 'Text mentions are not eligibility or an application; individual listing terms must be checked.'}


def refine(items: list[dict], *, kind: str | None = None, platform: str | None = None,
           terms: list[str] | None = None, require_all_terms: bool = False,
           exclude: list[str] | None = None, start: date | None = None, end: date | None = None,
           hide_expired: bool = False, min_award: int | None = None, currency: str | None = None,
           delivery: str | None = None, level: str | None = None, region: str | None = None,
           include_unknown: bool = False) -> list[dict]:
    """Compose public-result filters without inventing unknown source facts."""
    if bool(start) != bool(end): raise ValueError('start and end must be supplied together')
    if min_award is not None and not currency: raise ValueError('currency required with min_award')
    if kind: items = filter_kind(items, kind)
    if platform: items = filter_platform(items, platform)
    if terms: items = filter_terms(items, terms, require_all=require_all_terms)
    if exclude: items = exclude_terms(items, exclude)
    if start and end: items = deadline_window(items, start, end, include_unknown=include_unknown)
    if hide_expired: items = exclude_expired(items)
    if min_award is not None: items = minimum_award(items, min_award, currency, include_unknown=include_unknown)
    if delivery: items = filter_delivery(items, delivery, include_unknown=include_unknown)
    if level: items = filter_level_mentions(items, level, include_unknown=include_unknown)
    if region: items = filter_region_mentions(items, region, include_unknown=include_unknown)
    return items
