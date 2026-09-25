"""Real, free discovery sources for M22 beyond package registries.

Covers blog sites, podcast sites and git repository hosts. Every collector in
``default_source_collectors()`` talks to a public endpoint that needs no
account and no API key; each endpoint and response shape was verified live on
2026-09-25. The one keyed integration (Podcast Index) is optional config via
``ATLAS_PODCASTINDEX_API_KEY`` / ``ATLAS_PODCASTINDEX_API_SECRET`` and is only
registered when both are set - Atlas never requires a paid key.

Sources intentionally NOT included after live verification on 2026-09-25:
- Bitbucket: the 2.0 API no longer hosts unauthenticated global repository
  search (``GET /2.0/repositories?q=`` answers 404 "no API hosted at this URL").
- Gitee: ``GET /api/v5/search/repositories`` answers 200 with an empty list for
  every query tried (linux, oschina, kubernetes) without credentials.

Every collector yields the candidate dict contract consumed by
``service.Service._normalize`` plus a ``kind`` field
("blog" | "article" | "podcast" | "podcast-episode" | "repository").
"""
from __future__ import annotations

import asyncio
import hashlib
import html as html_lib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Iterator
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

USER_AGENT = "AtlasAI-ToolsHub/1.0 (+https://github.com/uditakankananonononono/atlas-ai)"
TIMEOUT_SECONDS = 15
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_FEED_ITEMS = 20
MAX_SUMMARY_CHARS = 400


class SourceError(ValueError):
    """A discovery source could not be reached or parsed."""


Fetch = Callable[[str], bytes]


def http_get(url: str, *, accept: str = "application/json, */*", limit: int = MAX_JSON_BYTES,
             headers: dict[str, str] | None = None) -> bytes:
    """HTTPS GET with Atlas UA and a hard byte cap."""
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept, **(headers or {})})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise SourceError(f"response from {url} exceeds the {limit}-byte cap")
    return data


def _strip_html(value: str) -> str:
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _truncate(value: str, limit: int = MAX_SUMMARY_CHARS) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _tag_slug(query: str) -> str:
    """Best-effort tag for tag-scoped blog search (DEV.to, Medium)."""
    return re.sub(r"[^a-z0-9]", "", query.lower())[:40]


def _recency_score(timestamp: str | None) -> float:
    if not timestamp:
        return 0.5
    try:
        seen = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return 0.5
    days = (datetime.now(timezone.utc) - seen).days
    if days <= 180:
        return 0.8
    if days <= 730:
        return 0.5
    return 0.2


class JsonSourceCollector:
    """Async collector over one JSON search endpoint. ``fetch`` is injectable for tests."""

    def __init__(self, name: str, kind: str, url_template: str,
                 parse: Callable[[Any], Iterator[dict[str, Any]]],
                 fetch: Fetch = http_get) -> None:
        self.name = name
        self.kind = kind
        self.url_template = url_template
        self.parse = parse
        self.fetch = fetch

    def url_for(self, query: str) -> str:
        return self.url_template.format(query=quote_plus(query), tag=_tag_slug(query))

    async def collect(self, query: str) -> AsyncIterator[dict[str, Any]]:
        raw = await asyncio.to_thread(self.fetch, self.url_for(query))
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SourceError(f"{self.name} returned non-JSON content: {exc}") from exc
        for item in self.parse(payload):
            item.setdefault("kind", self.kind)
            yield item


# --------------------------------------------------------------------------
# RSS / Atom feeds (blogs and podcasts)
# --------------------------------------------------------------------------

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(elem: ET.Element, *names: str) -> str:
    for child in elem:
        if _local(child.tag) in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def _entry_link(elem: ET.Element) -> str:
    fallback = ""
    for child in elem:
        if _local(child.tag) != "link":
            continue
        if child.text and child.text.strip():  # RSS <link>text</link>
            return child.text.strip()
        href = child.get("href", "")
        rel = child.get("rel", "alternate")
        if href and rel == "alternate":
            return href
        if href and not fallback:
            fallback = href
    return fallback


def _entry_enclosure(elem: ET.Element) -> tuple[str, str]:
    for child in elem:
        tag = _local(child.tag)
        if tag == "enclosure" and child.get("url"):
            return child.get("url", ""), child.get("type", "")
        if tag == "link" and child.get("rel") == "enclosure" and child.get("href"):
            return child.get("href", ""), child.get("type", "")
    return "", ""


