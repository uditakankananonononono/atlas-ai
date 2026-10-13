"""Row 106 route: mounted descriptive-difference review over supplied counts. No priming, no outreach, no causal claim."""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth.context import TenantContext, require_tenant
from .priming_effects106 import PrimingError, review

router = APIRouter(prefix='/priming-effects/106', tags=['m20-priming-effects-106'])


class Request106(BaseModel):
    data: dict[str, Any]


@router.post('/review')
def handle(body: Request106, tenant: TenantContext = Depends(require_tenant)):
    """Exact difference of two supplied proportions with disclosure gating. Not a measure of unconscious effect."""
    try:
        result = review(body.data)
    except PrimingError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
