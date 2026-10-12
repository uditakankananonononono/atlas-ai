from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .mob_programming692 import audit_session_log, plan_mob_session

router = APIRouter(prefix='/mob-programming/692', tags=['m20-mob-programming-692'])


class Plan692(BaseModel):
    participants: Any
    task: Any
    session_minutes: Any
    rotation_minutes: Any
    start_driver: Any = None
    break_every_minutes: Any = None
    break_minutes: Any = 5
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


class Audit692(BaseModel):
    log: Any
    participants: Any
    max_driver_share: Any = 0.5
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/plan', dependencies=[Depends(reject_surrogate_source)])
def plan(body: Plan692, tenant: TenantContext = Depends(require_tenant)):
    """Driver/navigator rotation schedule for a supplied mob. Starts no session."""
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = plan_mob_session(body.participants, body.task, body.session_minutes, body.rotation_minutes,
                                  start_driver=body.start_driver, break_every_minutes=body.break_every_minutes,
                                  break_minutes=body.break_minutes)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}


@router.post('/audit', dependencies=[Depends(reject_surrogate_source)])
def audit(body: Audit692, tenant: TenantContext = Depends(require_tenant)):
    """Audit a supplied session log against fair-rotation limits."""
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = audit_session_log(body.log, body.participants, max_driver_share=body.max_driver_share)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
