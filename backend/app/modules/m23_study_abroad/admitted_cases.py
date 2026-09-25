"""Public, provenance-preserving admitted-student case index.

Only catalog metadata is stored. Live metadata checks are opt-in; reading opens the publisher page.
The index is examples, not training data, admission probabilities, or verified causality.
"""
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

CATALOG = Path(__file__).with_name('admitted_cases.json')
USER_AGENT = 'AtlasCaseResearch/1.0 (public source research; no bulk copy)'

@lru_cache(maxsize=1)
def cases() -> list[dict]:
    entries = json.loads(CATALOG.read_text(encoding='utf-8'))
    assert len(entries) == len({item['id'] for item in entries})
    assert len(entries) == len({urlparse(item['url']).hostname for item in entries})
    assert all(urlparse(item['url']).scheme == 'https' for item in entries)
    return entries


def search_cases(query: str = '', evidence_type: str = '', limit: int = 20) -> list[dict]:
    """Deterministic catalog search, without claiming a fetched page is still live."""
    needle = query.casefold().strip()
    return [row for row in cases() if
            (not evidence_type or evidence_type == row['evidence_type']) and
            (not needle or any(needle in str(row[key]).casefold() for key in ('publisher', 'title', 'evidence_type')))
            ][:max(1, min(limit, 20))]


def fetch_case_metadata(case_id: str, transport: httpx.BaseTransport | None = None) -> dict:
    """Check robots and retrieve a title/description; never ingest the applicant's essay.

    A known HTTPS catalog URL is the only possible target; redirects are not followed.
    Unknown sites and login walls cannot become evidence through this function.
    """
    row = next((r for r in cases() if r['id'] == case_id), None)
    if row is None:
        raise KeyError(case_id)
    parsed = urlparse(row['url'])
    base = f'{parsed.scheme}://{parsed.netloc}'
    with httpx.Client(timeout=8, follow_redirects=False, transport=transport,
                      headers={'User-Agent': USER_AGENT}) as client:
        robots = client.get(base + '/robots.txt')
        if robots.status_code != 200:
            return {**row, 'live_status': 'robots_unverified', 'http_status': robots.status_code}
        parser = RobotFileParser()
        parser.parse(robots.text.splitlines())
        if not parser.can_fetch(USER_AGENT, row['url']):
            return {**row, 'live_status': 'robots_denied'}
        response = client.get(row['url'])
    if response.status_code != 200:
        return {**row, 'live_status': 'unavailable', 'http_status': response.status_code}
    if 'text/html' not in response.headers.get('content-type', '').lower():
        return {**row, 'live_status': 'unsupported_content_type'}
    if len(response.content) > 1_000_000:
        return {**row, 'live_status': 'too_large'}
    soup = BeautifulSoup(response.text, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    meta = soup.find('meta', attrs={'name': 'description'})
    description = meta.get('content', '') if meta else ''
    # Metadata is not proof of acceptance, and no essay body is retained.
    return {**row, 'live_status': 'page_reachable', 'page_title': title[:250],
            'page_description': description[:500], 'outcome_independently_verified': False}


def reading_route(case_id: str) -> dict:
    """Reading decision only; never copies a publisher's essay or calls the site."""
    row = next((r for r in cases() if r['id'] == case_id), None)
    if row is None:
        raise KeyError(case_id)
    return {**row, 'live_status': 'source_only',
            'reason': 'Open the original publisher page for personal reading; Atlas does not rehost this text.'}
