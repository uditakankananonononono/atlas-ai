"""Direct mounted semantic surface for AI-system rows 1910-1959."""
from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from . import ai_systems_1910_1959 as engine
router=APIRouter(prefix='/ai-systems-1910-1959',tags=['ai-systems-1910-1959'])
class Request(BaseModel):
 method:str=Field(min_length=1)
 data:dict[str,Any]=Field(default_factory=dict)
 params:dict[str,Any]=Field(default_factory=dict)
 seed:int=Field(0,ge=0)
@router.get('/methods')
def methods():return [{'method':m,'feature_row':r,'summary':engine.SUMMARIES[m],'required_inputs':engine.INPUTS[m]} for m,r in engine.ROWS.items()]
@router.post('/analyze')
def analyze(request:Request):
 try:return engine.run(request.method,request.data,request.params,request.seed)
 except (ValueError,KeyError,TypeError) as exc:raise HTTPException(422,detail=str(exc)) from exc
