"""Core domain models for Module 18 - Side Hustle & Knowledge Scraper.

Everything here is framework independent: no FastAPI, no pydantic, no network.
The module only collects content through legal channels (official public APIs,
published RSS/Atom feeds, robots-permitted public pages, user-provided text).
Every fetched item carries full provenance so downstream extraction, ranking
and freshness monitoring can justify each fact back to a source.

Compliance notes (atlas-compliance-boundaries):
- no scraping through personal logins at scale
- no unofficial/private APIs, no self-bots, no ban evasion, no proxy rotation
- no piracy sources
- public pages are stored as link + bounded excerpt only, never full mirrors
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional
from urllib.parse import urlsplit
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class RightsClass(str, Enum):
    """How the module is allowed to use a collected piece of content."""

    OFFICIAL_API = "official_api"        # documented public API, used under its public terms
    RSS_FEED = "rss_feed"                # published feed; store metadata + excerpt, link back
    PUBLIC_PAGE = "public_page"          # robots-permitted page; link + bounded excerpt only
    USER_PROVIDED = "user_provided"      # content the user handed to Atlas directly
    PROHIBITED = "prohibited"            # must never be collected


class SourceKind(str, Enum):
    REDDIT_JSON = "reddit_json"          # reddit.com public JSON listings (documented, UA-identified)
    YOUTUBE_DATA_API = "youtube_data_api"  # official YouTube Data API v3 with an API key
    RSS = "rss"                          # generic RSS/Atom feed
    HACKER_NEWS = "hacker_news"          # official HN Algolia API
    DEV_TO = "dev_to"                    # dev.to public articles API
    PUBLIC_WEB = "public_web"            # robots-permitted public page fetch
    PINTEREST_API = "pinterest_api"      # official Pinterest API v5
    X_API = "x_api"                      # official X API v2
    INSTAGRAM_GRAPH_API = "instagram_graph_api"  # official Graph API, user-provided links


# Platforms the user asked for that the compliance decision refuses. Collectors
# must reject these loudly instead of silently substituting a grey-area route.
PROHIBITED_PLATFORMS: Mapping[str, str] = {
    "tiktok_unofficial": "no unofficial/private TikTok API; use manual links or the official TikTok Research API",
    "instagram_login": "no login-driven Instagram scraping; public metadata via official APIs only",
    "instagram_reels_playwright": "no automated logged-in Reels capture; accepts user-provided links only",
    "pinterest_scraper": "no pinterest-scraper library; use the official Pinterest API v5 or RSS feeds",
    "discord_selfbot": "no Discord self-bots; only an invited bot via the official gateway",
    "proxy_rotation": "no proxy rotation or ban evasion of any kind",
}

# Public-page storage cap: link + excerpt, never a full mirror.
PUBLIC_PAGE_EXCERPT_CHARS = 2000

_URL_SCHEME_RE = re.compile(r"^https?$", re.IGNORECASE)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


@dataclass(frozen=True)
class FetchPolicy:
    """Network behaviour bounds shared by every collector.

    Defaults keep collection at human speed and well inside public-API norms.
    """

    user_agent: str = "AtlasAI-Research/1.0 (+https://github.com/uditakankananonononono/atlas-ai; contact: owner)"
    timeout_seconds: float = 15.0
    max_bytes: int = 2_000_000
    max_redirects: int = 5
    min_request_interval_seconds: float = 2.0
    max_retries: int = 3
    backoff_base_seconds: float = 2.0
    backoff_max_seconds: float = 120.0
    respect_robots_txt: bool = True
    robots_ttl_seconds: float = 86400.0
    allow_on_robots_error: bool = False  # conservative: unreachable robots.txt means do not crawl the page


@dataclass(frozen=True)
class HttpResponseRecord:
    url: str
    status: int
    headers: Mapping[str, str]
    body: bytes
    fetched_at: datetime = field(default_factory=utcnow)
    not_modified: bool = False
    truncated: bool = False

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class RobotsVerdict:
    url: str
    allowed: bool
    reason: str
    robots_url: str
    cached: bool = False


@dataclass
class RawDocument:
    """One collected item with provenance, before any LLM extraction."""

    url: str
    platform: str
    kind: SourceKind
    rights: RightsClass
    title: str = ""
    text: str = ""
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    retrieved_at: datetime = field(default_factory=utcnow)
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    http_status: Optional[int] = None
    content_hash: str = ""
    engagement: dict[str, float] = field(default_factory=dict)  # score, comments, views...
    meta: dict[str, Any] = field(default_factory=dict)          # source-specific extras (feed_url, video_id...)
    id: str = field(default_factory=lambda: new_id("doc"))

    def __post_init__(self) -> None:
        scheme = urlsplit(self.url).scheme
        if not _URL_SCHEME_RE.match(scheme):
            raise ValueError(f"only http(s) sources are collectible, got: {self.url!r}")
        if not self.url.strip():
            raise ValueError("url is required")
        if not self.platform.strip():
            raise ValueError("platform is required")
        if not self.content_hash:
            self.content_hash = sha256_text(self.title + "\n" + self.text)
        if self.rights is RightsClass.PUBLIC_PAGE and len(self.text) > PUBLIC_PAGE_EXCERPT_CHARS:
            # hard bound: public pages are excerpts only
            self.text = self.text[:PUBLIC_PAGE_EXCERPT_CHARS]

    def fingerprint(self) -> str:
        return self.content_hash


@dataclass(frozen=True)
class CollectionError:
    """A recorded, non-fatal collection failure. Failures are data, not crashes."""

    source: str
    url: str
    reason: str
    status: Optional[int] = None
    occurred_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class CollectionResult:
    documents: tuple[RawDocument, ...]
    errors: tuple[CollectionError, ...] = ()

    @property
    def ok(self) -> bool:
        return bool(self.documents) and not self.errors
