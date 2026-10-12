"""Thin tenant-bound route for the row-1520 Failure Analysis engine.

Scope is the engine's own module docstring: a bounded plan over caller-supplied
failure-analysis declarations. Closed-scoped, NOT literal breadth: this route
authorizes, executes, merges, releases or approves nothing.
"""
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .failure_analysis1520 import plan

router = APIRouter(prefix='/engineering/failure-analysis/1520', tags=['engineering-1520'])


class Request1520(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/plan', dependencies=[Depends(reject_surrogate_source)])
def run(body: Request1520, tenant: TenantContext = Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = plan(body.data)
        return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
