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


def fetch_case_metadata(case_id: str, transport: httpx.BaseTransport | None = None, **kwargs) -> dict:
    """Legacy entry point, kept for its test contract. It no longer has its own fetch path.

    It delegates to admitted_cases_bounded.fetch_case_metadata_bounded, so robots Crawl-delay
    (cap 30s, skipped above it), response-size bounds and the closed status set apply here too.
    routes.py already imports the bounded function under this name. Extra keyword arguments
    (max_crawl_delay, sleep, page_limit, ...) are passed through unchanged.
    """
    from .admitted_cases_bounded import fetch_case_metadata_bounded  # lazy: the bounded module imports this one
    return fetch_case_metadata_bounded(case_id, transport, **kwargs)


def reading_route(case_id: str) -> dict:
    """Reading decision only; never copies a publisher's essay or calls the site."""
    row = next((r for r in cases() if r['id'] == case_id), None)
    if row is None:
        raise KeyError(case_id)
    return {**row, 'live_status': 'source_only',
            'reason': 'Open the original publisher page for personal reading; Atlas does not rehost this text.'}