def parse_feed(xml_bytes: bytes, *, max_items: int = MAX_FEED_ITEMS) -> Iterator[dict[str, Any]]:
    """Yield normalized entries from an RSS 2.0 or Atom feed document.

    ``kind`` is "podcast-episode" when the entry carries an audio enclosure,
    else "blog". Raises SourceError on malformed XML.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise SourceError(f"feed is not well-formed XML: {exc}") from exc
    entries = [e for e in root.iter() if _local(e.tag) in ("item", "entry")]
    for entry in entries[:max_items]:
        enclosure_url, enclosure_type = _entry_enclosure(entry)
        summary = _truncate(_strip_html(
            _child_text(entry, "description", "summary", "subtitle", "encoded")
        ))
        published = _child_text(entry, "pubdate", "published", "updated", "date")
        kind = "podcast-episode" if enclosure_type.startswith("audio") or enclosure_url else "blog"
        yield {
            "name": _child_text(entry, "title") or "(untitled)",
            "url": _entry_link(entry),
            "summary": summary,
            "kind": kind,
            "evidence": [e for e in [
                {"published": published} if published else None,
                {"enclosure_url": enclosure_url, "enclosure_type": enclosure_type} if enclosure_url else None,
                {"author": _child_text(entry, "author", "creator")} if _child_text(entry, "author", "creator") else None,
            ] if e],
        }


class FeedCollector:
    """Collector over one RSS/Atom feed URL. Streams the response and stops
    reading after ``max_items`` entries, so oversized podcast feeds (tens of
    MB) do not have to download in full. ``opener`` is injectable for tests."""

    def __init__(self, feed_url: str, *, name: str | None = None, max_items: int = MAX_FEED_ITEMS,
                 opener: Callable[[str], Any] | None = None) -> None:
        if not re.fullmatch(r"https://[^/]+/.*", feed_url or ""):
            raise SourceError(f"feed URL must be https with a path: {feed_url!r}")
        self.feed_url = feed_url
        self.name = name or f"feed:{feed_url.split('/')[2]}"
        self.kind = "feed"
        self.max_items = max_items
        self._opener = opener

    def _stream(self):
        if self._opener is not None:
            return self._opener(self.feed_url)
        request = Request(self.feed_url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, */*"})
        return urlopen(request, timeout=TIMEOUT_SECONDS)

    async def collect(self, query: str = "") -> AsyncIterator[dict[str, Any]]:
        def read_entries() -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            with self._stream() as stream:
                try:
                    for _event, elem in ET.iterparse(stream, events=("end",)):
                        if _local(elem.tag) not in ("item", "entry"):
                            continue
                        out.extend(parse_feed(ET.tostring(elem, encoding="utf-8"), max_items=1))
                        elem.clear()
                        if len(out) >= self.max_items:
                            break
                except ET.ParseError as exc:
                    raise SourceError(f"feed at {self.feed_url} is not well-formed XML: {exc}") from exc
            return out

        for item in await asyncio.to_thread(read_entries):
            yield item


def feed_collector(feed_url: str, *, name: str | None = None, max_items: int = MAX_FEED_ITEMS,
                   opener: Callable[[str], Any] | None = None) -> FeedCollector:
    """Build a collector for any blog or podcast RSS/Atom feed the user names."""
    return FeedCollector(feed_url, name=name, max_items=max_items, opener=opener)


class MediumTagCollector(JsonSourceCollector):
    """Medium tag feeds are RSS; reuse the feed parser with a per-query URL."""

    def __init__(self, fetch: Fetch = http_get) -> None:
        super().__init__("medium", "blog", "https://medium.com/feed/tag/{tag}", lambda p: iter(()), fetch)

    async def collect(self, query: str) -> AsyncIterator[dict[str, Any]]:
        if not _tag_slug(query):
            return
        raw = await asyncio.to_thread(self.fetch, self.url_for(query))
        for item in parse_feed(raw):
            item["kind"] = "blog"
            item["evidence"] = [{"source": "medium", "feed": self.url_for(query)}, *item.get("evidence", [])]
            yield item


# --------------------------------------------------------------------------
# Candidate parsers for the JSON sources (shapes verified live 2026-09-25)
# --------------------------------------------------------------------------

def _parse_devto(payload: Any) -> Iterator[dict[str, Any]]:
    for x in (payload if isinstance(payload, list) else [])[:20]:
        user = x.get("user") or {}
        yield {
            "name": x.get("title") or "(untitled)",
            "url": x.get("url") or "",
            "summary": _truncate(_strip_html(x.get("description") or "")),
            "version": None, "license": None,
            "maintenance": 0.6, "security": 0.55, "fit": 0.6, "novelty": 0.5,
            "evidence": [{
                "source": "dev.to", "author": user.get("name"),
                "reactions": x.get("public_reactions_count", x.get("positive_reactions_count", 0)),
                "comments": x.get("comments_count", 0), "tags": x.get("tag_list") or [],
                "published_at": x.get("published_at"),
            }],
            "permissions": [],
        }


def _parse_wordpress(payload: Any) -> Iterator[dict[str, Any]]:
    for x in (payload.get("posts") if isinstance(payload, dict) else [])[:20]:
        author = x.get("author") or {}
        discussion = x.get("discussion") or {}
        yield {
            "name": _strip_html(x.get("title") or "") or "(untitled)",
            "url": x.get("URL") or "",
            "summary": _truncate(_strip_html(x.get("excerpt") or "")),
            "version": None, "license": None,
            "maintenance": 0.55, "security": 0.55, "fit": 0.55, "novelty": 0.5,
            "evidence": [{
                "source": "wordpress.com", "author": author.get("name"),
                "comments": discussion.get("comment_count", 0), "published_at": x.get("date"),
                "site_id": x.get("site_ID"),
            }],
            "permissions": [],
        }


def _parse_hackernews(payload: Any) -> Iterator[dict[str, Any]]:
    for x in (payload.get("hits") if isinstance(payload, dict) else [])[:20]:
        url = x.get("url") or f"https://news.ycombinator.com/item?id={x.get('objectID')}"
        yield {
            "name": x.get("title") or "(untitled)",
            "url": url,
            "summary": _truncate(_strip_html(x.get("story_text") or "")) or f"Hacker News story by {x.get('author', 'unknown')}",
            "version": None, "license": None,
            "maintenance": 0.65, "security": 0.6, "fit": 0.6, "novelty": 0.5,
            "evidence": [{
                "source": "hackernews", "author": x.get("author"), "points": x.get("points", 0),
                "comments": x.get("num_comments", 0), "published_at": x.get("created_at"),
            }],
            "permissions": [],
        }


def _parse_itunes(payload: Any) -> Iterator[dict[str, Any]]:
    for x in (payload.get("results") if isinstance(payload, dict) else [])[:20]:
        artist = x.get("artistName") or "unknown artist"
        genres = [g for g in (x.get("genres") or []) if g.lower() != "podcasts"]
        yield {
            "name": x.get("collectionName") or x.get("trackName") or "(untitled podcast)",
            "url": x.get("collectionViewUrl") or x.get("trackViewUrl") or "",
            "summary": f"Podcast by {artist}" + (f" ({', '.join(genres[:3])})" if genres else ""),
            "version": None, "license": None,
            "maintenance": 0.6, "security": 0.6, "fit": 0.6, "novelty": 0.5,
            "evidence": [{
                "source": "itunes", "artist": artist, "genres": genres,
                "feed_url": x.get("feedUrl"), "episode_count": x.get("trackCount"),
            }],
            "permissions": [],
        }


def _parse_gitlab(payload: Any) -> Iterator[dict[str, Any]]:
    for x in (payload if isinstance(payload, list) else [])[:20]:
        yield {
            "name": x.get("path_with_namespace") or x.get("name") or "",
            "url": x.get("web_url") or "",
            "summary": x.get("description") or "",
            "version": None, "license": None,
            "maintenance": _recency_score(x.get("last_activity_at")),
            "security": 0.6, "fit": 0.7, "novelty": 0.5,
            "evidence": [{
                "source": "gitlab", "stars": x.get("star_count", 0), "forks": x.get("forks_count", 0),
                "last_activity_at": x.get("last_activity_at"), "topics": x.get("topics") or [],
                "visibility": x.get("visibility"),
            }],
            "permissions": [],
        }


def _parse_codeberg(payload: Any) -> Iterator[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else []
    for x in (data or [])[:20]:
        yield {
            "name": x.get("full_name") or x.get("name") or "",
            "url": x.get("html_url") or "",
            "summary": x.get("description") or "",
            "version": None, "license": None,
            "maintenance": 0.1 if x.get("archived") else _recency_score(x.get("updated_at")),
            "security": 0.6, "fit": 0.7, "novelty": 0.5,
            "evidence": [{
                "source": "codeberg", "stars": x.get("stars_count", 0), "forks": x.get("forks_count", 0),
                "updated_at": x.get("updated_at"), "language": x.get("language"),
                "archived": bool(x.get("archived")),
            }],
            "permissions": [],
        }


class PodcastIndexCollector:
    """Optional Podcast Index search (free tier, key required). Only built when
    ATLAS_PODCASTINDEX_API_KEY and ATLAS_PODCASTINDEX_API_SECRET are set; Atlas
    works fully without it. ``fetch`` is injectable for tests."""

    name = "podcastindex"
    kind = "podcast"
    SEARCH_URL = "https://api.podcastindex.org/api/1.0/search/byterm?q={query}&max=20"

    def __init__(self, api_key: str | None = None, api_secret: str | None = None,
                 fetch: Callable[[str, dict[str, str]], bytes] | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("ATLAS_PODCASTINDEX_API_KEY", "")
        self.api_secret = api_secret if api_secret is not None else os.environ.get("ATLAS_PODCASTINDEX_API_SECRET", "")
        if not self.api_key or not self.api_secret:
            raise SourceError("Podcast Index search needs ATLAS_PODCASTINDEX_API_KEY and ATLAS_PODCASTINDEX_API_SECRET")
        self._fetch = fetch

    def _auth_headers(self) -> dict[str, str]:
        epoch = str(int(time.time()))
        auth = hashlib.sha1((self.api_key + self.api_secret + epoch).encode()).hexdigest()
        return {"X-Auth-Key": self.api_key, "X-Auth-Date": epoch, "Authorization": auth}

    async def collect(self, query: str) -> AsyncIterator[dict[str, Any]]:
        url = self.SEARCH_URL.format(query=quote_plus(query))
        headers = self._auth_headers()

        def do_fetch() -> bytes:
            if self._fetch is not None:
                return self._fetch(url, headers)
            return http_get(url, headers=headers)

        try:
            payload = json.loads(await asyncio.to_thread(do_fetch))
        except json.JSONDecodeError as exc:
            raise SourceError(f"podcastindex returned non-JSON content: {exc}") from exc
        for x in (payload.get("feeds") or [])[:20]:
            yield {
                "name": x.get("title") or "(untitled podcast)",
                "url": x.get("link") or x.get("url") or "",
                "summary": _truncate(_strip_html(x.get("description") or "")),
                "kind": "podcast",
                "version": None, "license": None,
                "maintenance": _recency_score(
                    datetime.fromtimestamp(x["lastUpdateTime"], tz=timezone.utc).isoformat()
                    if isinstance(x.get("lastUpdateTime"), (int, float)) and x.get("lastUpdateTime") else None),
                "security": 0.6, "fit": 0.65, "novelty": 0.5,
                "evidence": [{
                    "source": "podcastindex", "author": x.get("author"), "feed_url": x.get("url"),
                    "language": x.get("language"), "itunes_id": x.get("itunesId"),
                }],
                "permissions": [],
            }


def default_source_collectors() -> list[Any]:
    """No-key collectors plus any optional keyed sources whose config exists."""
    collectors: list[Any] = [
        JsonSourceCollector("devto", "blog", "https://dev.to/api/articles?tag={tag}&per_page=20&top=30", _parse_devto),
        JsonSourceCollector("wordpress", "blog", "https://public-api.wordpress.com/rest/v1.2/read/search?q={query}&number=20", _parse_wordpress),
        JsonSourceCollector("hackernews", "article", "https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=20", _parse_hackernews),
        MediumTagCollector(),
        JsonSourceCollector("itunes", "podcast", "https://itunes.apple.com/search?media=podcast&term={query}&limit=20", _parse_itunes),
        JsonSourceCollector("gitlab", "repository", "https://gitlab.com/api/v4/projects?search={query}&per_page=20&order_by=last_activity_at", _parse_gitlab),
        JsonSourceCollector("codeberg", "repository", "https://codeberg.org/api/v1/repos/search?q={query}&limit=20", _parse_codeberg),
    ]
    try:
        collectors.append(PodcastIndexCollector())
    except SourceError:
        pass  # optional config absent - Atlas runs free-first without it
    return collectors
