"""Mounted HTTP surface. Authentication, not request JSON, selects the tenant."""
import json
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from app.core.providers import generate
from .schemas import *
from .service import Service
from .wiring import build_narrative_collectors

router=APIRouter(prefix="/narrative-architect",tags=["narrative-architect"])
# The process service holds a bounded evidence cache partitioned by authenticated tenant.
# Production collectors are injected at startup; an absent collector fails closed.
_service=Service(generate=generate,collectors=build_narrative_collectors())
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

from .evidence_meter import EvidenceMeterRequest,meter as evidence_meter
@router.post('/evidence-completeness')
def evidence_completeness(body:EvidenceMeterRequest,tenant:TenantContext=Depends(require_tenant)):
 return {'tenant_id':tenant.tenant_id,**evidence_meter(body)}

from .revision_acceptance import RevisionAcceptance,verify_revision_acceptance
@router.post('/evidence-completeness/revision-acceptance/verify')
def revision_acceptance(body:RevisionAcceptance,tenant:TenantContext=Depends(require_tenant)):
 try:return {'tenant_id':tenant.tenant_id,**verify_revision_acceptance(body)}
 except ValueError as error:raise HTTPException(422,str(error)) from error

from .revision_persistence import persist_revision_acceptance
from .revision_store import RevisionStore
def get_revision_store(tenant:TenantContext=Depends(require_tenant)):return RevisionStore(tenant.tenant_id)
@router.post('/evidence-completeness/revision-acceptance/persist')
def persist_revision(body:RevisionAcceptance,tenant:TenantContext=Depends(require_tenant),store=Depends(get_revision_store)):
 try:return {'tenant_id':tenant.tenant_id,**persist_revision_acceptance(body,store)}
 except ValueError as error:raise HTTPException(409,str(error)) from error
