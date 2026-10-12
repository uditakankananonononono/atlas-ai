"""Mounted supplied CTQ/DMADV bookkeeping, no sigma or validation claim."""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .design_for_six_sigma1530 import run

router = APIRouter(prefix='/design-for-six-sigma/1530', tags=['m20-dfss-1530'])


class Request1530(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/run', dependencies=[Depends(reject_surrogate_source)])
def evaluate(body: Request1530, tenant: TenantContext = Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = run(body.data)
        return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
