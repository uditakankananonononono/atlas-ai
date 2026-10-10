from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .lifecycle_unverified_01_62 import ROWS,BY_METHOD,run
router=APIRouter(prefix='/lifecycle-workbench',tags=['study-abroad-lifecycle'])
class Request(BaseModel):method:str;data:dict[str,Any]=Field(default_factory=dict)
@router.get('/methods')
def methods():return [{'row':r,'method':m} for r,m in ROWS.items()]
@router.post('/analyze')
def analyze(req:Request):
 try:return run(req.method,req.data)
 except (ValueError,KeyError,TypeError) as e:raise HTTPException(422,str(e))

from datetime import datetime
from .source_freshness import assess_facts
from .cost_estimate import estimate_net_cost,summarize_awards
from .vector_contract import validated_cosine,lexical_hash_vector

class FreshnessRequest(BaseModel):
 records:list[dict[str,Any]]
 now:datetime
 max_age_days:int=Field(default=180,ge=1,le=3650)

@router.post('/source-freshness')
def source_freshness(req:FreshnessRequest):
 try:return assess_facts(req.records,now=req.now,max_age_days=req.max_age_days)
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc

class CostRequest(BaseModel):
 data:dict[str,Any]

@router.post('/cost-estimate')
def cost_estimate(req:CostRequest):
 try:return estimate_net_cost(req.data)
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@router.post('/award-summary')
def award_summary(req:CostRequest):
 try:return summarize_awards(req.data)
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc

class VectorRequest(BaseModel):
 left:list[Any]
 right:list[Any]

@router.post('/validated-cosine')
def validated_vector_cosine(req:VectorRequest):
 try:return {'score':validated_cosine(req.left,req.right),'semantic_provenance_attested':False,'calculation_only':True}
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc

class LexicalRequest(BaseModel):
 text:str=Field(max_length=100000)
 dimensions:int=Field(default=16,ge=1,le=4096)

@router.post('/lexical-vector')
def lexical_vector(req:LexicalRequest):
 try:return lexical_hash_vector(req.text,dimensions=req.dimensions).as_dict()
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc
