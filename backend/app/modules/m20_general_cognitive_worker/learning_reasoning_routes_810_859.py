from typing import Any
from fastapi import APIRouter,HTTPException,Depends
from app.auth.context import TenantContext,require_tenant
from .computation_boundary import owner_payload
from pydantic import BaseModel,Field
from .learning_reasoning_810_859 import *
router=APIRouter(prefix='/learning-reasoning-810-859',tags=['m20-learning-reasoning'])
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def listing():return capabilities()
@router.post('/{method}')
def run(method:str,request:Request,tenant:TenantContext=Depends(require_tenant)):
 payload=owner_payload(request.payload,tenant)
 try:
  result=execute(method,payload)
  return {**result,'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id}
 except (LearningReasoningError,ValueError,TypeError,KeyError,OverflowError) as exc:raise HTTPException(422,detail=str(exc)) from exc
