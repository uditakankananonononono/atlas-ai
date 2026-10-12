"""Dedicated response_surface_methodology1541 supplied-input route. No physical execution."""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .response_surface_methodology1541 import prepare

router = APIRouter(prefix='/engineering/response_surface_methodology1541', tags=['m20-response_surface_methodology1541'])

class EngineRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)

@router.post('/run', dependencies=[Depends(reject_surrogate_source)])
def run(body: EngineRequest, tenant: TenantContext = Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = prepare(body.data)
        return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
