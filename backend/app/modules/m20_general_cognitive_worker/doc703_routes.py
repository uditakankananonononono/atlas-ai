from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .ast_documentation703 import generate

router=APIRouter(prefix='/documentation-generation/703',tags=['m20-documentation-generation-703'])
class Request703(BaseModel):
    data:dict[str,Any]
    tenant_id:Optional[str]=None
    actor_id:Optional[str]=None
    resource_refs:list[dict[str,Any]]=Field(default_factory=list,max_length=64)

@router.post('/generate',dependencies=[Depends(reject_surrogate_source)])
def run(body:Request703,tenant:TenantContext=Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True),tenant)
    try:
        result=generate(body.data)
        return {**result,'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id}
    except (RecursionError,MemoryError)as exc:raise HTTPException(422,'doc703 parser resource limit; generation refused')from exc
    except (ValueError,TypeError)as exc:raise HTTPException(422,str(exc))from exc
