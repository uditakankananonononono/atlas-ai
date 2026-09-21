from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from app.core.approvals import approvals
from .schemas import *
from .service import Service,NotFoundError
from .sql_repository import Repository
router=APIRouter(prefix="/startup-growth",tags=["startup-growth"])
def get_service(tenant:TenantContext=Depends(require_tenant)):return Service(Repository(tenant.tenant_id),approvals)
@router.post("/landing-pages",response_model=BuildOut,status_code=201)
def landing(data:LandingPageIn,service:Service=Depends(get_service)):return service.landing_page(data)
@router.post("/pitch-decks",response_model=BuildOut,status_code=201)
def deck(data:PitchDeckIn,service:Service=Depends(get_service)):return service.pitch_deck(data)
@router.post("/documentation",response_model=BuildOut,status_code=201)
def docs(data:DocumentationIn,service:Service=Depends(get_service)):return service.documentation(data)
@router.post("/builds/{build_id}/propose/{action}",response_model=PublishProposal,status_code=201)
def propose(build_id:str,action:Literal["push_startup_site","deploy_startup_site","share_pitch_deck","publish_documentation"],service:Service=Depends(get_service)):
    try:return service.propose(build_id,action)
    except NotFoundError as e:raise HTTPException(404,"build not found") from e
@router.post('/technical-85-94/{row_id}')
def technical_85_94(row_id:int,payload:dict):
 from .technical_85_94 import run
 try:return run(row_id,payload)
 except (ValueError,TypeError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc
