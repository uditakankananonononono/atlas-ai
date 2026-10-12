"""Decoded retention adapter used by admitted-case live-metadata route.

Robots must be fetched/decoded/parsed before page; fixed failure statuses,
no essay retention. Per-body caps bound retained decoded data, not transport
allocation, decompression peak memory, or wire bytes. Defaults500k robots/1MB
page, configurable helper bounds1..2000000. No redirects.
"""
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .admitted_cases import USER_AGENT, cases

PAGE_LIMIT_BYTES = 1_000_000
ROBOTS_LIMIT_BYTES = 500_000
TIMEOUT_SECONDS = 8
MAX_CRAWL_DELAY_SECONDS = 30   # a robots Crawl-delay above this is not waited out: the page is skipped
SAFE_STATUSES = frozenset({
    'robots_unverified', 'robots_denied', 'unavailable', 'unsupported_content_type',
    'too_large', 'fetch_failed', 'page_reachable', 'crawl_delay_too_long',
})


class BodyTooLarge(Exception):
    """Internal signal only; never surfaced to callers."""


def read_bounded(response: httpx.Response, limit: int) -> bytes:
    """Bound retained decoded body; transport chunks/decompression can allocate more."""
    if type(limit) is not int or not 0 <= limit <= 2_000_000:
        raise ValueError('limit must be integer0..2000000')
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes(chunk_size=min(16_384,limit+1)):
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
                                robots_limit: int = ROBOTS_LIMIT_BYTES,
                                max_crawl_delay: float = MAX_CRAWL_DELAY_SECONDS,
                                sleep=time.sleep) -> dict:
    """robots.txt Crawl-delay is honored: the helper waits that long (via `sleep`) between the robots request and the
    page request; a delay above `max_crawl_delay` (default 30s) skips the page with status crawl_delay_too_long.
    The delay is read for USER_AGENT, falling back to the `*` entry (stdlib RobotFileParser semantics). Only one page
    request follows one robots request per call, so no further per-host pacing exists across calls."""
    if isinstance(max_crawl_delay, bool) or not isinstance(max_crawl_delay, (int, float)) or not 0 <= max_crawl_delay <= 120:
        raise ValueError('max_crawl_delay must be 0..120 seconds')
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
            # 1b. Crawl-delay: honored or the page is skipped; never ignored.
            delay = parser.crawl_delay(USER_AGENT)
            if delay is not None and delay > max_crawl_delay:
                return _safe(row, 'crawl_delay_too_long', crawl_delay_seconds=delay)
            if delay:
                sleep(delay)
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
