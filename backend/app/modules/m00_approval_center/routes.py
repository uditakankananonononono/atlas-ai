"""HTTP surface for the Human Approval Center.

Routes live under /approval-center; the integrator mounts this router with
the global /api/v1 prefix. All domain behavior is in service.py.
"""
import asyncio
import json
import queue

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth.context import TenantContext, require_admin, require_tenant, require_worker
from fastapi.responses import StreamingResponse

from app.core.models import ApprovalStatus
from app.modules.m00_approval_center import schemas
from app.modules.m00_approval_center.service import (
    ApprovalConflictError,
    ApprovalNotFoundError,
    Service,
    default_service,
)

router = APIRouter(prefix="/approval-center", tags=["approval-center"])

SSE_HEARTBEAT_SECONDS = 15.0


def get_service() -> Service:
    """FastAPI dependency: the process-wide Approval Center service."""
    return default_service()


def _not_found(error: ApprovalNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail="approval not found")


@router.post("/requests", response_model=schemas.ApprovalView, status_code=201)
def submit_request(body: schemas.ApprovalSubmit, service: Service = Depends(get_service), tenant: TenantContext = Depends(require_tenant)) -> dict:
    """Queue a gated action for human approval. Nothing executes here."""
    try:
        return service.submit(
            module_id=body.module_id,
            action_type=body.action_type,
            payload=body.payload,
            user_id=tenant.tenant_id,
            ttl_seconds=body.ttl_seconds,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/requests", response_model=list[schemas.ApprovalView])
def list_requests(
    status: ApprovalStatus | None = None,
    module_id: int | None = None,
    user_id: str | None = None,
    limit: int = 100,
    service: Service = Depends(get_service),
    tenant: TenantContext = Depends(require_tenant),
) -> list[dict]:
    """List approval requests newest first, scoped to the authenticated tenant."""
    if user_id is not None and user_id != tenant.tenant_id:
        raise HTTPException(status_code=403, detail="cross-tenant approval access denied")
    return service.list(status=status, module_id=module_id, user_id=tenant.tenant_id, limit=limit)


@router.get("/requests/{approval_id}", response_model=schemas.ApprovalView)
def get_request(approval_id: str, service: Service = Depends(get_service), tenant: TenantContext = Depends(require_tenant)) -> dict:
    """Fetch one request; overdue pending requests report as expired."""
    try:
        view = service.get(approval_id)
        if view["user_id"] != tenant.tenant_id:
            raise ApprovalNotFoundError(approval_id)
        return view
    except ApprovalNotFoundError as error:
        raise _not_found(error) from error


@router.post("/requests/{approval_id}/decision", response_model=schemas.ApprovalView)
def decide_request(
    approval_id: str,
    body: schemas.ApprovalDecisionIn,
    service: Service = Depends(get_service),
    tenant: TenantContext = Depends(require_tenant),
) -> dict:
    """Record the authenticated human decision. Final: re-deciding returns 409."""
    try:
        current = service.get(approval_id)
        if current["user_id"] != tenant.tenant_id:
            raise ApprovalNotFoundError(approval_id)
        return service.decide(approval_id, ApprovalStatus(body.decision), tenant.actor_id)
    except ApprovalNotFoundError as error:
        raise _not_found(error) from error
    except ApprovalConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/requests/{approval_id}/audit", response_model=list[schemas.ApprovalEventView])
def audit_request(approval_id: str, service: Service = Depends(get_service), tenant: TenantContext = Depends(require_tenant)) -> list[dict]:
    """Return the immutable event log for one request."""
    try:
        current = service.get(approval_id)
        if current["user_id"] != tenant.tenant_id:
            raise ApprovalNotFoundError(approval_id)
        return service.audit(approval_id)
    except ApprovalNotFoundError as error:
        raise _not_found(error) from error


@router.post("/expire", response_model=schemas.ExpireResult)
def expire_overdue(service: Service = Depends(get_service), worker: TenantContext = Depends(require_worker)) -> dict:
    """Sweep pending requests past their deadline into expired."""
    return {"expired_ids": service.expire_overdue()}


@router.get("/events")
async def stream_events(response: Response, service: Service = Depends(get_service), tenant: TenantContext = Depends(require_tenant)) -> StreamingResponse:
    """Server-Sent Events feed of approval requests, decisions, and expiries."""
    subscriber = service.broadcaster.subscribe()

    async def event_stream():
        try:
            while True:
                try:
                    event = await asyncio.to_thread(subscriber.get, True, SSE_HEARTBEAT_SECONDS)
                    approval = event.get("approval") if isinstance(event, dict) else None
                    if isinstance(approval, dict) and approval.get("user_id") != tenant.tenant_id:
                        continue
                    if isinstance(event, dict) and event.get("type") == "approval_expired":
                        try:
                            expired = service.get(str(event.get("approval_id", "")))
                        except ApprovalNotFoundError:
                            continue
                        if expired.get("user_id") != tenant.tenant_id:
                            continue
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        finally:
            service.broadcaster.unsubscribe(subscriber)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@router.put("/policies/{policy_id}", response_model=schemas.PolicyView)
def upsert_policy(policy_id: str, body: schemas.PolicyUpsert,
                  service: Service = Depends(get_service),
                  admin: TenantContext = Depends(require_admin)) -> dict:
    if policy_id != body.id:
        raise HTTPException(status_code=422, detail="path policy id must match body id")
    return service.upsert_policy(policy_id=body.id, name=body.name,
        action_pattern=body.action_pattern, effect=body.effect, actor=admin.actor_id,
        module_id=body.module_id, priority=body.priority, enabled=body.enabled,
        conditions=body.conditions, review_ttl_seconds=body.review_ttl_seconds)


@router.get("/policies", response_model=list[schemas.PolicyView])
def list_policies(enabled_only: bool = False, service: Service = Depends(get_service), admin: TenantContext = Depends(require_admin)) -> list[dict]:
    return service.list_policies(enabled_only=enabled_only)


@router.post("/gate", response_model=schemas.GateResult)
def check_gate(body: schemas.GateCheck, service: Service = Depends(get_service), tenant: TenantContext = Depends(require_tenant)) -> dict:
    try:
        return service.gate(module_id=body.module_id, action_type=body.action_type,
            payload=body.payload, context=body.context, user_id=tenant.tenant_id,
            idempotency_key=body.idempotency_key)
    except ApprovalConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/requests/{approval_id}/consume", response_model=schemas.EffectPermit)
def consume_effect(approval_id: str, body: schemas.EffectConsume,
                   service: Service = Depends(get_service),
                   tenant: TenantContext = Depends(require_tenant)) -> dict:
    try:
        current = service.get(approval_id)
        if current["user_id"] != tenant.tenant_id:
            raise ApprovalNotFoundError(approval_id)
        return service.consume_effect(approval_id, module_id=body.module_id,
            action_type=body.action_type, payload=body.payload, user_id=tenant.tenant_id,
            effect_id=body.effect_id, actor=tenant.actor_id)
    except ApprovalNotFoundError as error:
        raise _not_found(error) from error
    except ApprovalConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
