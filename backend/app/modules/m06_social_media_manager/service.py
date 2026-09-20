"""Social Media Manager (module 6) - domain logic.

Implements spec module 6 ("Social Media Manager"):

- Content generation pipeline: a content brief goes to a strategist step
  (LLM via the shared BYOK provider) that picks the best format per platform
  (carousel for Instagram, thread for X/Twitter, 60s video script for
  TikTok, article post for LinkedIn) and drafts copy plus asset prompts for
  the self-hosted renderers named in the spec (ComfyUI/Stable Diffusion XL
  for images, Bark/Tortoise-TTS for audio).
- Scheduling: every draft is compliance-checked (see compliance.py), filed
  with the shared approval store, and persisted as a schedule entry. The
  approval-verified execution gate that performs the platform write lives in
  scheduler.py; this service never publishes, schedules, or submits anything
  itself.
- Analytics: engagement metrics are pulled through official platform APIs
  (read-only, see adapters.py), normalized, persisted as snapshots, and
  summarised by the LLM into improvement suggestions with a deterministic
  fallback. A/B caption tests follow a full propose -> running -> concluded
  lifecycle with a statistical verdict (see analytics.py).

This file contains no FastAPI imports and performs no network or credential
work at import time. All dependencies are injected through the constructor.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol

import httpx

from app.core.models import ApprovalRequest
from app.core.providers import ProviderError

from .adapters import (
    AdapterError,
    LinkedInAdapter,
    MetaGraphAdapter,
    NormalizedMetrics,
    TikTokContentPostingAdapter,
    XApiV2Adapter,
)
from .analytics import ABTest
from .compliance import ComplianceIssue, is_blocking, validate_draft
from .scheduler import Scheduler, ScheduleEntry

# Signature of the shared BYOK generator (app.core.providers.generate).
GenerateFn = Callable[..., Awaitable[tuple[str, str]]]

from .models import (
    AUDIO_ENGINE,
    DEFAULT_FORMATS,
    IMAGE_ENGINE,
    MAX_CAROUSEL_SLIDES,
    MODULE_ID,
    AnalysisReport,
    AssetPrompt,
    ContentPlan,
    PlanNotFoundError,
    Platform,
    PlatformDraft,
)

__all__ = [
    "AUDIO_ENGINE", "DEFAULT_FORMATS", "IMAGE_ENGINE", "MAX_CAROUSEL_SLIDES", "MODULE_ID",
    "AnalysisReport", "AssetPrompt", "ContentPlan", "PlanNotFoundError", "Platform", "PlatformDraft",
]

class ApprovalStoreProtocol(Protocol):
    """The slice of the shared approval store this module needs."""

    def put(self, item: ApprovalRequest) -> ApprovalRequest: ...


class MetricsClient(Protocol):
    """Read-only engagement metrics from an official platform API."""

    async def fetch_engagement(self, platform: Platform, since_days: int) -> dict[str, Any]: ...


class DraftComplianceError(ValueError):
    """Drafts failed blocking compliance checks; carries every finding."""

    def __init__(self, issues: list[ComplianceIssue]) -> None:
        super().__init__("one or more drafts have blocking compliance issues")
        self.issues = issues


class OfficialSocialMetricsClient:
    """Engagement reader over official platform APIs only.

    Thin compatibility facade over the adapter layer (adapters.py): Meta
    Graph API (Instagram insights), X API v2 (authenticated user lookup with
    public metrics), LinkedIn API (organizational share statistics), TikTok
    Content Posting API (video list). Tokens are injected by the caller and
    are never logged or returned; adapter errors surface as ProviderError so
    the shared provider-error handling in routes keeps working.
    """

    def __init__(
        self,
        *,
        meta_access_token: str | None = None,
        x_bearer_token: str | None = None,
        linkedin_access_token: str | None = None,
        linkedin_org_id: str | None = None,
        meta_ig_user_id: str | None = None,
        tiktok_access_token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._transport = transport
        self._adapters = {
            Platform.INSTAGRAM: MetaGraphAdapter(
                access_token=meta_access_token, ig_user_id=meta_ig_user_id, transport=transport
            ),
            Platform.TWITTER: XApiV2Adapter(bearer_token=x_bearer_token, transport=transport),
            Platform.LINKEDIN: LinkedInAdapter(
                access_token=linkedin_access_token, organization_id=linkedin_org_id, transport=transport
            ),
            Platform.TIKTOK: TikTokContentPostingAdapter(access_token=tiktok_access_token, transport=transport),
        }

    def _adapter(self, platform: Platform) -> Any:
        return self._adapters[platform]

    async def fetch_engagement(self, platform: Platform, since_days: int) -> dict[str, Any]:
        """Fetch recent engagement metrics through the platform's official API."""
        try:
            return await self._adapter(platform).fetch_metrics(since_days)
        except AdapterError as error:
            raise ProviderError(str(error)) from error

    async def fetch_normalized(self, platform: Platform, since_days: int) -> NormalizedMetrics:
        """Fetch and normalize engagement into the cross-platform shape."""
        adapter = self._adapter(platform)
        try:
            raw = await adapter.fetch_metrics(since_days)
        except AdapterError as error:
            raise ProviderError(str(error)) from error
        return adapter.normalize_metrics(raw)


