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
@router.post("/projects/{project_id}/designs",response_model=DesignDocView,status_code=201)
def generate_design(project_id:str,request:DesignRequest,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    project=_get_or_404(service,tenant_id,project_id)
    try:return service.generate_design(project,request)
    except Exception as exc:raise HTTPException(422,str(exc)) from exc
@router.get("/projects/{project_id}/designs",response_model=list[DesignListItem])
def list_designs(project_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    try:return service.list_designs(_get_or_404(service,tenant_id,project_id))
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
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

from typing import Any
from .architecture_support_635_684 import architecture_support_635_684
class Architecture635To684In(BaseModel):
    feature_id:int=Field(ge=635,le=684)
    data:dict[str,Any]=Field(default_factory=dict)
@router.post('/architecture-635-684/support')
def architecture_635_684_route(body:Architecture635To684In,context:TenantContext=Depends(require_tenant)):
    try:return {'tenant_id':context.tenant_id,'actor_id':context.actor_id,**architecture_support_635_684(body.feature_id,body.data)}
    except ValueError as error:raise HTTPException(422,str(error)) from error

class ArchitectureWorkflowDraftIn(Architecture635To684In):
    provenance:dict[str,Any]
class ArchitectureWorkflowApprovalIn(BaseModel):
    approval_id:str=Field(min_length=1,max_length=200)
class ArchitectureWorkflowRollbackIn(BaseModel):
    reason:str=Field(min_length=1,max_length=1000)

def _architecture_workflow():
    from .architecture_workflow_635_684 import ArchitectureWorkflowRepository,ArchitectureWorkflowService
    return ArchitectureWorkflowService(ArchitectureWorkflowRepository())
def _workflow_call(operation):
    try:return operation().view()
    except KeyError as error:raise HTTPException(404,str(error)) from error
    except ValueError as error:raise HTTPException(422,str(error)) from error

@router.post('/architecture-635-684/workflows',status_code=201)
def draft_architecture_workflow(body:ArchitectureWorkflowDraftIn,context:TenantContext=Depends(require_tenant)):
    return _workflow_call(lambda:_architecture_workflow().draft(context.tenant_id,context.actor_id,body.feature_id,body.data,body.provenance))
@router.get('/architecture-635-684/workflows/{record_id}')
def get_architecture_workflow(record_id:str,context:TenantContext=Depends(require_tenant)):
    return _workflow_call(lambda:_architecture_workflow().repository.get(context.tenant_id,record_id))
@router.post('/architecture-635-684/workflows/{record_id}/submit')
def submit_architecture_workflow(record_id:str,context:TenantContext=Depends(require_tenant)):
    return _workflow_call(lambda:_architecture_workflow().submit(context.tenant_id,context.actor_id,record_id))
@router.post('/architecture-635-684/workflows/{record_id}/approve')
def approve_architecture_workflow(record_id:str,body:ArchitectureWorkflowApprovalIn,context:TenantContext=Depends(require_tenant)):
    return _workflow_call(lambda:_architecture_workflow().approve(context.tenant_id,context.actor_id,record_id,body.approval_id))
@router.post('/architecture-635-684/workflows/{record_id}/apply')
def apply_architecture_workflow(record_id:str,body:ArchitectureWorkflowApprovalIn,context:TenantContext=Depends(require_tenant)):
    return _workflow_call(lambda:_architecture_workflow().apply(context.tenant_id,context.actor_id,record_id,body.approval_id))
@router.post('/architecture-635-684/workflows/{record_id}/rollback')
def rollback_architecture_workflow(record_id:str,body:ArchitectureWorkflowRollbackIn,context:TenantContext=Depends(require_tenant)):
    return _workflow_call(lambda:_architecture_workflow().rollback(context.tenant_id,context.actor_id,record_id,body.reason))

@router.post('/semantic-engines-575-584/{row_id}')
def semantic_engines_575_584(row_id:int,payload:dict):
    from .semantic_engines_575_584 import run
    try:return run(row_id,payload)
    except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
@router.post('/semantic-architecture-635-684/{row_id}')
def semantic_architecture_635_684(row_id:int,payload:dict):
 from .semantic_architecture_635_684 import run
 try:return run(row_id,payload)
 except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:raise HTTPException(422,str(exc)) from exc

class EngineeringMethod510To574In(BaseModel):
    data:dict[str,Any]

@router.post('/engineering-design-510-574/{method}')
def engineering_design_510_574(method:str,body:EngineeringMethod510To574In,tenant_id:str=Depends(tenant)):
    from .engineering_methods_510_574 import run_engineering_method
    try:return {'tenant_id':tenant_id,**run_engineering_method(method,body.data)}
    except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:raise HTTPException(422,str(exc)) from exc

class AcceptanceMatrixIn(BaseModel):
    criteria:list[dict[str,Any]]=Field(min_length=1,max_length=500)
    artifacts:list[dict[str,Any]]=Field(default_factory=list,max_length=2000)
    tests:list[dict[str,Any]]=Field(default_factory=list,max_length=2000)
@router.post('/acceptance-matrix')
def acceptance_matrix(body:AcceptanceMatrixIn):
    from .acceptance_trace import build_acceptance_matrix
    try:return build_acceptance_matrix(body.criteria,body.artifacts,body.tests)
    except ValueError as error:raise HTTPException(422,str(error)) from error

class ProofStatusIn(BaseModel):requirements:list[dict[str,Any]]=Field(min_length=1,max_length=2000)
@router.post('/proof-status')
def proof_status(body:ProofStatusIn):
 from .acceptance_trace import build_proof_status
 try:return build_proof_status(body.requirements)
 except ValueError as error:raise HTTPException(422,str(error)) from error

from .live_receipt_verification import VerifyLiveReceipts,verify_live_receipts
@router.post('/proof-status/live-receipts/verify')
def verify_proof_live_receipts(body:VerifyLiveReceipts):
 try:return verify_live_receipts(body)
 except ValueError as error:raise HTTPException(422,str(error)) from error

from .asymmetric_live_receipts import VerifyAsymmetricLiveReceipts,verify_asymmetric_live_receipts
@router.post('/proof-status/live-receipts/ed25519/verify')
def verify_ed25519_proof_live_receipts(body:VerifyAsymmetricLiveReceipts):
 try:return verify_asymmetric_live_receipts(body)
 except ValueError as error:raise HTTPException(422,str(error)) from error
from .live_receipt_persistence import verify_and_persist_live_receipts
from .live_receipt_store import LiveReceiptStore
def get_live_receipt_store(context:TenantContext=Depends(require_tenant)):return LiveReceiptStore(context.tenant_id)
@router.post('/proof-status/live-receipts/verify-and-persist')
def verify_and_persist_proof_live_receipts(body:VerifyLiveReceipts,context:TenantContext=Depends(require_tenant),store=Depends(get_live_receipt_store)):
 try:return {'tenant_id':context.tenant_id,**verify_and_persist_live_receipts(body,store)}
 except ValueError as error:raise HTTPException(409,str(error)) from error
