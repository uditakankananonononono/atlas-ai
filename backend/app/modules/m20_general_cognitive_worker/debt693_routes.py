from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .debt_scheduler693 import schedule_debt

router = APIRouter(prefix='/technical-debt/693', tags=['m20-technical-debt-693'])


class Request693(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/schedule', dependencies=[Depends(reject_surrogate_source)])
def handle(body: Request693, tenant: TenantContext = Depends(require_tenant)):
    """Exact bounded debt schedule over a supplied dependency graph and budget."""
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = schedule_debt(body.data)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
