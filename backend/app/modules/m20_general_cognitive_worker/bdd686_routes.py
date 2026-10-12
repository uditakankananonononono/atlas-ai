from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .bdd_scenarios686 import execute_scenarios

router = APIRouter(prefix='/bdd-scenarios/686', tags=['m20-bdd-scenarios-686'])


class Request686(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/execute', dependencies=[Depends(reject_surrogate_source)])
def handle(body: Request686, tenant: TenantContext = Depends(require_tenant)):
    """Run the supplied declarative scenarios. Executes no submitted code."""
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = execute_scenarios(body.data)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
