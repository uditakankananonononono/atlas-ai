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
             headers: dict[str, str] | None = None, truncate_ok: bool = False) -> bytes:
    """HTTPS GET with Atlas UA and a byte cap. ``truncate_ok`` keeps the first
    ``limit`` bytes instead of failing (for HTML pages and feed probes)."""
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept, **(headers or {})})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        if truncate_ok:
            return data[:limit]
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


def _enclosure_length(elem: ET.Element) -> str:
    for child in elem:
        if _local(child.tag) == "enclosure" and child.get("url"):
            return child.get("length", "")
        if _local(child.tag) == "link" and child.get("rel") == "enclosure" and child.get("href"):
            return child.get("length", "")
    return ""


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
        guid = _child_text(entry, "guid", "id")
        duration = _child_text(entry, "duration")
        kind = "podcast-episode" if enclosure_type.startswith("audio") or enclosure_url else "blog"
        yield {
            "name": _child_text(entry, "title") or "(untitled)",
            "url": _entry_link(entry),
            "summary": summary,
            "kind": kind,
            "guid": guid,
            "published": published,
            "evidence": [e for e in [
                {"published": published} if published else None,
                {"enclosure_url": enclosure_url, "enclosure_type": enclosure_type,
                 "enclosure_length": _enclosure_length(entry)} if enclosure_url else None,
                {"duration": duration} if duration else None,
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
        JsonSourceCollector("itunes-episodes", "podcast-episode", "https://itunes.apple.com/search?media=podcast&entity=podcastEpisode&term={query}&limit=20", _parse_itunes_episodes),
        JsonSourceCollector("gitlab", "repository", "https://gitlab.com/api/v4/projects?search={query}&per_page=20&order_by=last_activity_at", _parse_gitlab),
        JsonSourceCollector("codeberg", "repository", "https://codeberg.org/api/v1/repos/search?q={query}&limit=20", _parse_codeberg),
    ]
    try:
        collectors.append(PodcastIndexCollector())
    except SourceError:
        pass  # optional config absent - Atlas runs free-first without it
    return collectors


# --------------------------------------------------------------------------
# Phase 2: episode search, feed autodiscovery, OPML, feed watching, refresh
# --------------------------------------------------------------------------

def _parse_itunes_episodes(payload: Any) -> Iterator[dict[str, Any]]:
    """Apple Search API with entity=podcastEpisode (shape verified 2026-09-25)."""
    for x in (payload.get("results") if isinstance(payload, dict) else [])[:20]:
        show = x.get("collectionName") or "unknown show"
        yield {
            "name": x.get("trackName") or "(untitled episode)",
            "url": x.get("trackViewUrl") or x.get("episodeUrl") or "",
            "summary": _truncate(_strip_html(x.get("description") or "")) or f"Episode of {show}",
            "version": None, "license": None,
            "maintenance": _recency_score(x.get("releaseDate")),
            "security": 0.6, "fit": 0.6, "novelty": 0.5,
            "evidence": [{
                "source": "itunes-episodes", "show": show, "feed_url": x.get("feedUrl"),
                "released_at": x.get("releaseDate"),
                "duration_ms": x.get("trackTimeMillis"), "episode_url": x.get("episodeUrl"),
            }],
            "permissions": [],
        }


FEED_MIME_TYPES = {
    "application/rss+xml", "application/atom+xml", "application/feed+json",
    "application/xml", "text/xml", "application/rdf+xml",
}
COMMON_FEED_PATHS = ("/feed", "/feed/", "/rss", "/rss.xml", "/atom.xml", "/feed.xml",
                     "/index.xml", "/podcast.xml", "/episodes/rss",
                     "/feeds/posts/default", "/blog/feed", "/blog/rss")


def find_feed_links(html_text: str, base_url: str) -> list[str]:
    """Extract RSS/Atom feed URLs from <link rel=alternate type=...> tags."""
    from urllib.parse import urljoin
    out: list[str] = []
    for match in re.finditer(r"<link\b[^>]*>", html_text or "", re.I):
        tag = match.group(0)
        rel = re.search(r"rel=[\"']?([^\"' >]+)", tag, re.I)
        typ = re.search(r"type=[\"']([^\"']+)[\"']", tag, re.I)
        href = re.search(r"href=[\"']([^\"']+)[\"']", tag, re.I)
        if rel and "alternate" in rel.group(1).lower() and typ and href:
            if typ.group(1).lower().split(";")[0].strip() in FEED_MIME_TYPES:
                url = urljoin(base_url, html_lib.unescape(href.group(1)))
                if url not in out:
                    out.append(url)
    return out


def discover_feeds(site_url: str, *, fetch: Callable[..., bytes] = http_get,
                   probe_paths: tuple[str, ...] = COMMON_FEED_PATHS) -> list[str]:
    """Find the RSS/Atom feeds of a blog or podcast site.

    Strategy: parse the site's HTML for feed <link> tags; if none, probe the
    well-known feed paths. Returns absolute feed URLs, empty list when none.
    """
    if not re.fullmatch(r"https://[^/]+(/.*)?", site_url or ""):
        raise SourceError(f"site URL must be https: {site_url!r}")

    def looks_like_feed(url: str) -> bool:
        """A declared feed URL only counts if the document is actually a feed;
        some CMSs (Blogger) advertise a self-referencing <link> to the homepage."""
        if re.fullmatch(r"https://[^/]+/?", url):
            return False
        try:
            data = fetch(url, accept="application/xml, */*", limit=256 * 1024, truncate_ok=True)
        except Exception:
            return False
        head = data[:8192]
        return head.lstrip()[:5] == b"<?xml" and (b"<rss" in head or b"<feed" in head or b"<channel" in head)

    html_text = fetch(site_url, accept="text/html, */*", limit=1024 * 1024,
                      truncate_ok=True).decode("utf-8", errors="replace")
    verified = [url for url in find_feed_links(html_text, site_url) if looks_like_feed(url)]
    if verified:
        return verified
    base = re.match(r"(https://[^/]+)", site_url).group(1)
    found: list[str] = []
    for path in probe_paths:
        url = base + path
        if looks_like_feed(url):
            found.append(url)
    return found


# ---------------------------------------------------------------- OPML ----

def parse_opml(opml_text: str) -> list[dict[str, str]]:
    """Parse an OPML subscription list into {title, feed_url, site_url} dicts."""
    try:
        root = ET.fromstring(opml_text)
    except ET.ParseError as exc:
        raise SourceError(f"OPML is not well-formed XML: {exc}") from exc
    if _local(root.tag) != "opml":
        raise SourceError("document is not OPML")
    feeds: list[dict[str, str]] = []
    for elem in root.iter():
        if _local(elem.tag) != "outline":
            continue
        feed_url = elem.get("xmlUrl") or elem.get("xmlurl") or ""
        if not feed_url:
            continue
        feeds.append({
            "title": elem.get("title") or elem.get("text") or feed_url,
            "feed_url": feed_url,
            "site_url": elem.get("htmlUrl") or elem.get("htmlurl") or "",
        })
    return feeds


def feeds_to_opml(feeds: list[dict[str, str]], *, title: str = "Atlas M22 feed subscriptions") -> str:
    """Build an OPML 2.0 document from {title, feed_url, site_url} dicts."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<opml version="2.0"><head><title>{html_lib.escape(title)}</title>',
             f'<dateCreated>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")}</dateCreated>',
             '</head><body>']
    for feed in feeds:
        attrs = f'type="rss" text={html_lib.escape(feed.get("title") or feed["feed_url"], quote=True)!r}'
        attrs = attrs.replace("'", '"')
        attrs += f' xmlUrl="{html_lib.escape(feed["feed_url"], quote=True)}"'
        if feed.get("site_url"):
            attrs += f' htmlUrl="{html_lib.escape(feed["site_url"], quote=True)}"'
        lines.append(f"<outline {attrs}/>")
    lines.append("</body></opml>")
    return "\n".join(lines)


def collectors_from_opml(opml_text: str, *, max_items: int = MAX_FEED_ITEMS) -> list[FeedCollector]:
    """Turn an OPML subscription list into ready FeedCollectors (https feeds only)."""
    collectors: list[FeedCollector] = []
    for feed in parse_opml(opml_text):
        try:
            collectors.append(feed_collector(feed["feed_url"], name=feed["title"], max_items=max_items))
        except SourceError:
            continue  # non-https feed URLs are skipped, not fatal to the import
    return collectors


# ---------------------------------------------------------- feed watching ----

def _entry_id(entry: dict[str, Any]) -> str:
    for value in (entry.get("guid"), entry.get("url"), entry.get("name")):
        if value:
            base = str(value)
            break
    else:
        base = ""
    published = next((e.get("published") for e in entry.get("evidence", []) if isinstance(e, dict) and e.get("published")), "")
    enclosure = next((e.get("enclosure_url") for e in entry.get("evidence", []) if isinstance(e, dict) and e.get("enclosure_url")), "")
    return hashlib.sha256(f"{base}|{published}|{enclosure}".encode()).hexdigest()


class FeedWatcher:
    """Poll RSS/Atom feeds and return only entries not seen before.

    Seen-entry cursors persist in a JSON state file so watches survive
    restarts; state is capped at 500 entry ids per feed.
    """

    def __init__(self, state_path: str | os.PathLike) -> None:
        self.state_path = os.fspath(state_path)
        self._state: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._state is None:
            try:
                with open(self.state_path, encoding="utf-8") as fh:
                    self._state = json.load(fh)
            except (OSError, json.JSONDecodeError):
                self._state = {}
        return self._state

    def _save(self) -> None:
        assert self._state is not None
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        tmp = f"{self.state_path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._state, fh, indent=1)
        os.replace(tmp, self.state_path)

    async def poll(self, feed_url: str, *, max_items: int = MAX_FEED_ITEMS,
                   opener: Callable[[str], Any] | None = None) -> list[dict[str, Any]]:
        collector = feed_collector(feed_url, max_items=max_items, opener=opener)
        entries = [x async for x in collector.collect()]
        state = self._load()
        seen = set(state.get(feed_url, {}).get("seen", []))
        new_entries = [e for e in entries if _entry_id(e) not in seen]
        fresh = [_entry_id(e) for e in entries]
        state[feed_url] = {
            "seen": list(dict.fromkeys([*fresh, *(i for i in seen if i not in fresh)]))[:500],
            "last_polled_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(entries),
        }
        self._save()
        return new_entries


# ------------------------------------------------- repository refresh ----

_REPO_REFRESH_URLS = {
    "github": "https://api.github.com/repos/{name}",
    "gitlab": "https://gitlab.com/api/v4/projects/{name}",
    "codeberg": "https://codeberg.org/api/v1/repos/{name}",
}


def refresh_repository_candidate(name: str, source: str, *,
                                 fetch: Fetch = http_get) -> dict[str, Any]:
    """Re-fetch current stats for a repository candidate from its source API.

    Returns {"maintenance": float, "evidence": {...}}. Only the git hosts are
    supported; anything else is a SourceError, not a guess.
    """
    if source not in _REPO_REFRESH_URLS:
        raise SourceError(f"evidence refresh is not supported for source {source!r}")
    from urllib.parse import quote
    url = _REPO_REFRESH_URLS[source].format(name=quote(name, safe="") if source == "gitlab" else name)
    try:
        payload = json.loads(fetch(url))
    except json.JSONDecodeError as exc:
        raise SourceError(f"{source} returned non-JSON content: {exc}") from exc
    if source == "github":
        updated = payload.get("pushed_at") or payload.get("updated_at")
        evidence = {"source": "github", "stars": payload.get("stargazers_count", 0),
                    "forks": payload.get("forks_count", 0), "updated_at": updated,
                    "license": (payload.get("license") or {}).get("spdx_id"),
                    "archived": bool(payload.get("archived"))}
    elif source == "gitlab":
        updated = payload.get("last_activity_at")
        evidence = {"source": "gitlab", "stars": payload.get("star_count", 0),
                    "forks": payload.get("forks_count", 0), "last_activity_at": updated,
                    "visibility": payload.get("visibility"),
                    "archived": bool(payload.get("archived"))}
    else:
        updated = payload.get("updated_at")
        evidence = {"source": "codeberg", "stars": payload.get("stars_count", 0),
                    "forks": payload.get("forks_count", 0), "updated_at": updated,
                    "language": payload.get("language"), "archived": bool(payload.get("archived"))}
    maintenance = 0.1 if evidence.get("archived") else _recency_score(updated)
    return {"maintenance": maintenance, "evidence": evidence}
