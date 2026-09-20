from typing import Any,Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from app.auth.context import TenantContext,require_tenant
from .personalization import PersonalizationRepository
router=APIRouter(prefix='/claire/personalization',tags=['claire-personalization'])
def repo(t:TenantContext=Depends(require_tenant)):return PersonalizationRepository(t.tenant_id)
class MemoryIn(BaseModel):kind:Literal['decision','correction','reasoning_note','ranking','review'];data:dict[str,Any];embedding:list[float]=[]
class OutcomeIn(BaseModel):
 outcome:str=Field(min_length=1);rating:Literal['better','same','worse','mixed','unknown'];lesson:str=Field(min_length=1);evidence:dict[str,Any]={}
class RetrievalIn(BaseModel):query_embedding:list[float]=Field(min_length=1);limit:int=Field(8,ge=1,le=50)
class ConsentIn(BaseModel):enabled:bool;scopes:list[Literal['link_click','opportunity_apply','draft_edit_time','tool_choice']]=[]
class TelemetryIn(BaseModel):kind:str;payload:dict[str,Any]
@router.post('/memories',status_code=201)
def add(x:MemoryIn,r=Depends(repo)):
 if x.kind=='reasoning_note' and 'owner_authored_note' not in x.data:raise HTTPException(422,'reasoning notes must be explicitly owner-authored')
 return {'id':r.add(x.kind,x.data,x.embedding),'kind':x.kind}
@router.post('/retrieve')
def retrieve(x:RetrievalIn,r=Depends(repo)):return r.retrieve(x.query_embedding,x.limit)
@router.post('/decisions/{decision_id}/outcomes',status_code=201)
def add_outcome(decision_id:int,x:OutcomeIn,r=Depends(repo)):
 try:return {'id':r.add_decision_outcome(decision_id,x.model_dump()),'decision_id':decision_id}
 except KeyError as e:raise HTTPException(404,str(e))
@router.get('/decisions/{decision_id}')
def decision_history(decision_id:int,r=Depends(repo)):
 try:return r.decision_history(decision_id)
 except KeyError as e:raise HTTPException(404,str(e))
@router.put('/telemetry-consent')
def consent(x:ConsentIn,r=Depends(repo)):r.set_telemetry_consent(x.enabled,x.scopes);return {'enabled':x.enabled,'scopes':x.scopes}
@router.post('/telemetry-events',status_code=201)
def telemetry(x:TelemetryIn,r=Depends(repo)):
 try:return {'id':r.log_telemetry(x.kind,x.payload)}
 except PermissionError as e:raise HTTPException(403,str(e))
