from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException,Query
from app.auth.context import TenantContext,require_tenant
from .schemas import *
from .service import Service
router=APIRouter(prefix="/project-builder",tags=["Project Builder"])
def get_service(tenant:TenantContext=Depends(require_tenant))->Service:
    from app.core.approvals import approvals
    from .sql_repository import SqlProjectRepository
    return Service(approvals,repository=SqlProjectRepository(tenant.tenant_id))
def tenant(context:TenantContext=Depends(require_tenant))->str:return context.tenant_id
def _get_or_404(service:Service,tenant_id:str,project_id:str):
    try:return service.get(tenant_id,project_id)
    except KeyError as exc:raise HTTPException(404,"project not found") from exc
@router.post("/projects",response_model=ProjectView)
def create(request:CreateProjectRequest,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):return service.create(tenant_id,request)
@router.get("/projects",response_model=list[ProjectView])
def list_projects(limit:int=Query(default=100,ge=1,le=500),tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):return service.list(tenant_id,limit=limit)
@router.get("/projects/{project_id}",response_model=ProjectView)
def get_project(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):return _get_or_404(service,tenant_id,project_id)
@router.post("/projects/{project_id}/plan",response_model=PlanResponse)
async def plan(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    try:return await service.plan(service.get(tenant_id,project_id))
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
    except Exception as exc:raise HTTPException(422,str(exc)) from exc
@router.post("/projects/{project_id}/execution-proposals",response_model=ExecutionProposal,status_code=202)
def propose(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    try:return service.propose_execution(service.get(tenant_id,project_id))
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.post("/projects/{project_id}/scope",response_model=ScopeView)
def scope(project_id:str,request:ScopeRequest,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    project=_get_or_404(service,tenant_id,project_id)
    try:return service.scope_project(project,request)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.post("/projects/{project_id}/milestones",response_model=list[MilestoneView])
def create_milestones(project_id:str,request:MilestonePlanRequest,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    project=_get_or_404(service,tenant_id,project_id)
    try:return service.plan_milestones(project,request)
    except KeyError as exc:raise HTTPException(422,str(exc)) from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.get("/projects/{project_id}/milestones",response_model=list[MilestoneView])
def get_milestones(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    return service.list_milestones(_get_or_404(service,tenant_id,project_id))
@router.get("/projects/{project_id}/milestones/progress",response_model=MilestoneProgressView)
def milestone_progress(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    project=_get_or_404(service,tenant_id,project_id)
    try:return service.milestone_progress(project)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.post("/projects/{project_id}/milestones/{milestone_id}/advance",response_model=MilestoneView)
def advance_milestone(project_id:str,milestone_id:str,request:MilestoneAdvanceRequest,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    project=_get_or_404(service,tenant_id,project_id)
    try:return service.advance_milestone(project,milestone_id,request)
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.get("/projects/{project_id}/milestones/slippage",response_model=list[SlippageView])
def milestone_slippage(project_id:str,as_of:datetime|None=None,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    return service.milestone_slippage(_get_or_404(service,tenant_id,project_id),as_of=as_of)
@router.post("/projects/{project_id}/milestones/replan",response_model=list[MilestoneView])
def replan_milestones(project_id:str,as_of:datetime|None=None,hours_per_day:float=Query(default=8.0,gt=0),tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    project=_get_or_404(service,tenant_id,project_id)
    try:return service.replan_milestones(project,as_of=as_of,hours_per_day=hours_per_day)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.post("/projects/{project_id}/artifacts",response_model=ArtifactManifest,status_code=201)
def register_artifact(project_id:str,request:ArtifactRegisterRequest,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    project=_get_or_404(service,tenant_id,project_id)
    try:return service.register_artifact(project,request)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.get("/projects/{project_id}/artifacts",response_model=list[ArtifactManifest])
def get_artifacts(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    return service.list_artifacts(_get_or_404(service,tenant_id,project_id))
@router.post("/projects/{project_id}/artifacts/validate",response_model=ArtifactSetValidationView)
def validate_artifacts(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    return service.validate_artifacts(_get_or_404(service,tenant_id,project_id))
@router.get("/projects/{project_id}/status-report",response_model=StatusReportView)
def status_report(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    return service.status_report(_get_or_404(service,tenant_id,project_id))
@router.post("/projects/{project_id}/quality",response_model=QualityResult)
def evaluate_quality(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    project=_get_or_404(service,tenant_id,project_id)
    try:return service.evaluate_plan(project)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.post("/projects/{project_id}/feedback",response_model=FeedbackResponse)
async def feedback(project_id:str,request:FeedbackRequest,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    project=_get_or_404(service,tenant_id,project_id)
    try:return await service.apply_feedback(project,request)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.post("/projects/{project_id}/exports",response_model=ExportView,status_code=201)
def export_project(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    project=_get_or_404(service,tenant_id,project_id)
    try:return service.export_project(project)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
