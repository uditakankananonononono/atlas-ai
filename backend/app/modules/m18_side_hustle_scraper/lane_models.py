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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SENSITIVE_QUERY_KEYS = frozenset({"key", "api_key", "apikey", "token", "access_token"})


def _redact_url(url: str) -> str:
    """Redact credentials before a URL is recorded.

    Collector fetches need the real URL, but failure records are persisted
    and reported. Two credential carriers are stripped: sensitive query
    parameters (e.g. the YouTube Data API key, passed as ``?key=``) and any
    userinfo (``https://user:password@host``). The fragment is left
    unchanged: recorded request URLs do not carry OAuth-style fragment
    tokens today. URLs with nothing to redact are returned byte-identical.
    This is bounded redaction, not general credential hygiene: it does not
    catch percent-encoded key names or every free-text secret shape (see
    ``_scrub_text`` for the reason-text boundary).
    """
    parts = urlsplit(url)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    has_sensitive = any(key.lower() in _SENSITIVE_QUERY_KEYS for key, _ in pairs)
    has_userinfo = parts.username is not None or parts.password is not None
    if not has_sensitive and not has_userinfo:
        return url  # no credentials: keep the recorded URL byte-identical
    query = [(key, "[REDACTED]" if key.lower() in _SENSITIVE_QUERY_KEYS else value)
             for key, value in pairs]
    # Keep the original authority verbatim minus userinfo: hostname/port are
    # copied from the raw netloc so IPv6 brackets (``[::1]:8080``) survive and
    # urlsplit().port - which raises on some inputs - is never consulted.
    netloc = parts.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parts.scheme, netloc, parts.path, urlencode(query), parts.fragment))


_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(key|api_key|apikey|token|access_token)=[^\s&]+")
_USERINFO = re.compile(r"://[^/@\s]+:[^/@\s]+@")


def _scrub_text(text: str) -> str:
    """Redact credential-shaped material inside free text (e.g. a reason
    string that embeds a failing URL). Arbitrary reasons are not trusted to
    be secret-free."""
    text = _SENSITIVE_ASSIGNMENT.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    return _USERINFO.sub("://[REDACTED]@", text)
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

    def __post_init__(self) -> None:
        # Records are redacted at construction, whoever constructed the
        # record: the URL loses sensitive query keys and userinfo, and the
        # free-text reason is scrubbed for credential-shaped assignments and
        # userinfo. This is bounded redaction, not a guarantee that no
        # credential-shaped text survives (residuals: see _scrub_text).
        object.__setattr__(self, "url", _redact_url(self.url))
        object.__setattr__(self, "reason", _scrub_text(self.reason))


@dataclass(frozen=True)
class CollectionResult:
    documents: tuple[RawDocument, ...]
    errors: tuple[CollectionError, ...] = ()

    @property
    def ok(self) -> bool:
        return bool(self.documents) and not self.errors