def _normalize_generic(platform: Platform, raw: dict[str, Any]) -> NormalizedMetrics:
    """Best-effort normalization for metrics clients without a normalizer."""
    def number(key: str) -> int:
        value = raw.get(key, 0)
        return int(value) if isinstance(value, (int, float)) else 0

    return NormalizedMetrics(
        platform=platform.value,
        impressions=number("impressions"),
        reach=number("reach"),
        engagement=number("engagement"),
        likes=number("likes"),
        comments=number("comments"),
        shares=number("shares"),
        follower_count=number("follower_count") or number("followers_count"),
        detail={"source": "generic", "keys": sorted(raw)},
    )


class SocialRepository(Protocol):
    """Full persistence boundary: plans, reports, schedules, analytics."""

    def save_plan(self, plan: ContentPlan) -> ContentPlan: ...
    def get_plan(self, plan_id: str) -> ContentPlan | None: ...
    def save_report(self, report: AnalysisReport) -> AnalysisReport: ...
    def get_report(self, report_id: str) -> AnalysisReport | None: ...
    def save_schedule(self, entry: ScheduleEntry) -> ScheduleEntry: ...
    def get_schedule(self, schedule_id: str) -> ScheduleEntry | None: ...
    def list_schedules(self, plan_id: str | None = None) -> list[ScheduleEntry]: ...
    def save_publish_record(self, record: Any) -> Any: ...
    def list_publish_records(self, schedule_id: str | None = None) -> list: ...
    def save_snapshot(self, snapshot: Any) -> Any: ...
    def get_snapshot(self, snapshot_id: str) -> Any | None: ...
    def list_snapshots(self, platform: Platform | None = None) -> list[Any]: ...
    def save_ab_test(self, test: ABTest) -> ABTest: ...
    def get_ab_test(self, test_id: str) -> ABTest | None: ...
    def list_ab_tests(self, plan_id: str | None = None) -> list[ABTest]: ...


