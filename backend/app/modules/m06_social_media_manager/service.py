"""Social Media Manager (module 6) - domain logic.

Implements spec module 6 ("Social Media Manager"):

- Content generation pipeline: a content brief goes to a strategist step
  (LLM via the shared BYOK provider) that picks the best format per platform
  (carousel for Instagram, thread for X/Twitter, 60s video script for TikTok,
  article post for LinkedIn) and drafts copy plus asset prompts for the
  self-hosted renderers named in the spec (ComfyUI/Stable Diffusion XL for
  images, Bark/Tortoise-TTS for audio).
- Scheduling: posts are scheduled through the official platform APIs (Meta
  Graph API, X API v2, LinkedIn API), but every schedule/publish/A-B test is
  filed with the shared approval store and held until a human confirms. This
  module never publishes, schedules, or submits anything itself.
- Analytics: engagement metrics are pulled through official platform APIs
  (read-only) and summarised by the LLM into improvement suggestions.

This file contains no FastAPI imports and performs no network or credential
work at import time. All dependencies are injected through the constructor.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol

import httpx

from app.core.models import ApprovalRequest
from app.core.providers import ProviderError

# Signature of the shared BYOK generator (app.core.providers.generate).
GenerateFn = Callable[..., Awaitable[tuple[str, str]]]

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


class ApprovalStoreProtocol(Protocol):
    """The slice of the shared approval store this module needs."""

    def put(self, item: ApprovalRequest) -> ApprovalRequest: ...


class MetricsClient(Protocol):
    """Read-only engagement metrics from an official platform API."""

    async def fetch_engagement(self, platform: Platform, since_days: int) -> dict[str, Any]: ...


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


class OfficialSocialMetricsClient:
    """Engagement reader over official platform APIs only.

    Meta Graph API (Instagram insights), X API v2 (authenticated user lookup
    with public metrics), LinkedIn API (organizational share statistics).
    Tokens are injected by the caller and are never logged or returned.
    """

    def __init__(
        self,
        *,
        meta_access_token: str | None = None,
        x_bearer_token: str | None = None,
        linkedin_access_token: str | None = None,
        linkedin_org_id: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._meta_access_token = meta_access_token
        self._x_bearer_token = x_bearer_token
        self._linkedin_access_token = linkedin_access_token
        self._linkedin_org_id = linkedin_org_id
        self._transport = transport

    async def _get(self, url: str, *, headers: dict[str, str], params: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30, transport=self._transport) as client:
            response = await client.get(url, headers=headers, params=params)
        if response.is_error:
            raise ProviderError(f"official platform API request failed ({response.status_code})")
        return response.json()

    async def fetch_engagement(self, platform: Platform, since_days: int) -> dict[str, Any]:
        """Fetch recent engagement metrics through the platform's official API."""
        if platform in {Platform.INSTAGRAM}:
            if not self._meta_access_token:
                raise ProviderError("Meta Graph API token is not configured")
            # Meta Graph API: account insights for the authenticated IG business account.
            return await self._get(
                "https://graph.facebook.com/v21.0/me/insights",
                headers={"Authorization": f"Bearer {self._meta_access_token}"},
                params={"metric": "impressions,reach,engagement", "period": "day"},
            )
        if platform == Platform.TWITTER:
            if not self._x_bearer_token:
                raise ProviderError("X API v2 bearer token is not configured")
            # X API v2: authenticated user lookup including public metrics.
            return await self._get(
                "https://api.twitter.com/2/users/me",
                headers={"Authorization": f"Bearer {self._x_bearer_token}"},
                params={"user.fields": "public_metrics"},
            )
        if platform == Platform.LINKEDIN:
            if not self._linkedin_access_token or not self._linkedin_org_id:
                raise ProviderError("LinkedIn API credentials are not configured")
            # LinkedIn API: organization share statistics.
            return await self._get(
                "https://api.linkedin.com/v2/organizationalEntityShareStatistics",
                headers={"Authorization": f"Bearer {self._linkedin_access_token}"},
                params={"q": "organizationalEntity", "organizationalEntity": f"urn:li:organization:{self._linkedin_org_id}"},
            )
        raise ProviderError(f"no official metrics API is wired for {platform.value}")


