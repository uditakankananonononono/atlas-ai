"""Domain logic for the Opportunity Discovery Engine (module 1).

Spec reference: "Atlas AI: Complete Technical Module Specification", Module 1.

Phase-1 scope, per the agreed phased build:
- Compliant sources only: RSS/Atom feeds and official documented APIs.
  Sources the spec listed that would require ToS-violating scraping or
  self-bots (Unstop HTML scraping, LinkedIn, Instagram, X lists, Discord
  self-bots) are intentionally absent here; INTEGRATION.md records the
  compliant replacement for each.
- Parsing uses the Python standard library (ElementTree) so the module adds
  no new dependencies. The spec's spaCy/dateparser/DeBERTa NLP stack and the
  applied/won logistic-regression impact model are deferred until their
  contracts and training data exist (see INTEGRATION.md); deterministic
  keyword tagging, multi-format deadline parsing, cosine token-similarity
  matching, and a documented impact heuristic stand in.
- External effects are gated. Scans and reads are free; drafting a digest
  email only ever produces an ApprovalRequest through the shared approval
  store (module 0). This module never sends anything.

No FastAPI imports and no network or database work at import time: every
dependency is injected through the constructor.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Iterable, Protocol
from uuid import NAMESPACE_URL, uuid5

import httpx
from sqlalchemy import JSON, DateTime, Float, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base, SessionLocal
from app.core.models import ApprovalRequest

from .schemas import OpportunityOut, OpportunityType, ProfileIn, ScanResultOut, SourceKind, SourceOut, SourceScanError

MODULE_ID = 1
MODULE_SLUG = "opportunity-discovery"
MODULE_NAME = "Opportunity Discovery Engine"

DIGEST_ACTION_TYPE = "send_opportunity_digest_email"


class Normalizer(Protocol):
    def entities(self, text: str) -> list[str]: ...
    def deadline(self, text: str) -> datetime | None: ...


class SpacyDateNormalizer:
    """Real configurable spaCy NER plus dateparser deadline normalization.

    The spaCy model is explicit because shipping an unverified language model
    would hide provenance. Production sets ATLAS_SPACY_MODEL to an installed
    checkpoint; failure is clear instead of silently pretending regex is NER.
    """
    def __init__(self, model: str | None = None) -> None:
        import spacy
        self.model = model or os.getenv("ATLAS_SPACY_MODEL", "en_core_web_sm")
        try:
            self.nlp = spacy.load(self.model)
        except OSError as exc:
            raise RuntimeError(f"spaCy model {self.model!r} is not installed") from exc

    def entities(self, text: str) -> list[str]:
        return sorted({f"{ent.label_.lower()}:{ent.text.strip()}" for ent in self.nlp(text) if ent.text.strip()})

    def deadline(self, text: str) -> datetime | None:
        import dateparser.search
        match = _DEADLINE_RE.search(text)
        if not match:
            return None
        found = dateparser.search.search_dates(
            match.group(1), settings={"PREFER_DATES_FROM":"future", "RETURN_AS_TIMEZONE_AWARE":True}
        )
        if not found:
            return None
        parsed = found[0][1]
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class EmbeddingMatcher(Protocol):
    def similarity(self, opportunity_text: str, profile_text: str) -> float: ...


class HttpEmbeddingMatcher:
    """Synchronous scoring adapter for OpenAI BYOK or local Ollama BGE."""
    def __init__(self, provider: str | None = None) -> None:
        self.provider=(provider or os.getenv("ATLAS_EMBEDDING_PROVIDER", "openai")).lower()

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self.provider == "openai":
            key=os.getenv("OPENAI_API_KEY")
            if not key: raise RuntimeError("OPENAI_API_KEY is not configured")
            response=httpx.post("https://api.openai.com/v1/embeddings",headers={"Authorization":f"Bearer {key}"},json={"model":os.getenv("ATLAS_OPENAI_EMBEDDING_MODEL","text-embedding-3-large"),"input":texts,"dimensions":1024},timeout=120)
            response.raise_for_status(); return [x["embedding"] for x in sorted(response.json()["data"],key=lambda x:x["index"])]
        if self.provider in {"ollama","bge","local"}:
            base=os.getenv("ATLAS_OLLAMA_URL","http://ollama:11434").rstrip("/")
            response=httpx.post(f"{base}/api/embed",json={"model":os.getenv("ATLAS_OLLAMA_EMBEDDING_MODEL","bge-m3"),"input":texts,"truncate":True},timeout=300)
            response.raise_for_status(); return response.json()["embeddings"]
        raise RuntimeError(f"unsupported embedding provider: {self.provider}")

    def similarity(self, opportunity_text: str, profile_text: str) -> float:
        left,right=self._embed([opportunity_text,profile_text])
        dot=sum(a*b for a,b in zip(left,right)); norms=math.sqrt(sum(a*a for a in left))*math.sqrt(sum(b*b for b in right))
        return 0.0 if not norms else dot/norms

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Source:
    """A compliant discovery source: RSS/Atom or an official JSON API."""

    id: str
    name: str
    kind: SourceKind
    url: str
    default_type: OpportunityType = OpportunityType.OTHER
    enabled: bool = True


#: Default registry. Every entry is an RSS/Atom feed or an official,
#: documented API endpoint - no HTML scraping of sites that forbid it, no
#: self-bots, no unofficial social wrappers.
DEFAULT_SOURCES: tuple[Source, ...] = (
    Source(
        id="opportunity-desk-rss",
        name="Opportunity Desk",
        kind=SourceKind.RSS,
        url="https://www.opportunitydesk.org/feed/",
    ),
    Source(
        id="opportunities-for-youth-rss",
        name="Opportunities for Youth",
        kind=SourceKind.RSS,
        url="https://opportunitiesforyouth.org/feed/",
    ),
    Source(
        id="reddit-scholarships-rss",
        name="Reddit r/scholarships (new)",
        kind=SourceKind.RSS,
        url="https://www.reddit.com/r/scholarships/new/.rss",
        default_type=OpportunityType.SCHOLARSHIP,
    ),
    Source(
        id="reddit-competitions-rss",
        name="Reddit r/competitions (new)",
        kind=SourceKind.RSS,
        url="https://www.reddit.com/r/competitions/new/.rss",
        default_type=OpportunityType.COMPETITION,
    ),
    Source(
        id="github-topics-api",
        name="GitHub Topics: hackathon/competition (official REST API)",
        kind=SourceKind.GITHUB_SEARCH,
        url="https://api.github.com/search/repositories?q=topic:hackathon+topic:competition&sort=updated&per_page=50",
        default_type=OpportunityType.COMPETITION,
    ),
    Source(
        id="devpost-hackathons-api",
        name="Devpost hackathons feed",
        kind=SourceKind.DEVPOST,
        url="https://devpost.com/api/hackathons?status=upcoming",
        default_type=OpportunityType.HACKATHON,
    ),
)

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class OpportunityRow(Base):
    """Stored opportunity. Table name is module-prefixed to avoid collisions."""

    __tablename__ = "m01_opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    source_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2000), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opportunity_type: Mapped[str] = mapped_column(String(30), index=True)
    match_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    # Legacy database column name retained for migration compatibility only.
    # Public output names the value honestly as ``impact_heuristic``.
    impact_heuristic: Mapped[float] = mapped_column("expected_impact", Float, default=0.0)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Fetching and parsing
# ---------------------------------------------------------------------------


class FetchError(RuntimeError):
    """A source could not be retrieved or parsed. Scans isolate these per source."""


Fetcher = Callable[[Source], bytes]
Notifier = Callable[[OpportunityOut], None]
ApprovalPutter = Callable[[ApprovalRequest], ApprovalRequest]

_USER_AGENT = "atlas-ai-opportunity-discovery/0.1 (+https://atlas-ai.local)"


def default_fetcher(source: Source) -> bytes:
    """Fetch one source over HTTP with a descriptive user agent.

    Network work happens only here and only when a scan runs; tests inject a
    fake fetcher and never touch the network.
    """

    response = httpx.get(source.url, headers={"User-Agent": _USER_AGENT}, timeout=30, follow_redirects=True)
    if response.is_error:
        raise FetchError(f"{source.name} returned HTTP {response.status_code}")
    return response.content


def _text(element: ET.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def parse_rss(payload: bytes, source: Source) -> list[dict[str, Any]]:
    """Parse an RSS 2.0 or Atom feed into raw item dicts."""

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise FetchError(f"{source.name}: malformed feed XML ({error})") from error
    items: list[dict[str, Any]] = []
    # RSS 2.0
    for item in root.iter("item"):
        items.append(
            {
                "title": _text(item.find("title")),
                "url": _text(item.find("link")),
                "description": _text(item.find("description")),
                "published": _text(item.find("pubDate")),
            }
        )
    if items:
        return items
    # Atom (namespace-aware)
    ns = "{http://www.w3.org/2005/Atom}"
    for entry in root.iter(f"{ns}entry"):
        link = ""
        for link_el in entry.iter(f"{ns}link"):
            if link_el.get("rel") in (None, "alternate"):
                link = link_el.get("href", "")
                break
        items.append(
            {
                "title": _text(entry.find(f"{ns}title")),
                "url": link,
                "description": _text(entry.find(f"{ns}summary")) or _text(entry.find(f"{ns}content")),
                "published": _text(entry.find(f"{ns}updated")) or _text(entry.find(f"{ns}published")),
            }
        )
    return items


def parse_github_search(payload: bytes, source: Source) -> list[dict[str, Any]]:
    """Parse a GitHub search/repositories API response into raw item dicts."""

    import json

    try:
        data = json.loads(payload)
    except ValueError as error:
        raise FetchError(f"{source.name}: malformed JSON ({error})") from error
    return [
        {
            "title": repo.get("full_name", ""),
            "url": repo.get("html_url", ""),
            "description": repo.get("description") or "",
            "published": repo.get("pushed_at") or "",
            "extra_tags": list(repo.get("topics") or []),
        }
        for repo in data.get("items", [])
    ]


def parse_devpost(payload: bytes, source: Source) -> list[dict[str, Any]]:
    """Parse a Devpost hackathons JSON listing into raw item dicts."""

    import json

    try:
        data = json.loads(payload)
    except ValueError as error:
        raise FetchError(f"{source.name}: malformed JSON ({error})") from error
    items = []
    for entry in data.get("hackathons", []):
        items.append(
            {
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "description": entry.get("tagline") or "",
                "published": "",
            }
        )
    return items


_PARSERS: dict[SourceKind, Callable[[bytes, Source], list[dict[str, Any]]]] = {
    SourceKind.RSS: parse_rss,
    SourceKind.GITHUB_SEARCH: parse_github_search,
    SourceKind.DEVPOST: parse_devpost,
}

# ---------------------------------------------------------------------------
# Normalization: type tagging and deadline extraction
# ---------------------------------------------------------------------------

_TYPE_KEYWORDS: tuple[tuple[OpportunityType, tuple[str, ...]], ...] = (
    (OpportunityType.HACKATHON, ("hackathon", "hack day", "hackday")),
    (OpportunityType.COMPETITION, ("competition", "contest", "challenge", "olympiad", "tournament")),
    (OpportunityType.FELLOWSHIP, ("fellowship", "fellow ")),
    (OpportunityType.SCHOLARSHIP, ("scholarship", "bursary", "financial aid")),
    (OpportunityType.GRANT, ("grant", "funding call", "research funding")),
    (OpportunityType.INTERNSHIP, ("internship", "intern ")),
    (OpportunityType.PROGRAM, ("accelerator", "incubator", "residency", "summer program", "bootcamp")),
)

_DATE_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%d %B %Y", "%b %d, %Y", "%d %b %Y", "%Y/%m/%d")

_DEADLINE_RE = re.compile(
    r"(?:deadline|apply by|applications? (?:close|due)|submission(?:s)? due)[:\s]*([A-Za-z0-9,/\-\s]{6,40})",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def tag_type(title: str, description: str, default: OpportunityType) -> tuple[OpportunityType, list[str]]:
    """Tag an opportunity with the first matching keyword category.

    Returns the type plus the matched keyword tags. Deterministic and
    explainable; the spec's fine-tuned classifier replaces this later.
    """

    haystack = f"{title} {description}".lower()
    for opp_type, keywords in _TYPE_KEYWORDS:
        matched = [kw for kw in keywords if kw in haystack]
        if matched:
            return opp_type, matched
    return default, []


def parse_deadline(text: str) -> datetime | None:
    """Extract a deadline from free text.

    Tries an explicit "deadline:"-style phrase in several common date
    formats, then a bare ISO date, then RFC 2822 (feed pubDate format).
    Returns a timezone-aware datetime (UTC assumed when naive) or None.
    """

    candidates: list[str] = []
    match = _DEADLINE_RE.search(text)
    if match:
        candidates.append(match.group(1).strip().rstrip("."))
    candidates.extend(_ISO_DATE_RE.findall(text))
    for candidate in candidates:
        for fmt in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(candidate.strip(), fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            parsed = parsedate_to_datetime(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (TypeError, ValueError):
            continue
    return None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    "the a an and or of for to in on with by from at is are was were be been this that these those it its as "
    "you your we our they their will would can could not all any more most other some such only open new now "
    "worldwide global international free online".split()
)


def _tokens(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-z0-9]+", text.lower()) if len(tok) > 2 and tok not in _STOPWORDS]


def _vector(tokens: Iterable[str]) -> dict[str, float]:
    counts: dict[str, float] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0.0) + 1.0
    return counts


def cosine_similarity(text_a: str, text_b: str) -> float:
    """Cosine similarity over token-count vectors.

    Phase-1 stand-in for the spec's embedding cosine similarity, which needs
    an embedding provider and pgvector (see INTEGRATION.md).
    """

    vec_a, vec_b = _vector(_tokens(text_a)), _vector(_tokens(text_b))
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(value * vec_b.get(token, 0.0) for token, value in vec_a.items())
    norm_a = math.sqrt(sum(value * value for value in vec_a.values()))
    norm_b = math.sqrt(sum(value * value for value in vec_b.values()))
    return dot / (norm_a * norm_b)


def match_score(opportunity_text: str, profile: ProfileIn) -> float:
    """Score an opportunity against the user's profile, 0.0 to 1.0."""

    profile_text = " ".join([*profile.interests, *profile.skills, *profile.past_successes])
    return round(cosine_similarity(opportunity_text, profile_text), 4)


