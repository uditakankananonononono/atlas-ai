"""FastAPI routes for the Calendar Intelligence module."""

import os
from collections.abc import AsyncIterator
from datetime import date, datetime

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.auth.context import TenantContext, require_tenant
from app.core.approvals import approvals
from app.core.models import ApprovalRequest
from app.core.token_crypto import TokenCipher, TokenCryptoError
from app.modules.m00_approval_center.service import (
    ApprovalNotFoundError,
    default_service,
)

from .caldav import HttpxCalDAVClient, UpstreamServiceError as CalDAVError
from .google_calendar import HttpxGoogleCalendarClient, UpstreamServiceError as GoogleError
from .schemas import (
    CalDAVSourceCreate,
    CalendarEventView,
    CalendarSourceView,
    ConflictReport,
    EventConflictView,
    GoogleSourceCreate,
    MeetingLoadReport,
    ProposedAction,
    SchedulingPrefsSchema,
    SchedulingProposalRequest,
    SchedulingProposalView,
    SchedulingTaskCreate,
    SchedulingTaskView,
    SyncResult,
    WeeklyPlanView,
)
from .service import (
    ApprovalNotGrantedError,
    ChannelVerificationError,
    Service,
    SourceNotFoundError,
)
from .sql_repository import SqlCalendarRepository

router = APIRouter(prefix="/calendar-intelligence", tags=["calendar-intelligence"])


class Module0ApprovalGate:
    """Approval-gate adapter over the shared Module 0 service."""

    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        return approvals.put(item)

    def status(self, approval_id: str) -> str:
        try:
            return default_service().get(approval_id)["status"].value
        except ApprovalNotFoundError as exc:
            raise KeyError(approval_id) from exc

    def payload(self, approval_id: str) -> dict:
        try:
            return dict(default_service().get(approval_id)["payload"])
        except ApprovalNotFoundError as exc:
            raise KeyError(approval_id) from exc


async def get_service(tenant: TenantContext = Depends(require_tenant)) -> AsyncIterator[Service]:
    try:
        cipher = TokenCipher(tenant.tenant_id)
    except TokenCryptoError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    async with httpx.AsyncClient(timeout=30) as client:
        yield Service(
            SqlCalendarRepository(tenant.tenant_id),
            Module0ApprovalGate(),
            cipher=cipher,
            google=HttpxGoogleCalendarClient(client),
            caldav=HttpxCalDAVClient(client, username="", password=""),
            webhook_base_url=os.getenv(
                "ATLAS_CALENDAR_WEBHOOK_URL",
                "https://atlas.example.com/api/v1/calendar-intelligence/webhooks/google",
            ),
        )


@router.post("/sources/google", response_model=CalendarSourceView, status_code=status.HTTP_201_CREATED)
def register_google(data: GoogleSourceCreate, service: Service = Depends(get_service)) -> CalendarSourceView:
    return service.register_google_source(data)


@router.post("/sources/caldav", response_model=CalendarSourceView, status_code=status.HTTP_201_CREATED)
def register_caldav(data: CalDAVSourceCreate, service: Service = Depends(get_service)) -> CalendarSourceView:
    return service.register_caldav_source(data)


@router.get("/sources", response_model=list[CalendarSourceView])
def list_sources(service: Service = Depends(get_service)) -> list[CalendarSourceView]:
    return service.list_sources()


@router.post("/sources/{source_id}/watch", response_model=CalendarSourceView)
async def ensure_watch(source_id: str, service: Service = Depends(get_service)) -> CalendarSourceView:
    try:
        return await service.ensure_watch(source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="source not found") from exc
    except (GoogleError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/webhooks/google", response_model=SyncResult | None)
async def google_webhook(
    x_goog_channel_id: str = Header(default=""),
    x_goog_channel_token: str = Header(default=""),
    x_goog_resource_state: str = Header(default=""),
    service: Service = Depends(get_service),
) -> SyncResult | None:
    try:
        return await service.handle_google_notification(
            channel_id=x_goog_channel_id,
            channel_token=x_goog_channel_token,
            resource_state=x_goog_resource_state,
        )
    except ChannelVerificationError as exc:
        raise HTTPException(status_code=403, detail="channel token mismatch") from exc
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="unknown channel") from exc
    except GoogleError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/sources/{source_id}/sync", response_model=SyncResult)
