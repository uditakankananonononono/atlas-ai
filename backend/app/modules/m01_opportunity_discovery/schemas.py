"""Pydantic request/response models for the Opportunity Discovery Engine (module 1).

These models are the HTTP boundary of the module. Domain internals live in
``service.py`` and never import FastAPI.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class OpportunityType(str, Enum):
    """Coarse opportunity categories assigned by the keyword tagger.

    The spec's fine-tuned DeBERTa classifier is deferred (see INTEGRATION.md);
    phase 1 tags deterministically so results are explainable and testable.
    """

    HACKATHON = "hackathon"
    COMPETITION = "competition"
    GRANT = "grant"
    FELLOWSHIP = "fellowship"
    SCHOLARSHIP = "scholarship"
    INTERNSHIP = "internship"
    PROGRAM = "program"
    OTHER = "other"


class SourceKind(str, Enum):
    """Fetch/parse strategy for a source.

    Only compliant transport is represented here: RSS/Atom feeds and official,
    documented JSON APIs. Sources that would require ToS-violating scraping,
    self-bots, or stealth are deliberately not representable (see
    INTEGRATION.md for the replacement plan).
    """

    RSS = "rss"
    GITHUB_SEARCH = "github_search"
    DEVPOST = "devpost"


class SourceOut(BaseModel):
    """Public description of a configured discovery source."""

    id: str
    name: str
    kind: SourceKind
    url: str
    default_type: OpportunityType
    enabled: bool


class ProfileIn(BaseModel):
    """The user profile a scan scores opportunities against."""

    interests: list[str] = Field(default_factory=list, max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=100)
    past_successes: list[str] = Field(default_factory=list, max_length=100)


class ScanRequestIn(BaseModel):
    """Request body for POST /scans."""

    source_ids: list[str] | None = Field(
        default=None, description="Restrict the scan to these source IDs; null scans every enabled source."
    )
    profile: ProfileIn = Field(default_factory=ProfileIn)
    notify_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="New opportunities at or above this match score are pushed to the notifier hook.",
    )


class SourceScanError(BaseModel):
    """Per-source failure captured during a scan; scans never abort on one bad source."""

    source_id: str
    error: str


class ScanResultOut(BaseModel):
    """Summary of one scan run."""

    scanned_sources: int
    fetched: int
    new: int
    updated: int
    notified: int
    errors: list[SourceScanError]


class OpportunityOut(BaseModel):
    """A normalized, scored, stored opportunity."""

    id: str
    source_id: str
    title: str
    url: str
    description: str
    deadline: datetime | None
    opportunity_type: OpportunityType
    match_score: float
    impact_heuristic: float = Field(
        description="Advisory deterministic heuristic, not a win probability."
    )
    score_kind: str = Field(default="heuristic", pattern="^heuristic$")
    advisory_only: bool = True
    tags: list[str]
    first_seen: datetime
    last_seen: datetime


class DigestRequestIn(BaseModel):
    """Request body for POST /digests.

    Producing a digest is free; *sending* it is an external effect and is
    always gated behind the Human Approval Center. ``use_llm`` polishes the
    digest prose through the shared BYOK provider; on any provider error the
    deterministic template is used instead.
    """

    min_score: float = Field(default=0.8, ge=0.0, le=1.0)
    max_items: int = Field(default=10, ge=1, le=100)
    recipient: str | None = Field(default=None, description="Intended recipient email, recorded for the approver.")
    use_llm: bool = False
    provider: str = "openai"
    model: str | None = None


class DigestProposalOut(BaseModel):
    """Result of POST /digests: a pending approval request plus a digest preview."""

    approval_id: str
    status: str
    item_count: int
    subject: str
    preview: str = Field(description="First 500 characters of the proposed digest body.")
