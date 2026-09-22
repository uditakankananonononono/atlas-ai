"""FastAPI routes for the Social Media Manager module.

Routes live under /social-media-manager; the integrator adds the global
/api/v1 prefix and mounts this router in app.main. Services are built
lazily so no credentials, clients, or DB work happen at import time.

The execute-due endpoint is the module's approval-verified effect gate: it
is wired for the integrator's worker/beat process and re-verifies every
approval decision against the shared Approval Center before any platform
write. All other routes only draft, file approvals, or read state.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

from app.core.models import ApprovalRequest
from app.auth.context import TenantContext, require_tenant
from app.core.providers import ProviderError

from .adapters import PlatformCredentials, build_adapter
from .analytics import ABTestStateError, ABTestNotFoundError, Analytics, SnapshotNotFoundError
from .scheduler import (
    Scheduler,
    ScheduleNotFoundError,
    ScheduleStateError,
)
from .models import Platform
from .creative import CREATIVE_SPECS
from .marketing import ARTIFACT_SPECS, ArtifactParseError, MarketingArtifact
from .schemas import (
    ArtifactIn,
    ArtifactOut,
    BestTimeOut,
    CopywritingIn,
    CreativeSpecIn,
    CopywritingOut,
    EditorialCalendarIn,
    SampleSizeIn,
    ABMetricsIn,
    ABTestIn,
    ABTestOut,
    ABTestStartIn,
    ABEvaluationOut,
    AnalysisReportOut,
    AnalyticsIn,
    AttachMediaIn,
    ComplianceIssueOut,
    ContentBriefIn,
    ContentPlanOut,
    PublishRecordOut,
    RescheduleIn,
    RevisionIn,
    RevisionOut,
    ScheduleEntryOut,
    ScheduleIn,
    SnapshotIn,
    SnapshotOut,
)
from .service import (
    DraftComplianceError,
    OfficialSocialMetricsClient,
    PlanNotFoundError,
    Service,
)
from .sql_repository import SqlSocialRepository

router = APIRouter(prefix="/social-media-manager", tags=["social-media-manager"])


def _env_credentials() -> PlatformCredentials:
    """Phase-1 stopgap: tenant platform tokens from env (see INTEGRATION.md)."""
    return PlatformCredentials(
        meta_access_token=os.getenv("ATLAS_META_ACCESS_TOKEN"),
        meta_ig_user_id=os.getenv("ATLAS_META_IG_USER_ID"),
        x_bearer_token=os.getenv("ATLAS_X_BEARER_TOKEN"),
        linkedin_access_token=os.getenv("ATLAS_LINKEDIN_ACCESS_TOKEN"),
        linkedin_org_id=os.getenv("ATLAS_LINKEDIN_ORG_ID"),
        tiktok_access_token=os.getenv("ATLAS_TIKTOK_ACCESS_TOKEN"),
    )


class _ApprovalCenterLookup:
    """Decision lookup over the shared Approval Center facade."""

    def __init__(self) -> None:
        from app.core.approvals import approvals

        self._approvals = approvals

    def status_of(self, approval_id: str) -> str | None:
        request = self._approvals.get(approval_id)
        if request is None:
            return None
        status = request.status
        return getattr(status, "value", str(status))


class _EnvAdapterFactory:
    """Builds official adapters from the tenant's env-injected credentials."""

    def for_platform(self, platform) -> object:
        return build_adapter(platform.value, _env_credentials())


def get_repository(tenant: TenantContext = Depends(require_tenant)) -> SqlSocialRepository:
    return SqlSocialRepository(tenant.tenant_id)


def get_scheduler(repository: SqlSocialRepository = Depends(get_repository)) -> Scheduler:
    return Scheduler(
        repository=repository,
        decisions=_ApprovalCenterLookup(),
        adapter_factory=_EnvAdapterFactory(),
    )


def get_analytics(repository: SqlSocialRepository = Depends(get_repository)) -> Analytics:
    return Analytics(repository=repository)


