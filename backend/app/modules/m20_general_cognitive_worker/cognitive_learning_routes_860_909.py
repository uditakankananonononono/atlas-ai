from typing import Any
from fastapi import APIRouter,HTTPException,Header
from pydantic import BaseModel,Field
from .cognitive_learning_860_909 import CognitiveLearningError,capabilities,execute
router=APIRouter(prefix='/cognitive-learning-860-909',tags=['m20-cognitive-learning'])
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def list_capabilities():return capabilities()
@router.post('/{row_id}')
def run(row_id:int,request:Request,x_tenant_id:str=Header(...),x_actor_id:str=Header(...)):
 try:
  p=dict(request.payload)
  if p.get('tenant_id',x_tenant_id)!=x_tenant_id or p.get('actor_id',x_actor_id)!=x_actor_id:raise CognitiveLearningError('header and payload scope mismatch')
  p['tenant_id']=x_tenant_id;p['actor_id']=x_actor_id
  return execute(row_id,p)
 except CognitiveLearningError as e:raise HTTPException(422,detail=str(e)) from e
