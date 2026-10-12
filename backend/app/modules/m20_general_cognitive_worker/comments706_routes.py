"""Row706: mounted caller-supplied computation, closed-scoped, NOT literal breadth.
Authorizes, executes, merges, releases or approves nothing.
"""
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .comment_audit706 import audit as engine

router=APIRouter(prefix='/code-comments/706',tags=['m20-comments706'])
class Request706(BaseModel):
    data:dict[str,Any]
    tenant_id:Optional[str]=None
    actor_id:Optional[str]=None
    resource_refs:list[dict[str,Any]]=Field(default_factory=list,max_length=64)

@router.post('/audit',dependencies=[Depends(reject_surrogate_source)])
def run(body:Request706,tenant:TenantContext=Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True),tenant)
    try:
        result=engine(body.data)
        return {**result,'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id}
    except (ValueError,TypeError,KeyError)as exc:
        raise HTTPException(422,str(exc))from exc
