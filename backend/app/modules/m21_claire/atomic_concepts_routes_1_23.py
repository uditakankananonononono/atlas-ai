from typing import Any
from fastapi import APIRouter,HTTPException,Depends
from pydantic import BaseModel,Field
from app.auth.context import TenantContext,require_tenant
from .atomic_concepts_1_23 import *
router=APIRouter(prefix='/atomic-concepts-1-23',tags=['claire-atomic-concepts'])
_journal=DecisionJournal(lambda text:[float(len(text)),float(sum(map(ord,text))%997),float(len(text.split()))])
class RunIn(BaseModel):row_id:str;data:dict[str,Any]=Field(default_factory=dict)
class DecisionIn(BaseModel):decision:str;reason:str;context:str=''
class RetrieveIn(BaseModel):query:str;k:int=Field(5,ge=1,le=20)
class AdaptIn(BaseModel):proposal:dict[str,Any];query:str
class CorrectionIn(BaseModel):original:str;corrected:str;context:str=''
@router.get('/capabilities')
def listing():return capabilities()
@router.post('/run')
def run(body:RunIn):
 try:return execute_atomic(body.row_id,body.data)
 except AtomicConceptError as exc:raise HTTPException(422,detail=str(exc)) from exc
@router.post('/decisions')
def decision(body:DecisionIn,t:TenantContext=Depends(require_tenant)):
 try:return _journal.capture(t.tenant_id,body.decision,body.reason,body.context)
 except AtomicConceptError as exc:raise HTTPException(422,detail=str(exc)) from exc
@router.post('/decisions/retrieve')
def retrieve(body:RetrieveIn,t:TenantContext=Depends(require_tenant)):return {'hits':_journal.retrieve(t.tenant_id,body.query,body.k)}
@router.post('/recommendations/adapt')
def adapt(body:AdaptIn,t:TenantContext=Depends(require_tenant)):return _journal.adapt(t.tenant_id,body.proposal,body.query)
@router.post('/corrections')
def correction(body:CorrectionIn,t:TenantContext=Depends(require_tenant)):
 try:return _journal.correction(t.tenant_id,body.original,body.corrected,body.context)
 except AtomicConceptError as exc:raise HTTPException(422,detail=str(exc)) from exc
