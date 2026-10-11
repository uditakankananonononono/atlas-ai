"""M01 free-source match: Fastweb public detail parsing and profile matching.

Scope (honest):
- Fastweb is the only one of the five named free sources with a public,
  logged-out page Atlas may parse. Listing rows come from m01's own
  ``discover``; this module adds a detail-page parser (JSON-LD plus the
  visible amount/awards/deadline block) and a profile matcher.
- RippleMatch, Simplify, RaiseMe and Bold.org have no public listing parsed
  here (account, extension or rate-limit challenge). They return no items.
- Nothing is submitted, no login is attempted, no paid tier is used.
- No form prefill here (m02 owns it).
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timezone

import httpx
from bs4 import BeautifulSoup

from .student_intelligence import annotate, extract_deadline, extract_student_level
from .student_platforms import BY_ID, PlatformUnavailable, _safe_target, discover

FASTWEB = BY_ID['fastweb']
SOURCE_ORDER = ('ripplematch', 'simplify', 'raiseme', 'bold', 'fastweb')
MAX_BYTES = 2_000_000
LEVELS = frozenset({'high school', 'undergraduate', 'graduate', 'phd'})

def _err(kind: str, name: str = '') -> ValueError:
    return ValueError('FREE_SOURCE_%s%s' % (kind, ':' + name if name else ''))


def source_capabilities() -> list[dict]:
    caps = []
    for pid in SOURCE_ORDER:
        p = BY_ID[pid]
        public = p.mode != 'launch_only'
        caps.append({'platform': pid, 'name': p.name, 'launch_url': p.url, 'public_parse': public,
                     'items_parsed_from': 'public listing and detail pages' if public else None,
                     'items': [], 'reason': '' if public else p.reason,
                     'paid_tier_used': False, 'submits': False})
    return caps


def _safe_detail_url(url) -> str:
    if not isinstance(url, str):
        raise _err('URL')
    target = _safe_target(FASTWEB, url)
    if target is None:
        raise _err('URL')
    return target


def _clean(text) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def _info(soup, wrapper: str):
    node = soup.select_one('.%s .award-info' % wrapper)
    return _clean(node.get_text(' ')) if node else None


def _money(raw):
    m = re.fullmatch(r'\$\s*([\d,]+)(?:\.\d+)?', raw or '')
    return {'amount': int(m.group(1).replace(',', '')), 'currency': 'USD'} if m else None


def _json_ld(soup) -> dict:
    for tag in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            data = json.loads(tag.string or '')
        except ValueError:
            continue
        if isinstance(data, dict) and data.get('@type') == 'MonetaryGrant':
            return data
    return {}


def _min_gpa(text: str):
    m = re.search(r'minimum (?:cumulative )?GPA of (\d(?:\.\d+)?)|GPA of (?:at least|\bno less than) (\d(?:\.\d+)?)', text, re.I)
    if not m:
        return None
    value = float(m.group(1) or m.group(2))
    return value if 0 < value <= 5 else None


def _base_row(title: str, url: str, description: str) -> dict:
    card = annotate({'title': title, 'description': description, 'url': url, 'platform': 'fastweb',
                     'source_url': FASTWEB.url, 'opportunity_kind': 'scholarship'})
    return {'id': card['id'], 'platform': 'fastweb', 'opportunity_kind': 'scholarship', 'title': title,
            'url': card['url'], 'source_url': FASTWEB.url, 'description': description,
            'student_level': card['student_level']}


def parse_fastweb_detail(html, url: str) -> dict:
    """Parse one public, logged-out Fastweb scholarship page into a row."""
    target = _safe_detail_url(url)
    if isinstance(html, bytes):
        html = html.decode('utf-8', 'replace')
    if not isinstance(html, str) or len(html) > MAX_BYTES:
        raise _err('PARSE', 'html')
    soup = BeautifulSoup(html, 'html.parser')
    ld = _json_ld(soup)
    h1 = soup.select_one('h1.award-name')
    title = _clean(h1.get_text(' ')) if h1 else _clean(ld.get('name'))
    if not title:
        raise _err('PARSE', 'title')
    provider_node = soup.select_one('.award-provider')
    funder = ld.get('funder') if isinstance(ld.get('funder'), dict) else {}
    provider = _clean(provider_node.get_text(' ')) if provider_node else _clean(funder.get('name'))
    description = _clean(ld.get('description'))
    if not description:
        meta = soup.find('meta', attrs={'property': 'og:description'})
        description = _clean(meta.get('content')) if meta else ''
    amount = _money(_info(soup, 'award-amount-wrapper'))
    if amount is None and isinstance(ld.get('amount'), dict):
        raw = str(ld['amount'].get('amount', ''))
        amount = {'amount': int(raw), 'currency': 'USD'} if raw.isdigit() else None
    awards_raw = _info(soup, 'awards-count-wrapper')
    awards = int(awards_raw) if awards_raw and awards_raw.isdigit() else None
    deadline_raw = _info(soup, 'award-deadline-wrapper')
    deadline = {'value': extract_deadline('deadline ' + deadline_raw)['value'] if deadline_raw else None,
                'raw': deadline_raw}
    apply_text = ' '.join(a.get_text(' ') for a in soup.select('.apply-now-button-wrapper a'))
    row = _base_row(title, target, description)
    row.update({'provider': provider, 'amount': amount, 'awards_available': awards, 'deadline': deadline,
                'min_gpa': _min_gpa(description),
                'requires_account_to_apply': 'login or sign up' in apply_text.lower(),
                'evidence_status': 'parsed_from_public_page'})
    row['student_level'] = extract_student_level(title + ' ' + description)
    return row


def _get(client, url: str, label: str) -> httpx.Response:
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        raise PlatformUnavailable('%s: source request failed (%s)' % (label, type(exc).__name__)) from exc
    if response.status_code != 200:
        raise PlatformUnavailable('%s: HTTP %s; no results claimed' % (label, response.status_code))
    if len(response.content) > MAX_BYTES:
        raise PlatformUnavailable('%s: response exceeds 2 MB limit' % label)
    if 'html' not in response.headers.get('content-type', '').lower():
        raise PlatformUnavailable('%s: expected HTML' % label)
    return response


def _new_client() -> httpx.Client:
    return httpx.Client(timeout=15, follow_redirects=False,
                        headers={'User-Agent': 'AtlasAI-StudentDiscovery/1.0'})


def fetch_fastweb_detail(url: str, *, client: httpx.Client | None = None) -> dict:
    target = _safe_detail_url(url)
    own = client is None
    client = client or _new_client()
    try:
        return parse_fastweb_detail(_get(client, target, 'fastweb').content, target)
    finally:
        if own:
            client.close()


def read_fastweb_listing(*, limit: int = 100, client: httpx.Client | None = None) -> list[dict]:
    """Listing rows via m01 discover (title and url only; nothing else is claimed)."""
    result = discover('fastweb', limit=limit, client=client)
    rows = []
    for item in result['items']:
        title = _clean(item['title'])
        row = _base_row(title, item['url'], '')
        provider = title.rsplit(' - ', 1)[1] if ' - ' in title else ''
        row.update({'provider': provider, 'amount': None, 'awards_available': None,
                    'deadline': {'value': None, 'raw': None}, 'min_gpa': None,
                    'requires_account_to_apply': None, 'evidence_status': 'listing_title_only'})
        rows.append(row)
    return rows


# ---- matching ---------------------------------------------------------------------
def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_profile(profile) -> dict:
    if isinstance(profile, bool) or not isinstance(profile, dict) or not profile:
        raise _err('PROFILE', 'profile')
    if 'gpa' in profile and not (_num(profile['gpa']) and 0 <= profile['gpa'] <= 5):
        raise _err('PROFILE', 'gpa')
    if 'min_award_usd' in profile and not (_num(profile['min_award_usd']) and profile['min_award_usd'] >= 0):
        raise _err('PROFILE', 'min_award_usd')
    if 'student_level' in profile and profile['student_level'] not in LEVELS:
        raise _err('PROFILE', 'student_level')
    if 'interests' in profile:
        terms = profile['interests']
        if not isinstance(terms, list) or not all(isinstance(t, str) and t.strip() for t in terms):
            raise _err('PROFILE', 'interests')
    return profile


def _as_of(value) -> date:
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise _err('AS_OF')
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise _err('AS_OF') from None


def _c(name: str, status: str, explanation: str, hard: bool = False) -> dict:
    return {'criterion': name, 'status': status, 'hard': hard, 'explanation': explanation}


def _criteria(profile: dict, row: dict, today: date) -> list[dict]:
    out = []
    # gpa (hard)
    if 'gpa' not in profile:
        out.append(_c('gpa', 'unknown', 'profile has no GPA', True))
    elif row.get('min_gpa') is None:
        out.append(_c('gpa', 'unknown', 'no minimum GPA stated on the page', True))
    elif profile['gpa'] >= row['min_gpa']:
        out.append(_c('gpa', 'met', 'profile GPA %s >= stated minimum %s' % (profile['gpa'], row['min_gpa']), True))
    else:
        out.append(_c('gpa', 'unmet', 'profile GPA %s < stated minimum %s' % (profile['gpa'], row['min_gpa']), True))
    # level (text mention, soft)
    levels = (row.get('student_level') or {}).get('levels') or []
    if 'student_level' not in profile:
        out.append(_c('level', 'unknown', 'profile has no student level'))
    elif not levels:
        out.append(_c('level', 'unknown', 'page text names no student level'))
    elif profile['student_level'] in levels:
        out.append(_c('level', 'met', 'page text mentions %s' % profile['student_level']))
    else:
        out.append(_c('level', 'unmet', 'page text mentions %s, profile is %s' % (', '.join(levels), profile['student_level'])))
    # award floor (soft preference)
    amount = row.get('amount')
    if 'min_award_usd' not in profile:
        out.append(_c('award', 'unknown', 'profile sets no award floor'))
    elif not amount or amount.get('currency') != 'USD':
        out.append(_c('award', 'unknown', 'page shows no USD amount'))
    elif amount['amount'] >= profile['min_award_usd']:
        out.append(_c('award', 'met', 'award $%s >= floor $%s' % (amount['amount'], profile['min_award_usd'])))
    else:
        out.append(_c('award', 'unmet', 'award $%s < floor $%s' % (amount['amount'], profile['min_award_usd'])))
    # deadline (hard when passed)
    deadline = row.get('deadline') or {}
    if deadline.get('value') is None:
        raw = deadline.get('raw')
        out.append(_c('deadline', 'unknown', 'no dated deadline on the page (%s)' % (raw if raw else 'not shown'), True))
    else:
        days = (date.fromisoformat(deadline['value']) - today).days
        if days < 0:
            out.append(_c('deadline', 'unmet', 'deadline %s passed %d days ago' % (deadline['value'], -days), True))
        else:
            out.append(_c('deadline', 'met', 'deadline %s, %d days left' % (deadline['value'], days), True))
    # interests (soft)
    if 'interests' not in profile:
        out.append(_c('interests', 'unknown', 'profile lists no interests'))
    else:
        text = (row.get('title', '') + ' ' + row.get('description', '')).lower()
        hits = [t for t in profile['interests'] if re.search(r'\b' + re.escape(t.strip().lower()) + r'\b', text)]
        if hits:
            out.append(_c('interests', 'met', 'page text mentions ' + ', '.join(hits)))
        else:
            out.append(_c('interests', 'unmet', 'page text mentions none of the listed interests'))
    return out


def match(profile: dict, rows: list, *, as_of) -> list[dict]:
    """Rank rows for a profile. Each criterion carries its evidence; unknown stays unknown."""
    profile = _check_profile(profile)
    today = _as_of(as_of)
    if isinstance(rows, bool) or not isinstance(rows, (list, tuple)) or not rows \
            or not all(isinstance(r, dict) for r in rows):
        raise _err('ROWS')
    results = []
    for row in rows:
        criteria = _criteria(profile, row, today)
        met = sum(c['status'] == 'met' for c in criteria)
        unmet = sum(c['status'] == 'unmet' for c in criteria)
        hard = [c['criterion'] for c in criteria if c['hard'] and c['status'] == 'unmet']
        result = dict(row)
        result.update({'criteria': criteria, 'unmet_hard': hard, 'eligible': not hard,
                       'score': round(met / (met + unmet), 4) if met + unmet else 0.0})
        results.append(result)
    results.sort(key=lambda r: (not r['eligible'], -r['score'], -((r.get('amount') or {}).get('amount') or 0),
                                r.get('title', '')))
    return results


def search_and_match(profile: dict, *, as_of, detail_limit: int = 5, client: httpx.Client | None = None) -> dict:
    """Fastweb listing, detail pages for the first rows, then profile matching. Read-only."""
    _check_profile(profile)
    _as_of(as_of)
    if isinstance(detail_limit, bool) or not isinstance(detail_limit, int) or not 0 <= detail_limit <= 25:
        raise _err('LIMIT')
    rows = read_fastweb_listing(client=client)
    fetched, errors = 0, []
    for i, row in enumerate(rows[:detail_limit]):
        try:
            rows[i] = fetch_fastweb_detail(row['url'], client=client)
            fetched += 1
        except (PlatformUnavailable, ValueError) as exc:
            errors.append({'url': row['url'], 'error': str(exc)[:120]})
    caps = source_capabilities()
    return {'scanned_at': datetime.now(timezone.utc).isoformat(), 'sources': caps,
            'matches': match(profile, rows, as_of=as_of), 'details_fetched': fetched, 'detail_errors': errors,
            'not_covered': {c['platform']: c['reason'] for c in caps if not c['public_parse']},
            'submitted': False}
