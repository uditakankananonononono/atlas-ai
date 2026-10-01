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
import time
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from hashlib import sha256
from .student_evidence import evidence_card


@dataclass(frozen=True)
class StudentPlatform:
    id: str
    name: str
    url: str
    mode: str  # rss, html, github_readme, or launch_only
    kind: str
    path_pattern: str = ""
    reason: str = ""


# Only these exact URLs are fetched. Entries marked launch_only are not scans.
PLATFORMS = (
    StudentPlatform('ripplematch', 'RippleMatch', 'https://ripplematch.com/', 'launch_only', 'job', reason='Account matching and auto-apply require an authorized interactive account flow.'),
    StudentPlatform('simplify', 'Simplify public community internship list', 'https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README.md', 'github_readme', 'internship', reason='Public Pitt CSC/Simplify maintained list only. No simplify.jobs scraping, Copilot, matching, autofill or applications.'),
    StudentPlatform('raiseme', 'RaiseMe', 'https://www.raiseme.com/', 'launch_only', 'scholarship', reason='Micro-scholarship balances and school matching require the student account.'),
    StudentPlatform('bold', 'Bold.org', 'https://bold.org/scholarships/', 'launch_only', 'scholarship', reason='The public listing returned a rate-limit challenge; do not evade it.'),
    StudentPlatform('fastweb', 'Fastweb', 'https://www.fastweb.com/college-scholarships', 'html', 'scholarship', r'^/college-scholarships/scholarships/\d+-'),
    StudentPlatform('devpost', 'Devpost', 'https://devpost.com/hackathons', 'launch_only', 'hackathon', reason='Devpost terms prohibit automated scraping/crawling. No undocumented API or browser workaround.'),
    StudentPlatform('challengerocket', 'ChallengeRocket', 'https://challengerocket.com/hackathons-and-challenges.html', 'html', 'competition', r'^/(?:hackathon-|cassini|pwc-(?:rpa|ai|crisis)|euroclear-hackathon|open-learning-by-globalworth)'),
    StudentPlatform('mlh', 'Major League Hacking', 'https://www.mlh.com/seasons/2026/events', 'html', 'hackathon', r'^/events/\d+-'),
    StudentPlatform('internshala', 'Internshala', 'https://internshala.com/internships/', 'launch_only', 'internship', reason='Terms prohibit automated data extraction for AI systems/RAG without prior written consent. No crawling or browser workaround.'),
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


def _plain_text(value: str) -> str:
    soup = BeautifulSoup(unescape(value), 'html.parser')
    for node in soup.select('script, style, template, noscript'):
        node.decompose()
    return soup.get_text(' ', strip=True)


def _safe_target(source: StudentPlatform, href: str) -> str | None:
    url = urljoin(source.url, href)
    try:
        parsed = urlsplit(url)
        if parsed.port not in (None, 443):
            return None
    except ValueError:
        return None
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
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b', payload, re.I):
        raise PlatformUnavailable(f'{source.id}: XML declarations are not supported')
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise PlatformUnavailable(f'{source.id}: invalid RSS response') from exc
    rows = []
    ns = '{http://www.w3.org/2005/Atom}'
    for item in root.iter('item'):
        rows.append({'title': ''.join(item.findtext('title', '')).strip(), 'url': item.findtext('link', '').strip(),
                     'evidence_text': _plain_text(item.findtext('description', ''))})
    for item in root.iter(f'{ns}entry'):
        link = next((x.get('href', '') for x in item.findall(f'{ns}link') if x.get('rel') in (None, 'alternate')), '')
        rows.append({'title': item.findtext(f'{ns}title', '').strip(), 'url': link,
                     'evidence_text': _plain_text(item.findtext(f'{ns}summary', ''))})
    for row in rows:
        row['description'] = row['evidence_text'][:600]
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


def _read_github_readme(payload: bytes) -> list[dict]:
    """Read the maintained public HTML tables, never fetch application links."""
    soup = BeautifulSoup(payload, 'html.parser')
    rows, company = [], ''
    for tr in soup.select('table tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 5:
            continue
        company_text = cells[0].get_text(' ', strip=True)
        inherited = company_text == '↳'
        if company_text != '↳':
            company = company_text
        if not company:
            continue
        role = cells[1].get_text(' ', strip=True)
        if '🔒' in tr.get_text():
            continue
        application = next((a for a in cells[3].select('a[href]')
                            if a.find('img', alt='Apply')), None)
        if application is None:
            continue
        href = application['href']
        try:
            target = urlsplit(href)
            if target.scheme != 'https' or not target.hostname or target.username or target.password:
                continue
            if target.port not in (None, 443):
                continue
        except ValueError:
            continue
        statements = []
        for marker, meaning in [('🇺🇸', 'Requires U.S. Citizenship'), ('🛂', 'Does NOT offer sponsorship'),
                                ('🎓', "Advanced degree required (Master's, PhD, MBA)")]:
            if marker in role or (not inherited and marker in company_text):
                statements.append(f'{marker}: {meaning} (repository legend)')
        rows.append({'title': f'{company}: {role}', 'url': href,
                     'description': f"Location: {cells[2].get_text(' ', strip=True)}",
                     'eligibility_statements': statements,
                     'source_unknowns': ['company_marker_applicability_unknown'] if inherited and any(m in company for m in ('🇺🇸', '🛂', '🎓')) else []})
    return rows


def discover(platform_id: str, query: str = '', *, limit: int = 25, client: httpx.Client | None = None) -> dict:
    """Fetch one public source and return evidence-bearing links in source order.

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
    started = time.monotonic()
    budget_seconds = 15.0
    def check_budget():
        if time.monotonic() - started >= budget_seconds:
            raise PlatformUnavailable(f'{source.id}: total fetch time budget exceeded')
    own_client = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=False, headers={'User-Agent': 'AtlasAI-StudentDiscovery/1.0'})
    try:
        # Streaming bounds decoded bytes during transfer, not after a potentially
        # unbounded client.get has buffered an entire response.
        check_budget()
        with client.stream('GET', source.url, follow_redirects=False, timeout=httpx.Timeout(1.0, connect=5.0)) as response:
            if str(response.url) != source.url:
                raise PlatformUnavailable(f'{source.id}: unexpected redirect; no results claimed')
            if response.status_code != 200:
                raise PlatformUnavailable(f'{source.id}: HTTP {response.status_code}; no results claimed')
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                check_budget()
                size += len(chunk)
                if size > 2_000_000:
                    raise PlatformUnavailable(f'{source.id}: response exceeds 2 MB limit')
                chunks.append(chunk)
            check_budget()
            payload = b''.join(chunks)
        ctype = response.headers.get('content-type', '').lower()
        if source.mode == 'rss' and not ('xml' in ctype or 'rss' in ctype):
            raise PlatformUnavailable(f'{source.id}: expected RSS/XML, got {ctype or "unknown"}')
        if source.mode == 'github_readme' and 'text/plain' not in ctype:
            raise PlatformUnavailable(f'{source.id}: expected public README text')
        if source.mode == 'html' and 'html' not in ctype:
            raise PlatformUnavailable(f'{source.id}: expected HTML, got {ctype or "unknown"}')
        rows = (_read_rss(source, payload) if source.mode == 'rss' else
                _read_github_readme(payload) if source.mode == 'github_readme' else
                _read_html(source, payload))
        fetched_at = datetime.now(timezone.utc).isoformat()
        content_hash = sha256(payload).hexdigest()
        seen = set()
        items = []
        for row in rows:
            url = row['url'] if source.mode in ('rss', 'github_readme') else _safe_target(source, row['url'])
            # RSS item links may go to the original publisher; allow only HTTPS,
            # never turn these links into network requests or auto-submit targets.
            if source.mode in ('rss', 'github_readme'):
                try:
                    target = urlsplit(url)
                    if target.port not in (None, 443):
                        continue
                except ValueError:
                    continue
                if target.scheme != 'https' or not target.hostname or target.username or target.password:
                    continue
            if not url or url in seen or not row['title']:
                continue
            seen.add(url)
            # Literal substring search, not an embedding/eligibility score.
            if query and query.casefold() not in (row['title'] + ' ' + row['description']).casefold():
                continue
            record = dict(row, source_url=source.url, platform=source.id,
                          opportunity_kind=source.kind)
            items.append(evidence_card(record, fetched_at=fetched_at, content_sha256=content_hash))
        if not rows or (not items and not query):
            raise PlatformUnavailable(f'{source.id}: no listing items parsed; layout may have changed')
        return {'platform': source.id, 'mode': source.mode, 'launch_url': source.url,
                'scanned_at': fetched_at, 'fetched_at': fetched_at, 'content_sha256': content_hash,
                'query_semantics': 'literal_substring_source_order', 'items': items[:limit]}
    except httpx.HTTPError as exc:
        raise PlatformUnavailable(f'{source.id}: source request failed ({type(exc).__name__})') from exc
    finally:
        if own_client:
            client.close()
