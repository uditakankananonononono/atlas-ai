from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .schemas import *
from .service import Service
router=APIRouter(prefix="/project-builder",tags=["Project Builder"])
def get_service(tenant:TenantContext=Depends(require_tenant))->Service:
    from app.core.approvals import approvals
    from .sql_repository import SqlProjectRepository
    return Service(approvals,repository=SqlProjectRepository(tenant.tenant_id))
def tenant(context:TenantContext=Depends(require_tenant))->str:return context.tenant_id
@router.post("/projects",response_model=ProjectView)
def create(request:CreateProjectRequest,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):return service.create(tenant_id,request)
@router.post("/projects/{project_id}/plan",response_model=PlanResponse)
async def plan(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    try:return await service.plan(service.get(tenant_id,project_id))
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.post("/projects/{project_id}/execution-proposals",response_model=ExecutionProposal,status_code=202)
def propose(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    try:return service.propose_execution(service.get(tenant_id,project_id))
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
