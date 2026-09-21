from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .schemas import *
from .service import Service
router=APIRouter(prefix="/document-generator",tags=["Document Generator"])
def get_service(tenant:TenantContext=Depends(require_tenant))->Service:
    from app.core.approvals import approvals
    from .sql_repository import SqlVersionRepository
    return Service(approvals,repository=SqlVersionRepository(tenant.tenant_id))
def tenant(context:TenantContext=Depends(require_tenant))->str:return context.tenant_id
@router.post("/documents/{document_id}/versions",response_model=DocumentVersion)
def create(document_id:str,request:CreateVersionRequest,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    try:return service.create_version(tenant_id,document_id,request)
    except (KeyError,ValueError) as exc:raise HTTPException(422,str(exc)) from exc
@router.get("/versions/diff",response_model=DiffResponse)
def diff(from_version_id:str,to_version_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    try:return service.diff(service.get(tenant_id,from_version_id),service.get(tenant_id,to_version_id))
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
@router.post("/versions/{version_id}/export-proposals",response_model=ExportProposal,status_code=202)
def export(version_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    try:return service.propose_export(service.get(tenant_id,version_id))
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc

from typing import Any
from .design_support_333_359 import design_support_333_359
class Design333To359In(BaseModel):
    feature_id:int=Field(ge=333,le=359)
    data:dict[str,Any]=Field(default_factory=dict)
@router.post('/design-333-359/support')
def design_333_359_route(body:Design333To359In,tenant_id:str=Depends(tenant)):
    try:return {'tenant_id':tenant_id,**design_support_333_359(body.feature_id,body.data)}
    except ValueError as error:raise HTTPException(422,str(error)) from error

@router.get('/creative-production-306-332')
def creative_catalog_306_332():
    from .creative_production_306_332 import catalog
    return catalog()
@router.post('/creative-production-306-332/{row_id}')
def creative_plan_306_332(row_id:int,payload:dict):
    from .creative_production_306_332 import CreativeError,plan
    try:return plan(row_id,payload)
    except CreativeError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
