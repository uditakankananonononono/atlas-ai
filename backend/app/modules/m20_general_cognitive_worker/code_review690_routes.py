from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .code_review690 import CodeReviewError, review

router = APIRouter(prefix='/code-review/690', tags=['m20-code-review-690'])


class Request690(BaseModel):
    diff: str = Field(max_length=1_000_000)
    review_checklist: list[Any] = Field(max_length=64)
    author: Any
    reviewer: Any = None
    requested_decision: Any = None
    max_added_lines: Any = 400
    max_line_length: Any = 120
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/review', dependencies=[Depends(reject_surrogate_source)])
def handle(body: Request690, tenant: TenantContext = Depends(require_tenant)):
    """Rule-based review evidence for a supplied unified diff. Merges, releases and approves nothing."""
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        result = review(body.diff, body.review_checklist, author=body.author, reviewer=body.reviewer,
                        requested_decision=body.requested_decision, max_added_lines=body.max_added_lines,
                        max_line_length=body.max_line_length)
    except (CodeReviewError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
