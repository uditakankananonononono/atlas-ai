from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .expanded_spec_1_66 import *
router=APIRouter(prefix='/opportunity-discovery/expanded-spec-1-66',tags=['m01-expanded-1-66'])
class NormalizeRequest(BaseModel):
 transport:str
 authorized:bool=False
 records:list[dict[str,Any]]=Field(default_factory=list)
class ScholarshipRegistryRequest(BaseModel):sites:list[dict[str,Any]]=Field(default_factory=list)
@router.get('/sources')
def sources():return capabilities()
@router.post('/sources/{row_id}/normalize')
def normalize_records(row_id:int,request:NormalizeRequest):
 try:return normalize_batch(row_id,request.records,transport=request.transport,authorized=request.authorized)
 except SourceRegistryError as exc:raise HTTPException(422,detail=str(exc)) from exc
@router.post('/scholarship-registry/validate')
def scholarship_registry(request:ScholarshipRegistryRequest):return validate_scholarship_registry(request.sites)
