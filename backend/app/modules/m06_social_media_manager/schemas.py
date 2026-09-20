"""Pydantic request/response models for the Social Media Manager routes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .service import Platform


class ContentBriefIn(BaseModel):
    """Inbound content brief, e.g. "Share our ISEF project update"."""

    brief: str = Field(min_length=3, max_length=4000)
    platforms: list[Platform] | None = None


class AssetPromptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    engine: str
    prompt: str


class PlatformDraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: Platform
    format: str
    post_copy: str
    asset_prompts: list[AssetPromptOut]


class ContentPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brief: str
    status: str
    created_at: datetime
    drafts: list[PlatformDraftOut]


class ScheduleIn(BaseModel):
    """Optional requested publish time; approval is always required."""

    publish_at: datetime | None = None


class ABTestIn(BaseModel):
    platform: Platform
    variant_caption: str = Field(min_length=1, max_length=4000)


class AnalyticsIn(BaseModel):
    platform: Platform
    since_days: int = Field(default=7, ge=1, le=90)


class AnalysisReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    platform: Platform
    since_days: int
    suggestions: list[str]
    model: str
    created_at: datetime
