from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .openapi704 import generate_openapi

router=APIRouter(prefix='/api-documentation',tags=['m20-api-documentation'])
class Request704(BaseModel):
    data:dict[str,Any]
    tenant_id:Optional[str]=None
    actor_id:Optional[str]=None
    resource_refs:list[dict[str,Any]]=Field(default_factory=list,max_length=64)

@router.post('/openapi',dependencies=[Depends(reject_surrogate_source)])
def run(body:Request704,tenant:TenantContext=Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True),tenant)
    try:
        result=generate_openapi(body.data)
        return {**result,'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id}
    except (ValueError,TypeError)as exc:raise HTTPException(422,str(exc))from exc

from fastapi import Request
from fastapi.responses import Response
from .mounted_openapi704 import mounted_documentation

@router.get('/mounted')
def mounted(request: Request, tenant: TenantContext = Depends(require_tenant)):
    try:
        result = mounted_documentation(request.app)
        return {**result, 'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

@router.get('/mounted/download')
def mounted_download(request: Request, tenant: TenantContext = Depends(require_tenant)):
    try:
        result = mounted_documentation(request.app)
        return Response(result['canonical_json'], media_type='application/json',
                        headers={'Content-Disposition': 'attachment; filename="mounted-openapi.json"',
                                 'ETag': '"' + result['sha256'] + '"',
                                 'Cache-Control': 'private, no-store'})
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
