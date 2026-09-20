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
from .schemas import (
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
        for request in self._approvals.list():
            if request.id == approval_id:
                status = request.status
                return getattr(status, "value", str(status))
        return None


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