_PRIZE_RE = re.compile(r"\$\s?[\d,]+|\b\d+[kK]\s?(?:USD|dollars?|prize)", re.IGNORECASE)


def impact_heuristic(opportunity_text: str, opp_type: OpportunityType) -> float:
    """Advisory deterministic impact heuristic, 0.0 to 1.0.

    This is not a win probability. A learned outcome model remains disabled
    until consented row-level applications include both awards and declines
    across multiple cycles (see INTEGRATION.md).
    """

    score = 0.5
    if _PRIZE_RE.search(opportunity_text):
        score += 0.2
    lowered = opportunity_text.lower()
    if any(word in lowered for word in ("fully funded", "fully-funded", "stipend", "all expenses")):
        score += 0.15
    if opp_type in {OpportunityType.GRANT, OpportunityType.FELLOWSHIP, OpportunityType.SCHOLARSHIP}:
        score += 0.1
    return round(min(score, 1.0), 4)


def opportunity_id(url: str) -> str:
    """Stable ID derived from the canonical URL, so rescans upsert instead of duplicating."""

    return str(uuid5(NAMESPACE_URL, url.strip()))


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class Service:
    """Opportunity Discovery Engine domain service.

    All dependencies are injected so tests run fully offline:
    - ``session_factory``: SQLAlchemy session factory (defaults to the shared
      ``SessionLocal``). Tables are created lazily on first use.
    - ``fetcher``: ``Source -> bytes`` transport (defaults to real HTTP).
    - ``approval_putter``: persists an ApprovalRequest (defaults to the shared
      approval store from module 0).
    - ``notifier``: hook for high-match alerts; the integrator wires this to
      the SSE bus (see INTEGRATION.md).
    """

    def __init__(
        self,
        session_factory: Callable[[], Session] | None = None,
        fetcher: Fetcher | None = None,
        approval_putter: ApprovalPutter | None = None,
        notifier: Notifier | None = None,
        sources: Iterable[Source] | None = None,
        normalizer: Normalizer | None = None,
        embedding_matcher: EmbeddingMatcher | None = None,
        tenant_id: str = "local",
    ) -> None:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        self.tenant_id = tenant_id.strip()
        self._session_factory = session_factory or SessionLocal
        self._fetcher = fetcher or default_fetcher
        self._approval_putter = approval_putter or self._put_tenant_approval
        self._notifier = notifier
        self._sources = tuple(sources) if sources is not None else DEFAULT_SOURCES
        self._normalizer = normalizer
        self._embedding_matcher = embedding_matcher
        self._tables_ready = False

    def _put_tenant_approval(self, request: ApprovalRequest) -> ApprovalRequest:
        """Persist a digest approval under the same authenticated tenant as its items."""
        # Imported lazily so tests never touch the shared approval database.
        from app.modules.m00_approval_center.service import default_service

        view = default_service().submit(
            module_id=request.module_id,
            action_type=request.action_type,
            payload=request.payload,
            user_id=self.tenant_id,
        )
        return ApprovalRequest(
            id=view["id"], module_id=view["module_id"],
            action_type=view["action_type"], payload=view["payload"],
            status=view["status"],
        )

    def _ensure_tables(self) -> None:
        if self._tables_ready:
            return
        with self._session_factory() as session:
            Base.metadata.create_all(session.get_bind())
        self._tables_ready = True

    # -- introspection -----------------------------------------------------

    def list_sources(self) -> list[SourceOut]:
        """Return the configured source registry."""

        return [
            SourceOut(
                id=source.id,
                name=source.name,
                kind=source.kind,
                url=source.url,
                default_type=source.default_type,
                enabled=source.enabled,
            )
            for source in self._sources
        ]

    # -- scanning ----------------------------------------------------------

    def run_scan(
        self,
        source_ids: list[str] | None = None,
        profile: ProfileIn | None = None,
        notify_threshold: float = 0.8,
    ) -> ScanResultOut:
        """Fetch, parse, normalize, score, and store opportunities.

        One failing source never aborts the scan; its error is recorded and
        the remaining sources still run. New opportunities scoring at or
        above ``notify_threshold`` are pushed to the notifier hook.
        """

        self._ensure_tables()
        profile = profile or ProfileIn()
        selected = [s for s in self._sources if s.enabled and (source_ids is None or s.id in source_ids)]
        fetched = new = updated = notified = 0
        errors: list[SourceScanError] = []
        for source in selected:
            try:
                payload = self._fetcher(source)
                raw_items = _PARSERS[source.kind](payload, source)
            except (FetchError, Exception) as error:  # noqa: BLE001 - isolate per source by design
                errors.append(SourceScanError(source_id=source.id, error=str(error)))
                continue
            fetched += 1
            for raw in raw_items:
                opportunity, is_new = self._ingest(source, raw, profile)
                if opportunity is None:
                    continue
                new += 1 if is_new else 0
                updated += 0 if is_new else 1
                if is_new and opportunity.match_score >= notify_threshold and self._notifier is not None:
                    self._notifier(opportunity)
                    notified += 1
        return ScanResultOut(
            scanned_sources=len(selected),
            fetched=fetched,
            new=new,
            updated=updated,
            notified=notified,
            errors=errors,
        )

    def _ingest(self, source: Source, raw: dict[str, Any], profile: ProfileIn) -> tuple[OpportunityOut | None, bool]:
        title = (raw.get("title") or "").strip()
        url = (raw.get("url") or "").strip()
        if not title or not url:
            return None, False
        description = (raw.get("description") or "").strip()
        text = f"{title} {description}"
        opp_type, tags = tag_type(title, description, source.default_type)
        tags = sorted({*tags, *raw.get("extra_tags", [])})
        deadline = self._normalizer.deadline(text) if self._normalizer else parse_deadline(text)
        if self._normalizer:
            tags = sorted({*tags, *self._normalizer.entities(text)})
        now = datetime.now(timezone.utc)
        # The storage identity includes the authenticated tenant. This prevents
        # the same canonical URL from colliding across tenants while remaining
        # deterministic for rescans inside one tenant.
        row_id = str(uuid5(NAMESPACE_URL, f"{self.tenant_id}\n{url.strip()}"))
        with self._session_factory() as session:
            row = session.get(OpportunityRow, row_id)
            is_new = row is None
            if row is None:
                row = OpportunityRow(
                    id=row_id,
                    tenant_id=self.tenant_id,
                    source_id=source.id,
                    first_seen=now,
                    title=title,
                    url=url,
                    description=description,
                    opportunity_type=opp_type.value,
                    tags=tags,
                )
                session.add(row)
            row.title = title
            row.description = description
            row.deadline = deadline
            row.opportunity_type = opp_type.value
            row.tags = tags
            profile_text = " ".join([*profile.interests, *profile.skills, *profile.past_successes])
            row.match_score = round(self._embedding_matcher.similarity(text, profile_text), 4) if self._embedding_matcher and profile_text else match_score(text, profile)
            row.impact_heuristic = impact_heuristic(text, opp_type)
            row.last_seen = now
            session.commit()
            return self._to_out(row), is_new

    # -- reads -------------------------------------------------------------

    def list_opportunities(
        self,
        min_score: float = 0.0,
        opportunity_type: OpportunityType | None = None,
        limit: int = 50,
    ) -> list[OpportunityOut]:
        """List stored opportunities, best match first."""

        self._ensure_tables()
        with self._session_factory() as session:
            statement = (
                select(OpportunityRow)
                .where(
                    OpportunityRow.tenant_id == self.tenant_id,
                    OpportunityRow.match_score >= min_score,
                )
                .order_by(OpportunityRow.match_score.desc(), OpportunityRow.last_seen.desc())
                .limit(limit)
            )
            if opportunity_type is not None:
                statement = statement.where(OpportunityRow.opportunity_type == opportunity_type.value)
            return [self._to_out(row) for row in session.scalars(statement)]

    def get_opportunity(self, opportunity: str) -> OpportunityOut | None:
        """Return one opportunity by ID, or None."""

        self._ensure_tables()
        with self._session_factory() as session:
            row = session.scalar(
                select(OpportunityRow).where(
                    OpportunityRow.id == opportunity,
                    OpportunityRow.tenant_id == self.tenant_id,
                )
            )
            return self._to_out(row) if row is not None else None

    def top_opportunities(self, min_score: float, limit: int) -> list[OpportunityOut]:
        """The highest-scoring opportunities at or above ``min_score``."""

        return self.list_opportunities(min_score=min_score, limit=limit)

    # -- digest (gated external effect) ------------------------------------

    @staticmethod
    def digest_subject(items: list[OpportunityOut]) -> str:
        return f"Atlas AI opportunity digest: {len(items)} high-match opportunities"

    @staticmethod
    def render_digest(items: list[OpportunityOut]) -> str:
        """Deterministic digest body used when no BYOK LLM polish is requested."""

        lines = ["Here are your highest-matching opportunities:", ""]
        for index, item in enumerate(items, start=1):
            deadline = item.deadline.strftime("%Y-%m-%d") if item.deadline else "no deadline found"
            lines.append(
                f"{index}. {item.title} ({item.opportunity_type.value}, match {item.match_score:.2f}, "
                f"advisory impact heuristic {item.impact_heuristic:.2f}, deadline {deadline})"
            )
            lines.append(f"   {item.url}")
        return "\n".join(lines)

    @staticmethod
    def digest_prompt(items: list[OpportunityOut]) -> str:
        """Prompt for optional BYOK LLM polish of the digest prose."""

        listing = "\n".join(
            f"- {item.title} | {item.opportunity_type.value} | match {item.match_score:.2f} | "
            f"deadline {item.deadline.strftime('%Y-%m-%d') if item.deadline else 'unknown'} | {item.url}"
            for item in items
        )
        return (
            "Write a short, friendly opportunity digest email from this list. "
            "Keep every title, URL, and deadline exactly as given; add no new facts.\n\n"
            f"{listing}"
        )

    def propose_digest(
        self,
        items: list[OpportunityOut],
        body: str,
        recipient: str | None = None,
    ) -> ApprovalRequest:
        """Gate a digest send behind the Human Approval Center.

        This method never sends anything. It records an ApprovalRequest whose
        execution stays disabled until a human approves it; the Email
        Assistant (module 10) performs the actual send after approval.
        """

        request = ApprovalRequest(
            id=f"m01-digest-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-"
            f"{hashlib.sha1(body.encode()).hexdigest()[:8]}",
            module_id=MODULE_ID,
            action_type=DIGEST_ACTION_TYPE,
            payload={
                "subject": self.digest_subject(items),
                "body": body,
                "recipient": recipient,
                "item_ids": [item.id for item in items],
                "tenant_id": self.tenant_id,
                "execution_enabled": False,
            },
        )
        return self._approval_putter(request)

    # -- mapping -----------------------------------------------------------

    @staticmethod
    def _to_out(row: OpportunityRow) -> OpportunityOut:
        deadline = row.deadline
        if deadline is not None and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return OpportunityOut(
            id=row.id,
            source_id=row.source_id,
            title=row.title,
            url=row.url,
            description=row.description,
            deadline=deadline,
            opportunity_type=OpportunityType(row.opportunity_type),
            match_score=row.match_score,
            impact_heuristic=row.impact_heuristic,
            score_kind="heuristic",
            advisory_only=True,
            tags=list(row.tags or []),
            first_seen=row.first_seen,
            last_seen=row.last_seen,
        )
