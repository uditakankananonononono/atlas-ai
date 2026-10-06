from typing import Any
from fastapi import APIRouter,HTTPException,Header,Depends
from app.auth.context import TenantContext,require_tenant
from pydantic import BaseModel,Field
from .cognitive_learning_860_909 import CognitiveLearningError,capabilities,execute
router=APIRouter(prefix='/cognitive-learning-860-909',tags=['m20-cognitive-learning'])
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def list_capabilities():return capabilities()
@router.post('/{row_id}')
def run(row_id:int,request:Request,x_tenant_id:str|None=Header(None),x_actor_id:str|None=Header(None),principal:TenantContext=Depends(require_tenant)):
 if (x_tenant_id is not None and x_tenant_id!=principal.tenant_id) or (x_actor_id is not None and x_actor_id!=principal.actor_id):raise HTTPException(403,'scope header mismatches authenticated principal')
 x_tenant_id=principal.tenant_id;x_actor_id=principal.actor_id
 if request.payload.get('tenant_id',x_tenant_id)!=x_tenant_id or request.payload.get('actor_id',x_actor_id)!=x_actor_id:raise HTTPException(403,'payload scope mismatches authenticated principal')
 try:
  p=dict(request.payload)
  if p.get('tenant_id',x_tenant_id)!=x_tenant_id or p.get('actor_id',x_actor_id)!=x_actor_id:raise CognitiveLearningError('header and payload scope mismatch')
  p['tenant_id']=x_tenant_id;p['actor_id']=x_actor_id
  return execute(row_id,p)
 except CognitiveLearningError as e:raise HTTPException(422,detail=str(e)) from e
