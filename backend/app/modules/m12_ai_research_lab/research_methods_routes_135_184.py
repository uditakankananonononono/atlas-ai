from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .research_methods_135_184 import *
router=APIRouter(prefix='/research-methods-135-184',tags=['m12-research-methods'])
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def list_capabilities():return capabilities()
@router.post('/{method}')
def run(method:str,request:Request):
 try:return execute(method,request.payload)
 except ResearchMethodError as exc:raise HTTPException(422,detail=str(exc)) from exc
