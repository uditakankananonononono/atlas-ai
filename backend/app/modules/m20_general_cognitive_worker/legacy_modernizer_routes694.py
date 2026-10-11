from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer694 import modernize

router = APIRouter(prefix='/legacy-modernization/694', tags=['legacy-modernization-694'])
class ModernizeRequest(BaseModel):
    source: str = Field(max_length=100000)
    rules: Optional[list[str]] = Field(default=None,max_length=7)
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str,Any]] = Field(default_factory=list,max_length=64)

async def reject_surrogate_source(request:Request):
    try:packet=await request.json()
    except (ValueError,UnicodeError):return
    # Inspect every parsed string before Pydantic can echo rejected input.
    # Iterative traversal avoids recursion; depth is part of this route's scope.
    pending=[(packet,0)]
    while pending:
        value,depth=pending.pop()
        if depth>64:
            raise HTTPException(422,'legacy694 JSON nesting exceeds 64 levels')
        if isinstance(value,str):
            try:value.encode('utf-8')
            except UnicodeEncodeError as e:
                raise HTTPException(422,'source contains invalid Unicode surrogate')from e
        elif isinstance(value,dict):
            pending.extend((key,depth+1)for key in value)
            pending.extend((item,depth+1)for item in value.values())
        elif isinstance(value,list):
            pending.extend((item,depth+1)for item in value)

@router.post('/modernize',dependencies=[Depends(reject_surrogate_source)])
def modernize_source(body:ModernizeRequest,tenant:TenantContext=Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True),tenant)
    try:encoded=body.source.encode('utf-8')
    except UnicodeEncodeError as e:raise HTTPException(422,'source contains invalid Unicode surrogate')from e
    if len(encoded)>100000:raise HTTPException(422,'source exceeds 100000 UTF-8 bytes')
    try:
        result=modernize(body.source,rules=body.rules).to_dict()
        return {**result,'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id,'source_execution_performed':False}
    except UnicodeDecodeError as e:raise HTTPException(422,'legacy694 Unicode source-span defect; transformation refused')from e
    except (RecursionError,MemoryError)as e:raise HTTPException(422,'legacy694 parser resource limit; transformation refused')from e
    except (ValueError,TypeError)as e:raise HTTPException(422,str(e))from e
