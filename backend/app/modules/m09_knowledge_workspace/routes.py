from fastapi import APIRouter,Depends,HTTPException,Query,status
from app.auth.context import TenantContext,require_tenant
from .repository import SqlGraphRepository
from .schemas import *
from .service import ConflictError,Service
router=APIRouter(prefix="/knowledge-workspace",tags=["knowledge-workspace"])
def get_service(t:TenantContext=Depends(require_tenant)):return Service(SqlGraphRepository(t.tenant_id,t.actor_id))
@router.post("/nodes",response_model=Node,status_code=status.HTTP_201_CREATED)
def create_node(data:NodeCreate,service:Service=Depends(get_service)):return service.create_node(data)
@router.patch("/nodes/{node_id}",response_model=Node)
def update_node(node_id:str,data:NodeUpdate,service:Service=Depends(get_service)):
    try:return service.update_node(node_id,data)
    except LookupError:raise HTTPException(404,"node not found")
    except ConflictError as e:raise HTTPException(409,str(e))
@router.post("/edges",response_model=Edge,status_code=status.HTTP_201_CREATED)
def create_edge(data:EdgeCreate,service:Service=Depends(get_service)):
    try:return service.create_edge(data)
    except LookupError:raise HTTPException(404,"node not found")
    except ConflictError as e:raise HTTPException(409,str(e))
@router.get("/nodes/{node_id}/neighborhood",response_model=Neighborhood)
def neighborhood(node_id:str,depth:int=Query(1,ge=1,le=5),limit:int=Query(250,ge=10,le=1000),service:Service=Depends(get_service)):
    try:return service.neighborhood(node_id,depth,limit)
    except LookupError:raise HTTPException(404,"node not found")
@router.post("/suggestions/{suggestion_id}/review",response_model=LinkSuggestion)
def review(suggestion_id:str,data:ReviewRequest,service:Service=Depends(get_service)):
    try:return service.review(suggestion_id,data.accept)
    except LookupError:raise HTTPException(409,"suggestion is not pending")
@router.post("/planner-context")
def planner_context(data:PlannerContextRequest,service:Service=Depends(get_service)):return service.planner_context(data.node_ids)

from typing import Any
from pydantic import BaseModel,Field
from .humanities_support_1860_1909 import humanities_support_1860_1909
class Humanities1860To1909In(BaseModel):
    feature_id:int=Field(ge=1860,le=1909)
    data:dict[str,Any]=Field(default_factory=dict)
@router.post('/humanities-1860-1909/support')
def humanities_1860_1909_route(body:Humanities1860To1909In,tenant:TenantContext=Depends(require_tenant)):
    try:return {'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id,**humanities_support_1860_1909(body.feature_id,body.data)}
    except ValueError as error:raise HTTPException(422,str(error)) from error
@router.post('/technical-95-99/{row_id}')
def technical_95_99(row_id:int,payload:dict):
 from .technical_95_99 import run
 try:return run(row_id,payload)
 except (ValueError,TypeError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc

from .contradictions import ContradictionInboxRequest, build_contradiction_inbox

@router.post('/contradiction-inbox')
def contradiction_inbox(body: ContradictionInboxRequest, tenant: TenantContext = Depends(require_tenant)):
    try:
        return {'tenant_id': tenant.tenant_id, **build_contradiction_inbox(body)}
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
