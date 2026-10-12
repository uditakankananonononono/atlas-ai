from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .local_rename_refactor689 import rename_local

router = APIRouter(prefix='/refactoring/689', tags=['m20-local-rename-689'])


class Request689(BaseModel):
    source: str = Field(max_length=100000)
    old: str = Field(max_length=256)
    new: str = Field(max_length=256)
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/rename-local', dependencies=[Depends(reject_surrogate_source)])
def handle(body: Request689, tenant: TenantContext = Depends(require_tenant)):
    """Local-variable alpha-rename of one supplied function. Executes nothing and writes no file."""
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = rename_local(body.source, body.old, body.new)
    except (ValueError, TypeError, KeyError, RecursionError, MemoryError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