def get_service(
    tenant: TenantContext = Depends(require_tenant),
    repository: SqlSocialRepository = Depends(get_repository),
    scheduler: Scheduler = Depends(get_scheduler),
) -> Service:
    """Build a tenant-bound durable service."""
    from app.core.approvals import approvals
    from app.core.providers import generate

    credentials = _env_credentials()
    return Service(
        approval_store=approvals,
        generate=generate,
        repository=repository,
        scheduler=scheduler,
        tenant_id=tenant.tenant_id,
        metrics_client=OfficialSocialMetricsClient(
            meta_access_token=credentials.meta_access_token,
            meta_ig_user_id=credentials.meta_ig_user_id,
            x_bearer_token=credentials.x_bearer_token,
            linkedin_access_token=credentials.linkedin_access_token,
            linkedin_org_id=credentials.linkedin_org_id,
            tiktok_access_token=credentials.tiktok_access_token,
        ),
    )


# -- content plans -------------------------------------------------------------


@router.post("/plans", response_model=ContentPlanOut, status_code=201)
async def create_plan(request: ContentBriefIn, service: Service = Depends(get_service)) -> object:
    """Create a content plan from a brief (drafts only, nothing published)."""
    return await service.create_plan(request.brief, request.platforms)


@router.get("/plans/{plan_id}", response_model=ContentPlanOut)
def get_plan(plan_id: str, service: Service = Depends(get_service)) -> object:
    try:
        return service.get_plan(plan_id)
    except PlanNotFoundError as error:
        raise HTTPException(status_code=404, detail="plan not found") from error


@router.get("/plans/{plan_id}/compliance", response_model=list[ComplianceIssueOut])
def check_compliance(plan_id: str, sponsored: bool = False, service: Service = Depends(get_service)) -> object:
    """Every compliance finding across a plan's drafts, errors and warnings."""
    try:
        return service.check_compliance(plan_id, sponsored=sponsored)
    except PlanNotFoundError as error:
        raise HTTPException(status_code=404, detail="plan not found") from error


@router.post("/plans/{plan_id}/schedule", response_model=list[ApprovalRequest], status_code=201)
def request_schedule(plan_id: str, request: ScheduleIn, service: Service = Depends(get_service)) -> object:
    """Compliance-check drafts, persist schedule entries, file approvals."""
    try:
        return service.request_schedule(plan_id, request.publish_at, sponsored=request.sponsored)
    except PlanNotFoundError as error:
        raise HTTPException(status_code=404, detail="plan not found") from error
    except DraftComplianceError as error:
        raise HTTPException(
            status_code=422,
            detail=[{"code": i.code, "severity": i.severity, "message": i.message} for i in error.issues],
        ) from error


@router.get("/plans/{plan_id}/schedule", response_model=list[ScheduleEntryOut])
def list_schedule(plan_id: str, service: Service = Depends(get_service)) -> object:
    try:
        return service.list_schedule(plan_id)
    except PlanNotFoundError as error:
        raise HTTPException(status_code=404, detail="plan not found") from error


@router.post("/plans/{plan_id}/ab-tests", response_model=ApprovalRequest, status_code=201)
def request_ab_test(plan_id: str, request: ABTestIn, service: Service = Depends(get_service)) -> object:
    """Propose an A/B caption test; execution stays behind approval."""
    try:
        return service.request_ab_test(plan_id, request.platform, request.variant_caption)
    except PlanNotFoundError as error:
        raise HTTPException(status_code=404, detail="plan or platform draft not found") from error


@router.post("/plans/{plan_id}/drafts/{platform}/revision", response_model=RevisionOut)
async def revise_draft(plan_id: str, platform: Platform, request: RevisionIn, service: Service = Depends(get_service)) -> object:
    """Rewrite one draft from human feedback; blocking findings keep the old copy."""
    try:
        draft, findings = await service.revise_draft(plan_id, platform, request.feedback, sponsored=request.sponsored)
        return {"draft": draft, "findings": findings}
    except PlanNotFoundError as error:
        raise HTTPException(status_code=404, detail="plan or platform draft not found") from error
    except DraftComplianceError as error:
        raise HTTPException(
            status_code=422,
            detail=[{"code": i.code, "severity": i.severity, "message": i.message} for i in error.issues],
        ) from error
    except ProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/metrics/best-time/{platform}", response_model=BestTimeOut)