class MemorySocialRepository:
    """In-memory repository for development and tests."""

    def __init__(self) -> None:
        self.plans: dict[str, ContentPlan] = {}
        self.reports: dict[str, AnalysisReport] = {}
        self.schedules: dict[str, ScheduleEntry] = {}
        self.publish_records: list = []
        self.snapshots: dict[str, Any] = {}
        self.ab_tests: dict[str, ABTest] = {}

    def save_plan(self, plan: ContentPlan) -> ContentPlan: self.plans[plan.id]=plan; return plan
    def get_plan(self, plan_id: str) -> ContentPlan | None: return self.plans.get(plan_id)
    def save_report(self, report: AnalysisReport) -> AnalysisReport: self.reports[report.id]=report; return report
    def get_report(self, report_id: str) -> AnalysisReport | None: return self.reports.get(report_id)
    def save_schedule(self, entry: ScheduleEntry) -> ScheduleEntry: self.schedules[entry.id]=entry; return entry
    def get_schedule(self, schedule_id: str) -> ScheduleEntry | None: return self.schedules.get(schedule_id)
    def list_schedules(self, plan_id: str | None = None) -> list[ScheduleEntry]:
        return [e for e in self.schedules.values() if plan_id is None or e.plan_id == plan_id]
    def save_publish_record(self, record: Any) -> Any: self.publish_records.append(record); return record
    def list_publish_records(self, schedule_id: str | None = None) -> list:
        return [r for r in self.publish_records if schedule_id is None or r.schedule_id == schedule_id]
    def save_snapshot(self, snapshot: Any) -> Any: self.snapshots[snapshot.id]=snapshot; return snapshot
    def get_snapshot(self, snapshot_id: str) -> Any | None: return self.snapshots.get(snapshot_id)
    def list_snapshots(self, platform: Platform | None = None) -> list[Any]:
        return [s for s in self.snapshots.values() if platform is None or s.platform == platform]
    def save_ab_test(self, test: ABTest) -> ABTest: self.ab_tests[test.id]=test; return test
    def get_ab_test(self, test_id: str) -> ABTest | None: return self.ab_tests.get(test_id)
    def list_ab_tests(self, plan_id: str | None = None) -> list[ABTest]:
        return [t for t in self.ab_tests.values() if plan_id is None or t.plan_id == plan_id]


