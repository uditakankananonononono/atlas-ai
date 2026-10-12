"""Supplied1D linear-elastic axial bar only; no general FEA or safety certification."""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .axial_fea1512 import solve_axial_bar

router = APIRouter(prefix='/axial-fea/1512', tags=['m20-bounded-engine'])

class EngineRequest(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)

@router.post('/solve')
def run(body: EngineRequest, tenant: TenantContext = Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = solve_axial_bar(body.data)
        return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
