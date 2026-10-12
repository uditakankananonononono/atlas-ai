"""Row707: mounted caller-supplied computation, closed-scoped, NOT literal breadth.
Authorizes, executes, merges, releases or approves nothing.
"""
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .naming_checker707 import check_naming as engine

router=APIRouter(prefix='/naming-conventions/707',tags=['m20-naming707'])
class Request707(BaseModel):
    data:dict[str,Any]
    tenant_id:Optional[str]=None
    actor_id:Optional[str]=None
    resource_refs:list[dict[str,Any]]=Field(default_factory=list,max_length=64)

@router.post('/check',dependencies=[Depends(reject_surrogate_source)])
def run(body:Request707,tenant:TenantContext=Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True),tenant)
    try:
        result=engine(body.data["source"],body.data["rules"])
        return {**result,'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id}
    except (ValueError,TypeError,KeyError)as exc:
        raise HTTPException(422,str(exc))from exc
