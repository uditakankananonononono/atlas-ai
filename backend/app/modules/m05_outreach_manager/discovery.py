"""University and lab discovery: a curated public registry plus a
robots-respecting collector for public lab pages.

Ledger row CRM-133 (University/lab page collection). The registry ships
only well-known public institute pages; the collector fetches a single
public page at a time with an identifying User-Agent, honors robots.txt,
and extracts only what the page openly publishes (headings, mailto:
addresses, member-page links). No stealth, no login automation, no
circumvention - pages that disallow crawling are simply not fetched.
"""
from __future__ import annotations

import json
import re
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel, Field, field_validator

USER_AGENT = "AtlasAI-Outreach/0.1 (public page collection; contact: site owner)"
MAX_PAGE_BYTES = 1_000_000
ROBOTS_TTL_SECONDS = 3600.0
_MEMBER_HINT = re.compile(r"(people|team|member|staff|faculty|researchers|group)", re.IGNORECASE)


class DiscoveryError(RuntimeError):
    """Raised when a public page cannot be collected or parsed."""


class RobotsDisallowedError(DiscoveryError):
    """Raised when robots.txt disallows fetching the requested page."""


class LabEntry(BaseModel):
    """One curated, public lab/institute page in the registry."""

    university: str = Field(min_length=1, max_length=300)
    department: str = Field(min_length=1, max_length=300)
    lab_name: str = Field(min_length=1, max_length=300)
    topics: list[str] = Field(default_factory=list, max_length=50)
    url: str
    country: str | None = Field(default=None, max_length=2)

    @field_validator("url")
    @classmethod
    def require_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("registry entries must use public https URLs")
        return value


class LabRegistry:
    """Load and search the packaged lab registry."""

    def __init__(self, entries: list[LabEntry]) -> None:
        urls = [entry.url for entry in entries]
        if len(set(urls)) != len(urls):
            raise ValueError("lab registry contains duplicate URLs")
        self._entries = entries

    @classmethod
    def load(cls, path: Path | None = None) -> "LabRegistry":
        registry_path = path or Path(__file__).resolve().parent / "data" / "lab_registry.json"
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
        entries = [LabEntry(**item) for item in raw.get("entries", [])]
        if not entries:
            raise ValueError("lab registry is empty")
        return cls(entries)

    def all(self) -> list[LabEntry]:
        return list(self._entries)

    def search(self, query: str = "", topics: list[str] | None = None, limit: int = 25) -> list[LabEntry]:
        """Case-insensitive substring match over names, departments, and topics."""
        needle = query.strip().lower()
        wanted = [topic.strip().lower() for topic in (topics or []) if topic.strip()]
        matches: list[tuple[int, LabEntry]] = []
        for entry in self._entries:
            haystack = " ".join(
                [entry.university, entry.department, entry.lab_name, " ".join(entry.topics)]
            ).lower()
            if needle and needle not in haystack:
                continue
            if wanted and not any(
                any(wish in topic.lower() for topic in entry.topics) for wish in wanted
            ):
                continue
            strength = sum(1 for wish in wanted if any(wish in t.lower() for t in entry.topics))
            if needle and needle in entry.lab_name.lower():
                strength += 2
            matches.append((strength, entry))
        matches.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for _, entry in matches[:limit]]


class LabPage(BaseModel):
    """What one openly published lab page showed at collection time."""

    url: str
    title: str | None = None
    headings: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    member_links: list[str] = Field(default_factory=list)
    collected_at: datetime
    final_url: str | None = None