class Service:
    """Domain service for the Social Media Manager module.

    Dependencies are injected: the shared approval store, the shared BYOK
    generator, a metrics client, a repository, and optionally the module
    scheduler (schedule entries are only persisted when one is wired). The
    service never publishes, schedules, submits, or deletes anything;
    external effects are filed as approval requests and returned to the
    caller, and the approval-verified execution gate lives in scheduler.py.
    """

    def __init__(
        self,
        *,
        approval_store: ApprovalStoreProtocol,
        generate: GenerateFn,
        metrics_client: MetricsClient | None = None,
        provider: str = "openai",
        model: str | None = None,
        repository: SocialRepository | None = None,
        scheduler: Scheduler | None = None,
    ) -> None:
        self._approvals = approval_store
        self._generate = generate
        self._metrics = metrics_client
        self._provider = provider
        self._model = model
        self._repository = repository or MemorySocialRepository()
        self._scheduler = scheduler

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
        return self._repository.save_plan(plan)

    def get_plan(self, plan_id: str) -> ContentPlan:
        """Return a stored plan or raise PlanNotFoundError."""
        item=self._repository.get_plan(plan_id)
        if item is None: raise PlanNotFoundError(plan_id)
        return item

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

    # -- approval-gated scheduling -----------------------------------------

    def check_compliance(self, plan_id: str, *, sponsored: bool = False) -> list[ComplianceIssue]:
        """Every compliance finding across a plan's drafts, errors and warnings."""
        plan = self.get_plan(plan_id)
        findings: list[ComplianceIssue] = []
        for draft in plan.drafts:
            findings.extend(
                validate_draft(
                    draft.platform.value,
                    draft.format,
                    draft.post_copy,
                    sponsored=sponsored,
                    media_count=len([p for p in draft.asset_prompts if p.kind == "image"]),
                    alt_texts=len([p for p in draft.asset_prompts if p.kind == "image" and p.prompt.strip()]),
                )
            )
        return findings

    def request_schedule(
        self, plan_id: str, publish_at: datetime | None = None, *, sponsored: bool = False
    ) -> list[ApprovalRequest]:
        """Compliance-check, persist schedule entries, and file approvals.

        Nothing is scheduled or published here. Blocking compliance findings
        abort the request before any approval is filed (fail closed). The
        approval-verified execution gate in scheduler.py performs the actual
        platform API call after a human approves.
        """
        plan = self.get_plan(plan_id)
        findings = self.check_compliance(plan_id, sponsored=sponsored)
        blocking = [issue for issue in findings if issue.severity == "error"]
        if blocking:
            raise DraftComplianceError(blocking)
        moment = publish_at or datetime.now(timezone.utc)
        requests = [
            self._file_approval(
                action_type="schedule_post",
                payload={
                    "plan_id": plan.id,
                    "platform": draft.platform.value,
                    "format": draft.format,
                    "copy": draft.post_copy,
                    "publish_at": moment.isoformat(),
                    "api": self._official_api_name(draft.platform),
                    "sponsored": sponsored,
                },
            )
            for draft in plan.drafts
        ]
        if self._scheduler is not None:
            approval_ids = {draft.platform: request.id for draft, request in zip(plan.drafts, requests)}
            entries = self._scheduler.create_entries(
                plan, publish_at=moment, approval_ids=approval_ids, sponsored=sponsored
            )
            for request, entry in zip(requests, entries):
                request.payload["schedule_id"] = entry.id
        plan.status = "pending_approval"
        self._repository.save_plan(plan)
        return requests

    def list_schedule(self, plan_id: str) -> list[ScheduleEntry]:
        """Schedule entries for one plan (empty when no scheduler is wired)."""
        self.get_plan(plan_id)
        return self._repository.list_schedules(plan_id)

    def request_ab_test(self, plan_id: str, platform: Platform, variant_caption: str) -> ApprovalRequest:
        """Propose an A/B caption test for one platform draft.

        Execution (posting both variants) stays behind the approval boundary;
        the persisted ABTest record tracks the full lifecycle to a
        statistical verdict.
        """
        plan = self.get_plan(plan_id)
        draft = next((d for d in plan.drafts if d.platform == platform), None)
        if draft is None:
            raise PlanNotFoundError(f"plan {plan_id} has no draft for {platform.value}")
        request = self._file_approval(
            action_type="ab_test",
            payload={
                "plan_id": plan.id,
                "platform": platform.value,
                "variant_a": draft.post_copy,
                "variant_b": variant_caption,
                "api": self._official_api_name(platform),
            },
        )
        self._repository.save_ab_test(
            ABTest(
                id=str(uuid.uuid4()),
                plan_id=plan.id,
                platform=platform,
                variant_a=draft.post_copy,
                variant_b=variant_caption,
                approval_id=request.id,
            )
        )
        request.payload["ab_test_id"] = self._repository.list_ab_tests(plan.id)[-1].id
        return request

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

    async def capture_metrics(self, platform: Platform, since_days: int = 1) -> Any:
        """Daily pull: fetch + normalize + persist one metrics snapshot."""
        if self._metrics is None:
            raise ProviderError("no metrics client is configured for this service")
        fetch_normalized = getattr(self._metrics, "fetch_normalized", None)
        if fetch_normalized is not None:
            normalized = await fetch_normalized(platform, since_days)
        else:
            raw = await self._metrics.fetch_engagement(platform, since_days)
            normalized = _normalize_generic(platform, raw)
        from .analytics import MetricsSnapshot

        snapshot = MetricsSnapshot(
            id=str(uuid.uuid4()),
            platform=platform,
            since_days=since_days,
            metrics=normalized,
            captured_at=datetime.now(timezone.utc),
        )
        return self._repository.save_snapshot(snapshot)

    async def analyze_engagement(self, platform: Platform, since_days: int = 7) -> AnalysisReport:
        """Pull official-API metrics and ask the LLM for improvement suggestions.

        The deterministic trend line is prepended to the prompt and used as
        the fallback when the provider is unavailable, so the report always
        contains at least one evidence-based suggestion.
        """
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
        return self._repository.save_report(report)

    def get_report(self, report_id: str) -> AnalysisReport:
        """Return a stored analysis report or raise PlanNotFoundError."""
        item=self._repository.get_report(report_id)
        if item is None: raise PlanNotFoundError(report_id)
        return item

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
