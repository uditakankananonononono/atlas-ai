from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .optimization_story_235_280 import *
router=APIRouter(prefix='/optimization-story-235-280',tags=['m20-optimization-story'])
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def listing():return capabilities()
@router.post('/{method}')
def run(method:str,request:Request):
 try:return execute(method,request.payload)
 except WorkbenchError as exc:raise HTTPException(422,detail=str(exc)) from exc
