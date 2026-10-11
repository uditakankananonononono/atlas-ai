"""M22 delta sources: fyyd (podcasts) and Software Heritage (git origins).

Both endpoints need no account and no API key. Verified live 2026-10-11:

- fyyd: ``GET https://api.fyyd.de/0.2/search/podcast?title=<q>&count=20`` -> JSON
  ``{status, msg, meta, data:[...]}``. Public search needs no authorization
  (OAuth in the fyyd docs is for user-scoped actions).
- Software Heritage: ``GET https://archive.softwareheritage.org/api/1/origin/search/<q>/
  ?limit=20&with_visit=true`` -> JSON list of origins. The query is a PATH
  component. Anonymous use is rate limited (``X-Ratelimit-*`` headers; the
  documented anonymous ceiling is 120 requests per hour). The API terms allow
  free use of the public API for pointwise access and forbid massive
  extraction, so this collector spends one request per search, honours the
  window headers and 429, and never pages. It emits no personal data fields.

Excluded after probing (see docs/contracts/M22.search.md): Reddit (403),
Listen Notes (401), Hashnode (301 to a notice), Bluesky public search (403),
Stack Exchange (docs now require authenticated requests), gitea.com and
Launchpad (terms do not clearly allow automated anonymous API use).
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Iterator
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .sources import (MAX_JSON_BYTES, TIMEOUT_SECONDS, USER_AGENT, JsonSourceCollector,
                      SourceError, _recency_score, _truncate, _strip_html)

MAX_ITEMS = 20
FYYD_URL = "https://api.fyyd.de/0.2/search/podcast?title={query}&count=20"
SWH_URL = "https://archive.softwareheritage.org/api/1/origin/search/{query}/?limit=20&with_visit=true"

_FRACTION = re.compile(r"(\.\d+)")


def parse_ts(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp (any fraction length, Z or offset) to aware UTC.

    Python 3.10 ``fromisoformat`` rejects 5-digit fractions that Software
    Heritage emits, so the fraction is normalised to 6 digits first.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    text = _FRACTION.sub(lambda m: (m.group(1) + "000000")[:7], text, count=1)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _recency(value: Any) -> float:
    parsed = parse_ts(value)
    return _recency_score(parsed.isoformat() if parsed else None)


# ------------------------------------------------------------------ fyyd

def parse_fyyd(payload: Any) -> Iterator[dict[str, Any]]:
    if not isinstance(payload, dict):
        return
    if payload.get("status", 1) != 1:
        raise SourceError(f"fyyd returned status {payload.get('status')}: {payload.get('msg')}")
    for x in (payload.get("data") or [])[:MAX_ITEMS]:
        title = (x.get("title") or "").strip()
        url = x.get("htmlURL") or x.get("url_fyyd") or ""
        if not title or not url:
            continue
        yield {
            "name": title,
            "url": url,
            "summary": _truncate(_strip_html(x.get("description") or x.get("subtitle") or "")) or "Podcast on fyyd",
            "version": None, "license": None,
            "maintenance": _recency(x.get("lastpub")),
            "security": 0.6, "fit": 0.6, "novelty": 0.5,
            "evidence": [{
                "source": "fyyd", "feed_url": x.get("xmlURL"), "fyyd_url": x.get("url_fyyd"),
                "language": x.get("language"), "episode_count": x.get("episode_count"),
                "lastpub": x.get("lastpub"), "rank": x.get("rank"),
            }],
            "permissions": [],
            "kind": "podcast",
        }


def fyyd_collector(fetch: Callable[..., bytes] | None = None) -> JsonSourceCollector:
    kwargs = {"fetch": fetch} if fetch else {}
    return JsonSourceCollector("fyyd", "podcast", FYYD_URL, parse_fyyd, **kwargs)


# ------------------------------------------------------ Software Heritage

_FORGE_HOSTS = {"github.com", "gitlab.com", "codeberg.org"}


def origin_name(url: str) -> str:
    """``owner/repo`` for the forges other collectors already cover (so the
    service's name+URL dedup collapses them), else ``host/path``."""
    m = re.match(r"^https?://([^/]+)/(.+?)/?$", url.strip())
    if not m:
        return url.strip()
    host, path = m.group(1).lower(), m.group(2)
    if path.endswith(".git"):
        path = path[:-4]
    if host in _FORGE_HOSTS and "/" in path:
        return path
    return f"{host}/{path}"


def parse_softwareheritage(payload: Any) -> Iterator[dict[str, Any]]:
    if not isinstance(payload, list):
        return
    kept = 0
    for x in payload:
        if kept >= MAX_ITEMS:
            break
        url = (x.get("url") or "").strip()
        if not url or not x.get("has_visits"):
            continue
        kept += 1
        last = x.get("last_eventful_visit_date") or x.get("last_visit_date")
        yield {
            "name": origin_name(url),
            "url": url,
            "summary": f"Archived in the Software Heritage archive ({', '.join(x.get('visit_types') or ['unknown'])}, "
                       f"{x.get('nb_visits', 0)} visits)",
            "version": None, "license": None,
            "maintenance": _recency(last),
            "security": 0.6, "fit": 0.6, "novelty": 0.5,
            "evidence": [{
                "source": "softwareheritage", "visit_types": x.get("visit_types") or [],
                "nb_visits": x.get("nb_visits"), "snapshot_id": x.get("snapshot_id"),
                "last_visit_date": x.get("last_visit_date"),
                "last_eventful_visit_date": x.get("last_eventful_visit_date"),
            }],
            "permissions": [],
            "kind": "repository",
        }


SwhFetch = Callable[[str], "tuple[int, dict[str, str], bytes]"]


def swh_http_get(url: str) -> tuple[int, dict[str, str], bytes]:
    """GET returning (status, lower-cased headers, body); HTTP errors are returned, not raised."""
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read(MAX_JSON_BYTES + 1)[:MAX_JSON_BYTES]
    except HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, b""


class SoftwareHeritageCollector:
    name = "softwareheritage"
    kind = "repository"

    def __init__(self, fetch: SwhFetch = swh_http_get, clock: Callable[[], float] = time.time) -> None:
        self.fetch = fetch
        self.clock = clock
        self._blocked_until = 0.0

    def url_for(self, query: str) -> str:
        return SWH_URL.format(query=quote(query.strip(), safe=""))

    def _check_window(self) -> None:
        wait = self._blocked_until - self.clock()
        if wait > 0:
            raise SourceError(f"softwareheritage rate window exhausted; resets in {int(wait)}s")

    def _note_headers(self, headers: dict[str, str]) -> None:
        try:
            remaining = int(headers["x-ratelimit-remaining"])
            reset = float(headers["x-ratelimit-reset"])
        except (KeyError, ValueError):
            return
        self._blocked_until = reset if remaining <= 0 else 0.0

    async def collect(self, query: str) -> AsyncIterator[dict[str, Any]]:
        if not query or not query.strip():
            raise SourceError("softwareheritage needs a non-empty query")
        self._check_window()
        status, headers, body = await asyncio.to_thread(self.fetch, self.url_for(query))
        self._note_headers(headers)
        if status == 429:
            raise SourceError(f"softwareheritage rate limit hit (HTTP 429); retry after {headers.get('retry-after', 'unknown')}s")
        if status != 200:
            raise SourceError(f"softwareheritage returned HTTP {status}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SourceError(f"softwareheritage returned non-JSON content: {exc}") from exc
        for item in parse_softwareheritage(payload):
            yield item


def extra_source_collectors() -> list[Any]:
    return [fyyd_collector(), SoftwareHeritageCollector()]
