"""Mounted supplied QA evidence only; runs no tests and grants no release."""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .qa_evidence1535 import evaluate_qa_evidence

router = APIRouter(prefix='/quality-assurance/1535', tags=['m20-qa-1535'])


class Request1535(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/evaluate', dependencies=[Depends(reject_surrogate_source)])
def evaluate(body: Request1535, tenant: TenantContext = Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = evaluate_qa_evidence(body.data)
        return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
