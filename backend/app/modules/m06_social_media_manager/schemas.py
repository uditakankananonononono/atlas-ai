"""Pydantic request/response models for the Social Media Manager routes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .models import Platform


class ContentBriefIn(BaseModel):
    """Inbound content brief, e.g. "Share our ISEF project update"."""

    brief: str = Field(min_length=3, max_length=4000)
    platforms: list[Platform] | None = None


class AssetPromptOut(BaseModel):
    kind: str
    engine: str
    prompt: str


class PlatformDraftOut(BaseModel):
    platform: Platform
    format: str
    post_copy: str
    asset_prompts: list[AssetPromptOut]


class ContentPlanOut(BaseModel):
    id: str
    brief: str
    status: str
    created_at: datetime
    drafts: list[PlatformDraftOut]


class ScheduleIn(BaseModel):
    """Optional requested publish time; approval is always required."""

    publish_at: datetime | None = None
    sponsored: bool = False


class ScheduleEntryOut(BaseModel):
    id: str
    plan_id: str
    platform: Platform
    format: str
    text: str
    publish_at: datetime
    approval_id: str
    status: str
    media_urls: list[str]
    alt_texts: list[str]
    thread_chunks: list[str]
    sponsored: bool
    created_at: datetime
    decided_at: datetime | None
    published_at: datetime | None
    external_id: str | None
    external_url: str | None
    draft_only: bool
    failure: str | None


class RescheduleIn(BaseModel):
    publish_at: datetime


class AttachMediaIn(BaseModel):
    """Rendered media URLs from the asset render pipeline."""

    media_urls: list[str] = Field(min_length=1, max_length=10)
    alt_texts: list[str] = Field(default_factory=list, max_length=10)


class ComplianceIssueOut(BaseModel):
    code: str
    severity: str
    message: str


class PublishRecordOut(BaseModel):
    schedule_id: str
    platform: str
    external_id: str
    external_url: str | None
    draft_only: bool
    published_at: datetime


class ABTestIn(BaseModel):
    platform: Platform
    variant_caption: str = Field(min_length=1, max_length=4000)


class ABTestOut(BaseModel):
    id: str
    plan_id: str
    platform: Platform
    variant_a: str
    variant_b: str
    approval_id: str
    status: str
    external_id_a: str | None
    external_id_b: str | None
    metrics_a: dict[str, int]
    metrics_b: dict[str, int]
    verdict: str | None
    created_at: datetime


class ABTestStartIn(BaseModel):
    """External post ids once both approved variants are live."""

    external_id_a: str = Field(min_length=1)
    external_id_b: str = Field(min_length=1)


class ABMetricsIn(BaseModel):
    variant: str = Field(pattern="^[ab]$")
    impressions: int = Field(ge=0)
    engagement: int = Field(ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)


class ABEvaluationOut(BaseModel):
    winner: str
    rate_a: float
    rate_b: float
    z_score: float
    significant: bool
    explanation: str


class AnalyticsIn(BaseModel):
    platform: Platform
    since_days: int = Field(default=7, ge=1, le=90)


class AnalysisReportOut(BaseModel):
    id: str
    platform: Platform
    since_days: int
    suggestions: list[str]
    model: str
    created_at: datetime


class SnapshotIn(BaseModel):
    platform: Platform
    since_days: int = Field(default=1, ge=1, le=90)


class NormalizedMetricsOut(BaseModel):
    platform: str
    impressions: int
    reach: int
    engagement: int
    likes: int
    comments: int
    shares: int
    follower_count: int
    detail: dict


class SnapshotOut(BaseModel):
    id: str
    platform: Platform
    since_days: int
    metrics: NormalizedMetricsOut
    captured_at: datetime


class RevisionIn(BaseModel):
    """Human feedback applied to one platform draft."""

    feedback: str = Field(min_length=3, max_length=2000)
    sponsored: bool = False


class RevisionOut(BaseModel):
    draft: PlatformDraftOut
    findings: list[ComplianceIssueOut]


class BestTimeOut(BaseModel):
    platform: Platform
    weekday: str
    next_at: datetime