class _PublicPageParser(HTMLParser):
    """Extract title, headings, mailto: addresses, and member-page links."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self.title: str | None = None
        self.headings: list[str] = []
        self.emails: list[str] = []
        self.member_links: list[str] = []
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "a":
            href = attr.get("href") or ""
            if href.lower().startswith("mailto:"):
                address = href.split(":", 1)[1].split("?", 1)[0].strip()
                if address and "@" in address and address not in self.emails:
                    self.emails.append(address)
            elif _MEMBER_HINT.search(href) or _MEMBER_HINT.search(attr.get("title") or ""):
                absolute = urljoin(self._base_url, href)
                if absolute.startswith("https://") and absolute not in self.member_links:
                    self.member_links.append(absolute)
        if tag in {"title", "h1", "h2", "h3"}:
            self._capture = tag
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture != tag:
            return
        text = " ".join("".join(self._buffer).split())
        if tag == "title":
            self.title = self.title or text or None
        elif text and text not in self.headings:
            self.headings.append(text)
        self._capture = None
        self._buffer = []


@dataclass
class _RobotsEntry:
    parser: urllib.robotparser.RobotFileParser
    fetched_at: float


@dataclass
class RobotsCache:
    """Fetch and cache robots.txt per origin; deny-by-default on fetch failure."""

    client: httpx.AsyncClient
    clock: Any = None
    ttl_seconds: float = ROBOTS_TTL_SECONDS
    _cache: dict[str, _RobotsEntry] = field(default_factory=dict)

    def _now(self) -> float:
        if self.clock is not None:
            return self.clock()
        return datetime.now(timezone.utc).timestamp()

    async def allowed(self, url: str, user_agent: str = USER_AGENT) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        entry = self._cache.get(origin)
        if entry is None or self._now() - entry.fetched_at > self.ttl_seconds:
            parser = urllib.robotparser.RobotFileParser()
            try:
                response = await self.client.get(f"{origin}/robots.txt")
            except httpx.HTTPError as exc:
                raise DiscoveryError(f"robots.txt fetch failed for {origin}") from exc
            if response.status_code == 404:
                parser.parse([])
            elif response.is_error:
                raise DiscoveryError(
                    f"robots.txt fetch failed for {origin} ({response.status_code})"
                )
            else:
                parser.parse(response.text.splitlines())
            entry = _RobotsEntry(parser=parser, fetched_at=self._now())
            self._cache[origin] = entry
        return entry.parser.can_fetch(user_agent, url)


class LabPageCollector:
    """Collect one public lab page at a time, politely and transparently."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        robots: RobotsCache | None = None,
        user_agent: str = USER_AGENT,
        max_bytes: int = MAX_PAGE_BYTES,
    ) -> None:
        self._client = client
        self._robots = robots or RobotsCache(client)
        self._user_agent = user_agent
        self._max_bytes = max_bytes

    async def collect(self, url: str) -> LabPage:
        if not url.startswith("https://"):
            raise DiscoveryError("only public https pages are collected")
        if not await self._robots.allowed(url, self._user_agent):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")
        try:
            response = await self._client.get(
                url,
                headers={"User-Agent": self._user_agent, "Accept": "text/html"},
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise DiscoveryError(f"page fetch failed for {url}") from exc
        if response.is_error:
            raise DiscoveryError(f"page fetch failed for {url} ({response.status_code})")
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            raise DiscoveryError(f"page at {url} is not HTML ({content_type or 'unknown'})")
        body = response.content[: self._max_bytes]
        parser = _PublicPageParser(str(response.url))
        parser.feed(body.decode(response.encoding or "utf-8", errors="replace"))
        return LabPage(
            url=url,
            title=parser.title,
            headings=parser.headings[:50],
            emails=parser.emails[:50],
            member_links=parser.member_links[:50],
            collected_at=datetime.now(timezone.utc),
            final_url=str(response.url),
        )


class LabDiscoveryService:
    """Domain entry point: registry search plus public page collection."""

    def __init__(self, registry: LabRegistry, collector: LabPageCollector) -> None:
        self.registry = registry
        self.collector = collector

    def search_labs(self, query: str = "", topics: list[str] | None = None, limit: int = 25) -> list[LabEntry]:
        return self.registry.search(query=query, topics=topics, limit=limit)

    async def collect_lab_page(self, url: str) -> LabPage:
        return await self.collector.collect(url)

    async def discover_lab_contacts(self, url: str) -> dict[str, Any]:
        """Return the publicly listed contact surface of a lab page.

        Only mailto: addresses the page openly publishes are returned,
        each with the source URL as provenance. Names are never guessed:
        pairing addresses with people is a human/LLM review step on the
        collected headings and member pages.
        """
        page = await self.collector.collect(url)
        return {
            "url": page.url,
            "title": page.title,
            "emails": [{"email": email, "source_url": page.final_url} for email in page.emails],
            "member_pages": page.member_links,
            "collected_at": page.collected_at.isoformat(),
        }
