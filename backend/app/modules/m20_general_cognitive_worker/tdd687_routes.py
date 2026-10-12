from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .test_driven_development687 import run

router = APIRouter(prefix='/test-driven-development/687', tags=['m20-tdd-receipts-687'])


class Request687(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/check', dependencies=[Depends(reject_surrogate_source)])
def handle(body: Request687, tenant: TenantContext = Depends(require_tenant)):
    """Check supplied red/green/refactor receipts for consistency. Runs no tests."""
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = run(body.data)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
