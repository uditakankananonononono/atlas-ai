from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .models import RouteRequest
from .schemas import RunIn,WorkflowIn
from .workflow import Workflow,WorkflowValidationError
router=APIRouter(prefix="/ai-research-lab",tags=["ai-research-lab"])
def get_service(): raise RuntimeError("bind Module 12 Service/provider in app dependency overrides")
def get_dag_engine(): raise RuntimeError("bind Celery-backed DagEngine in app dependency overrides")
@router.post("/run")
async def run(body:RunIn,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)):
    try:return await service.execute(RouteRequest(body.task_type,body.output_tokens,body.budget_cents,body.latency_tolerance_ms,tenant.tenant_id),body.prompt)
    except RuntimeError as error: raise HTTPException(422,str(error)) from error
@router.post("/workflows/run")
async def run_workflow(body:WorkflowIn,tenant:TenantContext=Depends(require_tenant),engine=Depends(get_dag_engine)):
    try:return await engine.run(Workflow.from_yaml(body.yaml),{**body.inputs,"tenant_id":tenant.tenant_id})
    except WorkflowValidationError as error: raise HTTPException(422,str(error)) from error
