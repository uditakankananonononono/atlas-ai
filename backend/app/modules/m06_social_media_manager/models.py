"""Shared domain types for the Social Media Manager module.

Kept dependency-free (no adapters/scheduler/analytics imports) so every
layer of the module can import them without cycles. ``service.py``
re-exports these names for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

MODULE_ID = 6


class Platform(str, Enum):
    """Platforms covered by the spec's content generation pipeline."""

    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"


#: Format the strategist prefers per platform when the LLM gives no usable
#: answer. Mirrors the examples in the spec.
DEFAULT_FORMATS: dict[Platform, str] = {
    Platform.INSTAGRAM: "carousel",
    Platform.TWITTER: "thread",
    Platform.TIKTOK: "video_script_60s",
    Platform.LINKEDIN: "article_post",
}

#: Self-hosted asset renderers named in the spec. The module only emits
#: prompts; the render jobs themselves are wired by the integrator.
IMAGE_ENGINE = "comfyui-sdxl"
AUDIO_ENGINE = "bark-tts"

MAX_CAROUSEL_SLIDES = 5


@dataclass
class AssetPrompt:
    """A render prompt for a self-hosted asset engine (no render executed)."""

    kind: str  # "image" | "audio"
    engine: str
    prompt: str


@dataclass
class PlatformDraft:
    """Drafted content for one platform."""

    platform: Platform
    format: str
    post_copy: str
    asset_prompts: list[AssetPrompt] = field(default_factory=list)


@dataclass
class ContentPlan:
    """A strategist plan produced from one content brief."""

    id: str
    brief: str
    drafts: list[PlatformDraft]
    created_at: datetime
    status: str = "draft"  # draft -> pending_approval once scheduling is requested


@dataclass
class AnalysisReport:
    """LLM-written improvement suggestions over pulled engagement metrics."""

    id: str
    platform: Platform
    since_days: int
    suggestions: list[str]
    model: str
    created_at: datetime


class PlanNotFoundError(KeyError):
    """Raised when a caller references an unknown content plan."""
