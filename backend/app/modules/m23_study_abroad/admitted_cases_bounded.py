"""Decoded retention adapter used by admitted-case live-metadata route.

Robots must be fetched/decoded/parsed before page; fixed failure statuses,
no essay retention. Per-body caps bound retained decoded data, not transport
allocation, decompression peak memory, or wire bytes. Defaults500k robots/1MB
page, configurable helper bounds1..2000000. No redirects.
"""
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .admitted_cases import USER_AGENT, cases

PAGE_LIMIT_BYTES = 1_000_000
ROBOTS_LIMIT_BYTES = 500_000
TIMEOUT_SECONDS = 8
SAFE_STATUSES = frozenset({
    'robots_unverified', 'robots_denied', 'unavailable', 'unsupported_content_type',
    'too_large', 'fetch_failed', 'page_reachable',
})


class BodyTooLarge(Exception):
    """Internal signal only; never surfaced to callers."""


def read_bounded(response: httpx.Response, limit: int) -> bytes:
    """Bound retained decoded body; transport chunks/decompression can allocate more."""
    if type(limit) is not int or not 0 <= limit <= 2_000_000:
        raise ValueError('limit must be integer0..2000000')
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes(chunk_size=16_384):
        room = limit + 1 - total
        if len(chunk) >= room:
            raise BodyTooLarge()
        chunks.append(chunk)
        total += len(chunk)
    return b''.join(chunks)


def _get_bounded(client: httpx.Client, url: str, limit: int):
    """Return (status_code, content_type, body_bytes). Raises BodyTooLarge or httpx.HTTPError."""
    with client.stream('GET', url) as response:
        status = response.status_code
        content_type = response.headers.get('content-type', '')
        if status != 200:
            return status, content_type, b''  # body not read for non-200
        declared = response.headers.get('content-length', '')
        if declared.isdigit() and int(declared) > limit:
            raise BodyTooLarge()  # hint only; the byte cap below is the real bound
        return status, content_type, read_bounded(response, limit)


def _safe(row: dict, status: str, **extra) -> dict:
    assert status in SAFE_STATUSES
    return {**row, 'live_status': status, **extra}


def fetch_case_metadata_bounded(case_id: str, transport: httpx.BaseTransport | None = None, *,
                                catalog: list[dict] | None = None,
                                page_limit: int = PAGE_LIMIT_BYTES,
                                robots_limit: int = ROBOTS_LIMIT_BYTES) -> dict:
    for bound in (page_limit,robots_limit):
        if type(bound) is not int or not 1<=bound<=2_000_000:raise ValueError('body limits must be integer1..2000000')
    rows = cases() if catalog is None else catalog
    row = next((r for r in rows if r['id'] == case_id), None)
    if row is None:
        raise KeyError(case_id)
    parsed = urlparse(row['url'])
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        return _safe(row, 'unavailable')
    base = f'{parsed.scheme}://{parsed.netloc}'
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False, transport=transport,
                          headers={'User-Agent': USER_AGENT}) as client:
            # 1. robots first; any failure refuses BEFORE the page request.
            try:
                status, _ctype, robots_body = _get_bounded(client, base + '/robots.txt', robots_limit)
            except BodyTooLarge:
                return _safe(row, 'robots_unverified')
            if status != 200:
                return _safe(row, 'robots_unverified', http_status=status)
            parser = RobotFileParser()
            try:robots_text=robots_body.decode('utf-8', errors='strict')
            except UnicodeError:return _safe(row,'robots_unverified')
            parser.parse(robots_text.splitlines())
            if not parser.can_fetch(USER_AGENT, row['url']):
                return _safe(row, 'robots_denied')
            # 2. page, bounded.
            try:
                status, ctype, page_body = _get_bounded(client, row['url'], page_limit)
            except BodyTooLarge:
                return _safe(row, 'too_large')
    except (httpx.HTTPError, ValueError, UnicodeError):
        return _safe(row, 'fetch_failed')  # no exception text, URL, or body in the result
    if status != 200:
        return _safe(row, 'unavailable', http_status=status)
    if 'text/html' not in ctype.lower():
        return _safe(row, 'unsupported_content_type')
    soup = BeautifulSoup(page_body.decode('utf-8', errors='replace'), 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    meta = soup.find('meta', attrs={'name': 'description'})
    description = (meta.get('content', '') if meta else '') or ''
    return _safe(row, 'page_reachable', page_title=title[:250], page_description=str(description)[:500],
                 outcome_independently_verified=False)
