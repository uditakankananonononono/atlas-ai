"""HTTP surface for the Human Approval Center.

Routes live under /approval-center; the integrator mounts this router with
the global /api/v1 prefix. All domain behavior is in service.py.
"""
import asyncio
import json
import queue

from fastapi import APIRouter, Depends, HTTPException, Response
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
def submit_request(body: schemas.ApprovalSubmit, service: Service = Depends(get_service)) -> dict:
    """Queue a gated action for human approval. Nothing executes here."""
    try:
        return service.submit(
            module_id=body.module_id,
            action_type=body.action_type,
            payload=body.payload,
            user_id=body.user_id,
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
) -> list[dict]:
    """List approval requests newest first, with optional filters."""
    return service.list(status=status, module_id=module_id, user_id=user_id, limit=limit)


@router.get("/requests/{approval_id}", response_model=schemas.ApprovalView)
def get_request(approval_id: str, service: Service = Depends(get_service)) -> dict:
    """Fetch one request; overdue pending requests report as expired."""
    try:
        return service.get(approval_id)
    except ApprovalNotFoundError as error:
        raise _not_found(error) from error


@router.post("/requests/{approval_id}/decision", response_model=schemas.ApprovalView)
def decide_request(
    approval_id: str,
    body: schemas.ApprovalDecisionIn,
    service: Service = Depends(get_service),
) -> dict:
    """Record the human decision. Final: re-deciding returns 409."""
    try:
        return service.decide(approval_id, ApprovalStatus(body.decision), body.decided_by)
    except ApprovalNotFoundError as error:
        raise _not_found(error) from error
    except ApprovalConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/requests/{approval_id}/audit", response_model=list[schemas.ApprovalEventView])
def audit_request(approval_id: str, service: Service = Depends(get_service)) -> list[dict]:
    """Return the immutable event log for one request."""
    try:
        return service.audit(approval_id)
    except ApprovalNotFoundError as error:
        raise _not_found(error) from error


@router.post("/expire", response_model=schemas.ExpireResult)
def expire_overdue(service: Service = Depends(get_service)) -> dict:
    """Sweep pending requests past their deadline into expired."""
    return {"expired_ids": service.expire_overdue()}


@router.get("/events")
async def stream_events(response: Response, service: Service = Depends(get_service)) -> StreamingResponse:
    """Server-Sent Events feed of approval requests, decisions, and expiries."""
    subscriber = service.broadcaster.subscribe()

    async def event_stream():
        try:
            while True:
                try:
                    event = await asyncio.to_thread(subscriber.get, True, SSE_HEARTBEAT_SECONDS)
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
