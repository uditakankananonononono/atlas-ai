"""Thin tenant-bound route for the row-1526 engine (industrial_design1526.py).

Scope is the engine's own module docstring. Closed-scoped, NOT literal breadth:
this route authorizes, executes, merges, releases or approves nothing.
"""
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .industrial_design1526 import run as engine_run

router = APIRouter(prefix='/engineering/industrial-design/1526', tags=['engineering-1526'])


class Request1526(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/run', dependencies=[Depends(reject_surrogate_source)])
def run(body: Request1526, tenant: TenantContext = Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = engine_run(body.data)
        return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