def best_publish_time(platform: Platform, service: Service = Depends(get_service)) -> object:
    """Next occurrence of the platform's best-performing weekday (Meta series)."""
    suggestion = service.suggest_publish_time(platform)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="not enough daily metrics for a recommendation")
    return {"platform": platform, "weekday": suggestion.strftime("%A"), "next_at": suggestion}


# -- rows 400-426: marketing analyses and plans (draft/review-first) -------


def _artifact_out(artifact: MarketingArtifact) -> dict:
    return {
        "id": artifact.id, "row": artifact.row, "kind": artifact.kind, "title": artifact.title,
        "status": artifact.status, "provenance": artifact.provenance, "model": artifact.model,
        "sections": artifact.sections, "created_at": artifact.created_at,
    }


@router.post("/marketing/sample-size", response_model=ArtifactOut)
def sample_size(request: SampleSizeIn, service: Service = Depends(get_service)) -> object:
    """Row 400: deterministic two-proportion A/B power calculation."""
    try:
        return _artifact_out(service.marketing.sample_size(
            request.baseline_rate, request.minimum_detectable_effect,
            alpha=request.alpha, power=request.power,
        ))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


async def _run_artifact(slug: str, request: ArtifactIn, service: Service) -> dict:
    try:
        artifact = await service.marketing.generate(
            slug,
            business=request.business,
            product=request.product,
            audience=request.audience,
            goals=request.goals,
            facts=request.facts,
            contacts=request.contacts,
            provided_metrics=request.provided_metrics,
        )
        return _artifact_out(artifact)
    except ArtifactParseError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def _register_artifact_route(slug: str) -> None:
    """Mount POST /marketing/<slug> for one registry row (401-426)."""

    async def handler(request: ArtifactIn, service: Service = Depends(get_service)) -> object:
        return await _run_artifact(slug, request, service)

    handler.__name__ = f"marketing_{slug.replace('-', '_')}"
    router.add_api_route(
        f"/marketing/{slug}", handler, methods=["POST"],
        response_model=ArtifactOut, name=handler.__name__,
    )


for _slug in ARTIFACT_SPECS:
    if _slug not in ("copywriting", "editorial-calendar"):
        _register_artifact_route(_slug)


@router.post("/marketing/copywriting", response_model=CopywritingOut)
async def marketing_copywriting(request: CopywritingIn, service: Service = Depends(get_service)) -> object:
    """Row 407: persuasive copy through the module compliance gate (never published)."""
    try:
        artifact, findings = await service.marketing.draft_copy(
            brief=request.brief, platform=request.platform, format=request.format,
            voice=request.voice, sponsored=request.sponsored,
            media_count=request.media_count, alt_texts=request.alt_texts,
        )
        return {"artifact": _artifact_out(artifact), "findings": findings}
    except ArtifactParseError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except DraftComplianceError as error:
        raise HTTPException(
            status_code=422,
            detail=[{"code": i.code, "severity": i.severity, "message": i.message} for i in error.issues],
        ) from error
    except ProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/marketing/editorial-calendar", response_model=ArtifactOut)
async def marketing_editorial_calendar(request: EditorialCalendarIn, service: Service = Depends(get_service)) -> object:
    """Row 409: dated draft calendar entries; scheduling stays approval-gated elsewhere."""
    try:
        artifact = await service.marketing.editorial_calendar(
            business=request.business, themes=request.themes, start_date=request.start_date,
            weeks=request.weeks, posts_per_week=request.posts_per_week,
        )
        return _artifact_out(artifact)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"invalid calendar input: {error}") from error
    except ArtifactParseError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/marketing/artifacts", response_model=list[ArtifactOut])
def list_marketing_artifacts(kind: str | None = None, service: Service = Depends(get_service)) -> object:
    """List stored draft artifacts, optionally filtered by kind."""
    return [_artifact_out(a) for a in service.marketing.list_artifacts(kind)]


