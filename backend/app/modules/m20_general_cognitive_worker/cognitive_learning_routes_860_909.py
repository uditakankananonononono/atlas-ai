from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .cognitive_learning_860_909 import CognitiveLearningError,capabilities,execute
router=APIRouter(prefix='/cognitive-learning-860-909',tags=['m20-cognitive-learning'])
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def list_capabilities():return capabilities()
@router.post('/{row_id}')
def run(row_id:int,request:Request):
 try:return execute(row_id,request.payload)
 except CognitiveLearningError as e:raise HTTPException(422,detail=str(e)) from e
