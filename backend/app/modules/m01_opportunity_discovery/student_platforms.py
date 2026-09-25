"""Free student-platform discovery. Read-only public listings or verified launch URLs.

No account impersonation, applications, browser autofill, or inference from a
platform homepage into an authenticated API. A blocked listing raises an error.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlsplit
import re
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from .service import cosine_similarity


@dataclass(frozen=True)
class StudentPlatform:
    id: str
    name: str
    url: str
    mode: str  # rss, html, or launch_only
    kind: str
    path_pattern: str = ""
    reason: str = ""


# Only these exact URLs are fetched. Entries marked launch_only are not scans.
PLATFORMS = (
    StudentPlatform('ripplematch', 'RippleMatch', 'https://ripplematch.com/', 'launch_only', 'job', reason='Account matching and auto-apply require an authorized interactive account flow.'),
    StudentPlatform('simplify', 'Simplify', 'https://simplify.jobs/copilot', 'launch_only', 'job', reason='Copilot is a user-installed Chrome extension; Atlas does not run it or submit forms.'),
    StudentPlatform('raiseme', 'RaiseMe', 'https://www.raiseme.com/', 'launch_only', 'scholarship', reason='Micro-scholarship balances and school matching require the student account.'),
    StudentPlatform('bold', 'Bold.org', 'https://bold.org/scholarships/', 'launch_only', 'scholarship', reason='The public listing returned a rate-limit challenge; do not evade it.'),
    StudentPlatform('fastweb', 'Fastweb', 'https://www.fastweb.com/college-scholarships', 'html', 'scholarship', r'^/college-scholarships/scholarships/\d+-'),
    StudentPlatform('devpost', 'Devpost', 'https://devpost.com/hackathons', 'launch_only', 'hackathon', reason='Official listing and linked RSS were checked; the RSS returned 403/406 from this environment, so automated discovery is not claimed.'),
    StudentPlatform('challengerocket', 'ChallengeRocket', 'https://challengerocket.com/hackathons-and-challenges.html', 'html', 'competition', r'^/(?:hackathon-|cassini|pwc-(?:rpa|ai|crisis)|euroclear-hackathon|open-learning-by-globalworth)'),
    StudentPlatform('mlh', 'Major League Hacking', 'https://www.mlh.com/seasons/2026/events', 'html', 'hackathon', r'^/events/\d+-'),
    StudentPlatform('internshala', 'Internshala', 'https://internshala.com/internships/', 'html', 'internship', r'^/internship/detail/'),
    StudentPlatform('scholarships360', 'Scholarships360', 'https://scholarships360.org/feed/', 'rss', 'scholarship', reason='Editorial feed, not a complete scholarship-search API.'),
    StudentPlatform('unigo', 'Unigo', 'https://www.unigo.com/scholarships', 'launch_only', 'scholarship', reason='Public landing page is available; no validated listings feed or account-matching API.'),
    StudentPlatform('scholarshiproar', 'Scholarship Roar', 'https://scholarshiproar.com/feed/', 'rss', 'scholarship'),
    StudentPlatform('scholarshipregion', 'Scholarship Region', 'https://www.scholarshipregion.com/feed/', 'rss', 'scholarship'),
    StudentPlatform('opportunitiesforafricans', 'Opportunities for Africans', 'https://www.opportunitiesforafricans.com/feed/', 'rss', 'program'),
    StudentPlatform('scholarshipunion', 'Scholarship Union', 'https://scholarshipunion.com/feed/', 'rss', 'scholarship'),
    StudentPlatform('opportunitiesforyouth', 'Opportunities for Youth', 'https://opportunitiesforyouth.org/feed/', 'rss', 'program'),
    StudentPlatform('kaggle', 'Kaggle Competitions', 'https://www.kaggle.com/competitions', 'launch_only', 'competition', reason='The public page is JavaScript rendered; no anonymous listing API was validated.'),
)
BY_ID = {p.id: p for p in PLATFORMS}
assert len(BY_ID) == len(PLATFORMS) == 17


class PlatformUnavailable(RuntimeError):
    pass


def _safe_target(source: StudentPlatform, href: str) -> str | None:
    url = urljoin(source.url, href)
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname is None or parsed.username or parsed.password:
        return None
    if source.id == 'mlh':
        if parsed.hostname != 'events.mlh.io':
            return None
    elif parsed.hostname != urlsplit(source.url).hostname:
        return None
    if not re.match(source.path_pattern, parsed.path):
        return None
    return parsed._replace(query='', fragment='').geturl()


def _read_rss(source: StudentPlatform, payload: bytes) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise PlatformUnavailable(f'{source.id}: invalid RSS response') from exc
    rows = []
    ns = '{http://www.w3.org/2005/Atom}'
    for item in root.iter('item'):
        rows.append({'title': ''.join(item.findtext('title', '')).strip(), 'url': item.findtext('link', '').strip(),
                     'description': unescape(re.sub('<[^>]+>', ' ', item.findtext('description', '')))[:600]})
    for item in root.iter(f'{ns}entry'):
        link = next((x.get('href', '') for x in item.findall(f'{ns}link') if x.get('rel') in (None, 'alternate')), '')
        rows.append({'title': item.findtext(f'{ns}title', '').strip(), 'url': link,
                     'description': unescape(re.sub('<[^>]+>', ' ', item.findtext(f'{ns}summary', '')))[:600]})
    return rows


def _read_html(source: StudentPlatform, payload: bytes) -> list[dict[str, str]]:
    soup = BeautifulSoup(payload, 'html.parser')
    rows = []
    for a in soup.select('a[href]'):
        if source.id == 'fastweb' and not a.find_parent('h3'):
            continue  # exclude promotional banners and 'See Details' duplicates
        if source.id == 'challengerocket' and not a.find_parent(class_='challenge-card__title'):
            continue  # only actual cards, not navigation links
        url = _safe_target(source, a['href'])
        if url is None:
            continue
        if source.id == 'mlh':
            title_node = a.select_one('h2, h3, h4')
            title = title_node.get_text(' ', strip=True) if title_node else (a.find('img').get('alt', '') if a.find('img') else a.get_text(' ', strip=True))
        else:
            title = a.get_text(' ', strip=True)
        title = re.sub(r'\s+', ' ', title).strip()
        if len(title) < 5 or title.lower() in {'see details', 'read more', 'apply now'}:
            continue
        rows.append({'title': title[:300], 'url': url, 'description': ''})
    return rows


def discover(platform_id: str, query: str = '', *, limit: int = 25, client: httpx.Client | None = None) -> dict:
    """Fetch a public source and return provenance-bearing, deterministically ranked links.

    The caller cannot supply arbitrary URLs; the fixed registry is the SSRF boundary.
    No application or account action is exposed here.
    """
    source = BY_ID.get(platform_id)
    if source is None:
        raise KeyError(platform_id)
    if not 1 <= limit <= 100 or len(query) > 200:
        raise ValueError('limit must be 1-100 and query at most 200 characters')
    if source.mode == 'launch_only':
        return {'platform': source.id, 'mode': source.mode, 'launch_url': source.url,
                'reason': source.reason, 'items': [], 'scanned_at': None}
    own_client = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=False, headers={'User-Agent': 'AtlasAI-StudentDiscovery/1.0'})
    try:
        response = client.get(source.url)
        if response.status_code != 200:
            raise PlatformUnavailable(f'{source.id}: HTTP {response.status_code}; no results claimed')
        if len(response.content) > 2_000_000:
            raise PlatformUnavailable(f'{source.id}: response exceeds 2 MB limit')
        ctype = response.headers.get('content-type', '').lower()
        if source.mode == 'rss' and not ('xml' in ctype or 'rss' in ctype):
            raise PlatformUnavailable(f'{source.id}: expected RSS/XML, got {ctype or "unknown"}')
        if source.mode == 'html' and 'html' not in ctype:
            raise PlatformUnavailable(f'{source.id}: expected HTML, got {ctype or "unknown"}')
        rows = _read_rss(source, response.content) if source.mode == 'rss' else _read_html(source, response.content)
        seen = set()
        items = []
        for row in rows:
            url = row['url'] if source.mode == 'rss' else _safe_target(source, row['url'])
            # RSS item links may go to the original publisher; allow only HTTPS,
            # never turn these links into network requests or auto-submit targets.
            if source.mode == 'rss':
                target = urlsplit(url)
                if target.scheme != 'https' or not target.hostname or target.username or target.password:
                    continue
            if not url or url in seen or not row['title']:
                continue
            seen.add(url)
            score = cosine_similarity(query, row['title'] + ' ' + row['description']) if query else 0.0
            items.append({'title': row['title'], 'url': url, 'description': row['description'],
                          'score': round(score, 4), 'source_url': source.url, 'platform': source.id,
                          'opportunity_kind': source.kind})
        if not items:
            raise PlatformUnavailable(f'{source.id}: no listing items parsed; layout may have changed')
        items.sort(key=lambda item: item['score'], reverse=True)
        return {'platform': source.id, 'mode': source.mode, 'launch_url': source.url,
                'scanned_at': datetime.now(timezone.utc).isoformat(), 'items': items[:limit]}
    except httpx.HTTPError as exc:
        raise PlatformUnavailable(f'{source.id}: source request failed ({type(exc).__name__})') from exc
    finally:
        if own_client:
            client.close()
