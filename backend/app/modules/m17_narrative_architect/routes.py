"""Mounted HTTP surface. Authentication, not request JSON, selects the tenant."""
import json
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from app.core.providers import generate
from .schemas import *
from .service import Service

router=APIRouter(prefix="/narrative-architect",tags=["narrative-architect"])
# The process service holds a bounded evidence cache partitioned by authenticated tenant.
# Production collectors are injected at startup; an absent collector fails closed.
_service=Service(generate=generate,collectors={})
def get_service()->Service:return _service

def _tenant_copy(request,tenant:TenantContext):
 return request.model_copy(update={"owner_id":tenant.tenant_id})

@router.post("/advice",response_model=list[AdviceOut])
async def advice(request:CollectIn,tenant:TenantContext=Depends(require_tenant),service:Service=Depends(get_service)):
 try:return await service.collect(_tenant_copy(request,tenant))
 except (ValueError,RuntimeError) as e:raise HTTPException(422,str(e))

@router.post("/concepts",response_model=list[ConceptOut])
async def concepts(request:ConceptIn,tenant:TenantContext=Depends(require_tenant),service:Service=Depends(get_service)):
 try:return await service.concepts(_tenant_copy(request,tenant))
 except (ValueError,RuntimeError,json.JSONDecodeError) as e:raise HTTPException(422,str(e))

@router.post("/critique",response_model=CritiqueOut)
async def critique(request:CritiqueIn,tenant:TenantContext=Depends(require_tenant),service:Service=Depends(get_service)):
 try:return await service.critique(_tenant_copy(request,tenant))
 except (ValueError,RuntimeError,json.JSONDecodeError) as e:raise HTTPException(422,str(e))
