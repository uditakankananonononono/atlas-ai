from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .pair_programming691 import collaborate

router = APIRouter(prefix='/pair-programming/691', tags=['m20-pair-programming-691'])


class Request691(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/diagnostics', dependencies=[Depends(reject_surrogate_source)])
def handle(body: Request691, tenant: TenantContext = Depends(require_tenant)):
    """Rotation and alignment diagnostics over a supplied session record."""
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = collaborate(body.data)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
