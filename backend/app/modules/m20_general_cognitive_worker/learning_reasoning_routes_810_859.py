from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .learning_reasoning_810_859 import *
router=APIRouter(prefix='/learning-reasoning-810-859',tags=['m20-learning-reasoning'])
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def listing():return capabilities()
@router.post('/{method}')
def run(method:str,request:Request):
 try:return execute(method,request.payload)
 except LearningReasoningError as exc:raise HTTPException(422,detail=str(exc)) from exc
