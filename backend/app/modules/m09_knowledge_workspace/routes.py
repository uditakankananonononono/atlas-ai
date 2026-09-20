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