# -- rows 281-305: creative specifications (review-only, never rendered) -----


async def _run_creative(slug: str, request: CreativeSpecIn, service: Service) -> dict:
    try:
        artifact = await service.creative.generate(
            slug,
            business=request.business,
            subject=request.subject,
            goals=request.goals,
            facts=request.facts,
            constraints=request.constraints,
        )
        return _artifact_out(artifact)
    except ArtifactParseError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def _register_creative_route(slug: str) -> None:
    """Mount POST /creative/<slug> for one registry row (281-305)."""

    async def handler(request: CreativeSpecIn, service: Service = Depends(get_service)) -> object:
        return await _run_creative(slug, request, service)

    handler.__name__ = f"creative_{slug.replace('-', '_')}"
    router.add_api_route(
        f"/creative/{slug}", handler, methods=["POST"],
        response_model=ArtifactOut, name=handler.__name__,
    )




from .creative_semantics_281_287 import CreativeSemanticError,validate as validate_creative_281_287
@router.post("/creative/{slug}/semantic-validate")
def creative_semantic_validate_281_287(slug:str,payload:dict):
    if slug not in CREATIVE_SPECS or CREATIVE_SPECS[slug].row>287:raise HTTPException(404,"semantic validator not available")
    try:return {"row":CREATIVE_SPECS[slug].row,"slug":slug,"invariants":validate_creative_281_287(slug,payload)}
    except CreativeSemanticError as error:raise HTTPException(422,str(error)) from error

for _slug in CREATIVE_SPECS:
    _register_creative_route(_slug)


# -- scheduler (approval-verified execution gate) -------------------------------


@router.get("/schedules", response_model=list[ScheduleEntryOut])
def list_schedules(scheduler: Scheduler = Depends(get_scheduler)) -> object:
    return scheduler.list_entries()


@router.get("/schedules/{schedule_id}", response_model=ScheduleEntryOut)
def get_schedule(schedule_id: str, scheduler: Scheduler = Depends(get_scheduler)) -> object:
    try:
        return scheduler.get_entry(schedule_id)
    except ScheduleNotFoundError as error:
        raise HTTPException(status_code=404, detail="schedule entry not found") from error


@router.post("/schedules/{schedule_id}/cancel", response_model=ScheduleEntryOut)
def cancel_schedule(schedule_id: str, scheduler: Scheduler = Depends(get_scheduler)) -> object:
    try:
        return scheduler.cancel(schedule_id)
    except ScheduleNotFoundError as error:
        raise HTTPException(status_code=404, detail="schedule entry not found") from error
    except ScheduleStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/schedules/{schedule_id}/reschedule", response_model=ScheduleEntryOut)
def reschedule_schedule(schedule_id: str, request: RescheduleIn, scheduler: Scheduler = Depends(get_scheduler)) -> object:
    try:
        return scheduler.reschedule(schedule_id, request.publish_at)
    except ScheduleNotFoundError as error:
        raise HTTPException(status_code=404, detail="schedule entry not found") from error
    except ScheduleStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/schedules/{schedule_id}/media", response_model=ScheduleEntryOut)
def attach_media(schedule_id: str, request: AttachMediaIn, scheduler: Scheduler = Depends(get_scheduler)) -> object:
    """Attach rendered media URLs from the asset render pipeline."""
    try:
        return scheduler.attach_media(schedule_id, request.media_urls, request.alt_texts)
    except ScheduleNotFoundError as error:
        raise HTTPException(status_code=404, detail="schedule entry not found") from error
    except ScheduleStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/schedules/sync", response_model=list[ScheduleEntryOut])
def sync_decisions(scheduler: Scheduler = Depends(get_scheduler)) -> object:
    """Fold Approval Center decisions into entry state (worker entry point)."""
    return scheduler.sync_decisions()


@router.post("/schedules/execute-due", response_model=list[PublishRecordOut])
def execute_due(scheduler: Scheduler = Depends(get_scheduler)) -> object:
    """The effect gate: publish due entries whose approval is still approved."""
    return scheduler.execute_due()


