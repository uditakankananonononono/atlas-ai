from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Depends
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

@router.post('/modernize')
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
