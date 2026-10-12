from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .acceptance_test_driven_development688 import run

router = APIRouter(prefix='/acceptance-test-driven-development/688', tags=['m20-atdd-agreements-688'])


class Request688(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/bookkeeping', dependencies=[Depends(reject_surrogate_source)])
def handle(body: Request688, tenant: TenantContext = Depends(require_tenant)):
    """Declared-agreement bookkeeping. Runs no acceptance tests."""
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = run(body.data)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