class Service:
    """Domain service for the Social Media Manager module.

    Dependencies are injected: the shared approval store, the shared BYOK
    generator, and an optional metrics client. The service never publishes,
    schedules, submits, or deletes anything; external effects are filed as
    approval requests and returned to the caller.
    """

    def __init__(
        self,
        *,
        approval_store: ApprovalStoreProtocol,
        generate: GenerateFn,
        metrics_client: MetricsClient | None = None,
        provider: str = "openai",
        model: str | None = None,
    ) -> None:
        self._approvals = approval_store
        self._generate = generate
        self._metrics = metrics_client
        self._provider = provider
        self._model = model
        # In-memory working state. Durable storage is a shared-schema concern
        # recorded in INTEGRATION.md; the module lane owns no migrations.
        self._plans: dict[str, ContentPlan] = {}
        self._reports: dict[str, AnalysisReport] = {}

    # -- content generation pipeline -------------------------------------

    async def create_plan(self, brief: str, platforms: list[Platform] | None = None) -> ContentPlan:
        """Turn a content brief into per-platform drafts.

        The strategist step asks the BYOK LLM for JSON copy per platform. If
        the provider is unavailable or returns unusable JSON, a deterministic
        fallback formats the brief per platform so the pipeline still works.
        """
        chosen = platforms or list(Platform)
        drafts = await self._strategize(brief, chosen)
        plan = ContentPlan(
            id=str(uuid.uuid4()),
            brief=brief,
            drafts=[self._with_asset_prompts(draft) for draft in drafts],
            created_at=datetime.now(timezone.utc),
        )
        self._plans[plan.id] = plan
        return plan

    def get_plan(self, plan_id: str) -> ContentPlan:
        """Return a stored plan or raise PlanNotFoundError."""
        try:
            return self._plans[plan_id]
        except KeyError as error:
            raise PlanNotFoundError(plan_id) from error

    async def _strategize(self, brief: str, platforms: list[Platform]) -> list[PlatformDraft]:
        prompt = (
            "You are a social media strategist. For the content brief below, choose the best "
            "format per platform (carousel for Instagram, thread for X/Twitter, 60-second video "
            "script for TikTok, article post for LinkedIn) and write the post copy. Reply with "
            "ONLY a JSON object mapping each platform name to an object with string fields "
            '"format" and "copy". Platforms: '
            + ", ".join(p.value for p in platforms)
            + f"\n\nBrief: {brief}"
        )
        try:
            _model, text = await self._generate(prompt, self._provider, self._model)
        except ProviderError:
            return [self._fallback_draft(brief, p) for p in platforms]
        parsed = self._parse_strategist_json(text, platforms)
        if not parsed:
            return [self._fallback_draft(brief, p) for p in platforms]
        return [
            PlatformDraft(
                platform=p,
                format=str(parsed.get(p, {}).get("format") or DEFAULT_FORMATS[p]),
                post_copy=str(parsed.get(p, {}).get("copy") or brief),
            )
            for p in platforms
        ]

    @staticmethod
    def _parse_strategist_json(text: str, platforms: list[Platform]) -> dict[Platform, dict[str, Any]]:
        """Extract the first JSON object from an LLM reply; tolerant of fences."""
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            raw = json.loads(text[start : end + 1])
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        parsed: dict[Platform, dict[str, Any]] = {}
        for platform in platforms:
            value = raw.get(platform.value)
            if isinstance(value, dict):
                parsed[platform] = value
        return parsed

    @staticmethod
    def _fallback_draft(brief: str, platform: Platform) -> PlatformDraft:
        return PlatformDraft(platform=platform, format=DEFAULT_FORMATS[platform], post_copy=brief)

    @staticmethod
    def _with_asset_prompts(draft: PlatformDraft) -> PlatformDraft:
        """Attach render prompts for the spec's self-hosted asset engines."""
        if draft.format == "carousel":
            draft.asset_prompts = [
                AssetPrompt(
                    kind="image",
                    engine=IMAGE_ENGINE,
                    prompt=f"Carousel slide {index} for an Instagram post about: {draft.post_copy[:200]}",
                )
                for index in range(1, MAX_CAROUSEL_SLIDES + 1)
            ]
        elif draft.format.startswith("video_script"):
            draft.asset_prompts = [
                AssetPrompt(kind="audio", engine=AUDIO_ENGINE, prompt=f"Narration voiceover: {draft.post_copy[:400]}")
            ]
        return draft

    # -- approval-gated external effects -----------------------------------

    def request_schedule(self, plan_id: str, publish_at: datetime | None = None) -> list[ApprovalRequest]:
        """File one approval request per platform draft to schedule the post.

        Returns the pending requests. Nothing is scheduled or published here;
        the integrator's approval executor performs the platform API call only
        after a human approves.
        """
        plan = self.get_plan(plan_id)
        requests = [
            self._file_approval(
                action_type="schedule_post",
                payload={
                    "plan_id": plan.id,
                    "platform": draft.platform.value,
                    "format": draft.format,
                    "copy": draft.post_copy,
                    "publish_at": publish_at.isoformat() if publish_at else None,
                    "api": self._official_api_name(draft.platform),
                },
            )
            for draft in plan.drafts
        ]
        plan.status = "pending_approval"
        return requests

    def request_ab_test(self, plan_id: str, platform: Platform, variant_caption: str) -> ApprovalRequest:
        """Propose an A/B caption test for one platform draft.

        Execution (posting both variants) stays behind the approval boundary.
        """
        plan = self.get_plan(plan_id)
        draft = next((d for d in plan.drafts if d.platform == platform), None)
        if draft is None:
            raise PlanNotFoundError(f"plan {plan_id} has no draft for {platform.value}")
        return self._file_approval(
            action_type="ab_test",
            payload={
                "plan_id": plan.id,
                "platform": platform.value,
                "variant_a": draft.post_copy,
                "variant_b": variant_caption,
                "api": self._official_api_name(platform),
            },
        )

    def _file_approval(self, *, action_type: str, payload: dict[str, Any]) -> ApprovalRequest:
        request = ApprovalRequest(id=str(uuid.uuid4()), module_id=MODULE_ID, action_type=action_type, payload=payload)
        return self._approvals.put(request)

    @staticmethod
    def _official_api_name(platform: Platform) -> str:
        return {
            Platform.INSTAGRAM: "meta-graph-api",
            Platform.TIKTOK: "tiktok-content-posting-api",
            Platform.TWITTER: "x-api-v2",
            Platform.LINKEDIN: "linkedin-api",
        }[platform]

    # -- analytics ---------------------------------------------------------

    async def analyze_engagement(self, platform: Platform, since_days: int = 7) -> AnalysisReport:
        """Pull official-API metrics and ask the LLM for improvement suggestions."""
        if self._metrics is None:
            raise ProviderError("no metrics client is configured for this service")
        metrics = await self._metrics.fetch_engagement(platform, since_days)
        prompt = (
            f"You are a social media analyst. Given these {platform.value} engagement metrics "
            f"from the last {since_days} days, suggest concrete improvements (best posting times, "
            "formats, caption ideas). Reply with ONLY a JSON array of short suggestion strings.\n\n"
            f"Metrics: {json.dumps(metrics)[:4000]}"
        )
        try:
            model, text = await self._generate(prompt, self._provider, self._model)
            suggestions = self._parse_suggestions(text)
        except ProviderError:
            model, suggestions = self._model or "unavailable", ["Metrics retrieved, but the LLM provider is unavailable; review the raw metrics."]
        if not suggestions:
            suggestions = ["No actionable pattern found in the pulled metrics."]
        report = AnalysisReport(
            id=str(uuid.uuid4()),
            platform=platform,
            since_days=since_days,
            suggestions=suggestions,
            model=model,
            created_at=datetime.now(timezone.utc),
        )
        self._reports[report.id] = report
        return report

    def get_report(self, report_id: str) -> AnalysisReport:
        """Return a stored analysis report or raise PlanNotFoundError."""
        try:
            return self._reports[report_id]
        except KeyError as error:
            raise PlanNotFoundError(report_id) from error

    @staticmethod
    def _parse_suggestions(text: str) -> list[str]:
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end <= start:
            return []
        try:
            raw = json.loads(text[start : end + 1])
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(raw, list):
            return []
        return [str(item) for item in raw if str(item).strip()]
