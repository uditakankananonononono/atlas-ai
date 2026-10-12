"""Authenticated access to the dedicated row-1304 supplied-record computation."""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .law_firm_management1304 import run as compute

router = APIRouter(prefix="/legal/1304", tags=["legal-1304"])


class ComputationRequest(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post("/run", dependencies=[Depends(reject_surrogate_source)])
def run(body: ComputationRequest, tenant: TenantContext = Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = compute(body.data)
        return {**result, "tenant_id": tenant.tenant_id, "actor_id": tenant.actor_id}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