async def sync_source(source_id: str, service: Service = Depends(get_service)) -> SyncResult:
    try:
        return await service.sync_source(source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="source not found") from exc
    except (GoogleError, CalDAVError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/events", response_model=list[CalendarEventView])
def list_events(
    start: datetime | None = None,
    end: datetime | None = None,
    service: Service = Depends(get_service),
) -> list[CalendarEventView]:
    return service.list_events(start=start, end=end)


@router.post("/proposals", response_model=SchedulingProposalView)
def propose_scheduling_slots(
    data: SchedulingProposalRequest,
    service: Service = Depends(get_service),
) -> SchedulingProposalView:
    try:
        return service.propose_scheduling_slots(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/conflicts", response_model=list[EventConflictView])
def list_conflicts(
    start: datetime | None = None,
    end: datetime | None = None,
    minimum_overlap_minutes: int = Query(default=1, ge=1, le=24 * 60),
    across_sources_only: bool = False,
    service: Service = Depends(get_service),
) -> list[EventConflictView]:
    return service.detect_event_conflicts(
        start=start,
        end=end,
        minimum_overlap_minutes=minimum_overlap_minutes,
        across_sources_only=across_sources_only,
    )


@router.get("/prefs", response_model=SchedulingPrefsSchema)
def get_prefs(service: Service = Depends(get_service)) -> SchedulingPrefsSchema:
    return service.get_prefs()


@router.put("/prefs", response_model=SchedulingPrefsSchema)
def save_prefs(data: SchedulingPrefsSchema, service: Service = Depends(get_service)) -> SchedulingPrefsSchema:
    return service.save_prefs(data)


@router.post("/tasks", response_model=SchedulingTaskView, status_code=status.HTTP_201_CREATED)
def create_task(data: SchedulingTaskCreate, service: Service = Depends(get_service)) -> SchedulingTaskView:
    return service.create_task(data)


@router.get("/tasks", response_model=list[SchedulingTaskView])
def list_tasks(service: Service = Depends(get_service)) -> list[SchedulingTaskView]:
    return service.list_tasks()


@router.post("/plan", response_model=WeeklyPlanView, status_code=status.HTTP_201_CREATED)
def plan_week(
    week_start: date = Query(), service: Service = Depends(get_service)
) -> WeeklyPlanView:
    return service.plan_week(week_start)


@router.post("/plan/{plan_id}/propose", response_model=ProposedAction)
def propose_plan(plan_id: str, service: Service = Depends(get_service)) -> ProposedAction:
    try:
        return service.propose_plan(plan_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="plan not found") from exc


@router.post("/plan/apply/{approval_id}", response_model=WeeklyPlanView)
def apply_plan(approval_id: str, service: Service = Depends(get_service)) -> WeeklyPlanView:
    try:
        return service.apply_plan(approval_id)
    except ApprovalNotGrantedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="plan not found") from exc


@router.post("/reschedule/request")
def request_reschedule(
    data: SchedulingTaskCreate, service: Service = Depends(get_service)
) -> dict:
    report, proposal = service.request_reschedule(data)
    return {
        "conflict": report.model_dump(mode="json") if report else None,
        "proposal": proposal.model_dump(mode="json") if proposal else None,
    }


@router.post("/reschedule/apply/{approval_id}", response_model=SchedulingTaskView)
def apply_reschedule(approval_id: str, service: Service = Depends(get_service)) -> SchedulingTaskView:
    try:
        return service.apply_reschedule(approval_id)
    except ApprovalNotGrantedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/analytics/meeting-load", response_model=MeetingLoadReport)
def meeting_load(
    week_start: date = Query(), service: Service = Depends(get_service)
) -> MeetingLoadReport:
    return service.meeting_load(week_start)

from .schedule_risk import ScheduleRiskRequest, analyze_schedule_risk

@router.post('/schedule-risk')
def schedule_risk(body: ScheduleRiskRequest, tenant: TenantContext = Depends(require_tenant)):
    try:
        return {'tenant_id': tenant.tenant_id, **analyze_schedule_risk(body)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

from .live_risk_evidence import LiveRiskEvidenceRequest, verify_live_risk_evidence


@router.post('/schedule-risk/live-evidence/verify')
def live_schedule_risk_evidence(
    body: LiveRiskEvidenceRequest,
    tenant: TenantContext = Depends(require_tenant),
):
    try:
        return {'tenant_id': tenant.tenant_id, **verify_live_risk_evidence(body)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

from .asymmetric_risk_evidence import VerifySignedRiskEvidence,verify_signed_risk_evidence
@router.post('/schedule-risk/live-evidence/ed25519/verify')
def signed_live_risk_evidence(body:VerifySignedRiskEvidence,tenant:TenantContext=Depends(require_tenant)):
 try:return {'tenant_id':tenant.tenant_id,**verify_signed_risk_evidence(body)}
 except ValueError as error:raise HTTPException(422,str(error)) from error
from .risk_snapshot_persistence import PersistRiskSnapshot,persist_risk_snapshot
from .risk_snapshot_store import RiskSnapshotStore
def get_risk_snapshot_store(tenant:TenantContext=Depends(require_tenant)):return RiskSnapshotStore(tenant.tenant_id)
@router.post('/schedule-risk/live-evidence/snapshots/persist')
def persist_live_risk_snapshot(body:PersistRiskSnapshot,tenant:TenantContext=Depends(require_tenant),store=Depends(get_risk_snapshot_store)):
 try:return {'tenant_id':tenant.tenant_id,**persist_risk_snapshot(body,store)}
 except ValueError as error:raise HTTPException(409,str(error)) from error
