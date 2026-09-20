"""FastAPI routes for the Social Media Manager module.

Routes live under /social-media-manager; the integrator adds the global
/api/v1 prefix and mounts this router in app.main. The service is built
lazily so no credentials, clients, or DB work happen at import time.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

from app.core.models import ApprovalRequest
from app.core.providers import ProviderError

from .schemas import ABTestIn, AnalysisReportOut, AnalyticsIn, ContentBriefIn, ContentPlanOut, ScheduleIn
from .service import OfficialSocialMetricsClient, PlanNotFoundError, Service

router = APIRouter(prefix="/social-media-manager", tags=["social-media-manager"])

_service: Service | None = None


def get_service() -> Service:
    """Lazily build the default service wiring (shared store + BYOK provider)."""
    global _service
    if _service is None:
        from app.core.approvals import approvals
        from app.core.providers import generate

        _service = Service(
            approval_store=approvals,
            generate=generate,
            metrics_client=OfficialSocialMetricsClient(
                meta_access_token=os.getenv("ATLAS_META_ACCESS_TOKEN"),
                x_bearer_token=os.getenv("ATLAS_X_BEARER_TOKEN"),
                linkedin_access_token=os.getenv("ATLAS_LINKEDIN_ACCESS_TOKEN"),
                linkedin_org_id=os.getenv("ATLAS_LINKEDIN_ORG_ID"),
            ),
        )
    return _service


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


@router.post("/plans/{plan_id}/schedule", response_model=list[ApprovalRequest], status_code=201)
def request_schedule(plan_id: str, request: ScheduleIn, service: Service = Depends(get_service)) -> object:
    """File approval requests to schedule the plan's drafts via official APIs."""
    try:
        return service.request_schedule(plan_id, request.publish_at)
    except PlanNotFoundError as error:
        raise HTTPException(status_code=404, detail="plan not found") from error


@router.post("/plans/{plan_id}/ab-tests", response_model=ApprovalRequest, status_code=201)
def request_ab_test(plan_id: str, request: ABTestIn, service: Service = Depends(get_service)) -> object:
    """Propose an A/B caption test; execution stays behind approval."""
    try:
        return service.request_ab_test(plan_id, request.platform, request.variant_caption)
    except PlanNotFoundError as error:
        raise HTTPException(status_code=404, detail="plan or platform draft not found") from error


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
