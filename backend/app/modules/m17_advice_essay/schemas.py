"""Typed contracts for Module 17.

The module accepts only user-owned or lawfully public material. It coaches the
user from their own experiences and never represents generated prose as a
submission-ready essay authored by the user.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SourceKind(str, Enum):
    USER_SUBMITTED = "user_submitted"
    PUBLIC_API = "public_api"
    PUBLIC_WEB = "public_web"


class MediaKind(str, Enum):
    TEXT = "text"
    AUDIO_TRANSCRIPT = "audio_transcript"
    VIDEO_TRANSCRIPT = "video_transcript"


class AdviceSource(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    source_kind: SourceKind
    media_kind: MediaKind = MediaKind.TEXT
    platform: str = Field(min_length=1, max_length=80)
    canonical_url: str | None = Field(default=None, max_length=2048)
    creator: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1, max_length=100_000)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    permission_basis: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def public_sources_need_a_url(self) -> "AdviceSource":
        if self.source_kind != SourceKind.USER_SUBMITTED and not self.canonical_url:
            raise ValueError("public sources require a canonical_url for provenance")
        return self


class AdviceTip(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    topic: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=2000)
    source_ids: list[UUID] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    caveats: list[str] = Field(default_factory=list)


class IdentityMaterial(BaseModel):
    """A user-confirmed experience, value, trait, or writing sample."""

    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=5000)
    user_confirmed: bool = False
    tags: list[str] = Field(default_factory=list, max_length=30)


class EssayBrief(BaseModel):
    owner_id: UUID
    prompt: str = Field(min_length=1, max_length=5000)
    word_limit: int = Field(ge=50, le=5000)
    material_ids: list[UUID] = Field(min_length=1)
    requested_concepts: int = Field(default=5, ge=1, le=10)


class EssayConcept(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    title: str = Field(min_length=1, max_length=200)
    metaphor: str = Field(min_length=1, max_length=500)
    outline: list[str] = Field(min_length=3, max_length=12)
    opening_scaffold: str = Field(min_length=1, max_length=1200)
    material_ids: list[UUID] = Field(min_length=1)
    advice_tip_ids: list[UUID] = Field(default_factory=list)
    coaching_notice: str = (
        "Coaching scaffold only. Verify every fact and rewrite in your own words "
        "before using it in an application."
    )


class CritiqueDimension(str, Enum):
    NARRATIVE_FLOW = "narrative_flow"
    GRAMMAR = "grammar"
    PROMPT_ALIGNMENT = "prompt_alignment"
    SPECIFICITY = "specificity"
    CLICHES = "cliches"
    VOICE_CONSISTENCY = "voice_consistency"


class CritiqueFinding(BaseModel):
    dimension: CritiqueDimension
    severity: str = Field(pattern="^(info|suggestion|important)$")
    message: str = Field(min_length=1, max_length=1200)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    suggestion: str | None = Field(default=None, max_length=1200)

    @model_validator(mode="after")
    def valid_span(self) -> "CritiqueFinding":
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class EssayCritique(BaseModel):
    owner_id: UUID
    findings: list[CritiqueFinding]
    strengths: list[str]
    questions_for_writer: list[str]
    authorship_notice: str = (
        "Feedback is advisory. The writer remains responsible for the ideas, facts, "
        "wording, and final submission."
    )


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