@router.get("/schedules/{schedule_id}/publishes", response_model=list[PublishRecordOut])
def list_publishes(schedule_id: str, scheduler: Scheduler = Depends(get_scheduler)) -> object:
    return scheduler.list_publish_records(schedule_id)


# -- analytics --------------------------------------------------------------------


@router.post("/metrics/snapshots", response_model=SnapshotOut, status_code=201)
async def capture_snapshot(request: SnapshotIn, service: Service = Depends(get_service)) -> object:
    """Daily pull: fetch + normalize + persist one metrics snapshot."""
    try:
        return await service.capture_metrics(request.platform, request.since_days)
    except ProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/metrics/snapshots", response_model=list[SnapshotOut])
def list_snapshots(platform: str | None = None, analytics: Analytics = Depends(get_analytics)) -> object:
    from .models import Platform

    return analytics.list_snapshots(Platform(platform) if platform else None)


@router.get("/metrics/trend/{platform}", response_model=dict)
def metrics_trend(platform: str, analytics: Analytics = Depends(get_analytics)) -> object:
    from .models import Platform

    trend = analytics.trend(Platform(platform))
    if trend is None:
        raise HTTPException(status_code=404, detail="not enough snapshots for a trend")
    return trend


@router.post("/analytics/reports", response_model=AnalysisReportOut, status_code=201)
async def create_analysis(request: AnalyticsIn, service: Service = Depends(get_service)) -> object:
    """Pull official-API engagement metrics and return LLM suggestions."""
    try:
        return await service.analyze_engagement(request.platform, request.since_days)
    except ProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/analytics/reports/{report_id}", response_model=AnalysisReportOut)
def get_analysis(report_id: str, service: Service = Depends(get_service)) -> object:
    try:
        return service.get_report(report_id)
    except PlanNotFoundError as error:
        raise HTTPException(status_code=404, detail="report not found") from error


# -- A/B tests ----------------------------------------------------------------------


@router.get("/ab-tests/{test_id}", response_model=ABTestOut)
def get_ab_test(test_id: str, analytics: Analytics = Depends(get_analytics)) -> object:
    try:
        return analytics.get_ab_test(test_id)
    except ABTestNotFoundError as error:
        raise HTTPException(status_code=404, detail="A/B test not found") from error


@router.post("/ab-tests/{test_id}/start", response_model=ABTestOut)
def start_ab_test(test_id: str, request: ABTestStartIn, analytics: Analytics = Depends(get_analytics)) -> object:
    """Mark a proposed test running once both approved variants are posted."""
    try:
        return analytics.start_ab_test(analytics.get_ab_test(test_id), request.external_id_a, request.external_id_b)
    except ABTestNotFoundError as error:
        raise HTTPException(status_code=404, detail="A/B test not found") from error
    except ABTestStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/ab-tests/{test_id}/metrics", response_model=ABTestOut)
def record_ab_metrics(test_id: str, request: ABMetricsIn, analytics: Analytics = Depends(get_analytics)) -> object:
    try:
        return analytics.record_variant_metrics(
            test_id,
            request.variant,
            {"impressions": request.impressions, "engagement": request.engagement,
             "likes": request.likes, "comments": request.comments, "shares": request.shares},
        )
    except ABTestNotFoundError as error:
        raise HTTPException(status_code=404, detail="A/B test not found") from error


@router.post("/ab-tests/{test_id}/conclude", response_model=ABEvaluationOut)
def conclude_ab_test(test_id: str, analytics: Analytics = Depends(get_analytics)) -> object:
    """Evaluate a running test with a two-proportion z-test and persist the verdict."""
    try:
        _test, evaluation = analytics.conclude_ab_test(test_id)
        return evaluation
    except ABTestNotFoundError as error:
        raise HTTPException(status_code=404, detail="A/B test not found") from error
    except ABTestStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

@router.post('/technical-67-75/{row_id}')
def technical_67_75(row_id:int,payload:dict):
    from .technical_67_75 import run
    try:return run(row_id,payload)
    except (ValueError,TypeError,KeyError) as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
