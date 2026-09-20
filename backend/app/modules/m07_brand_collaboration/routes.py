from fastapi import APIRouter,Depends,HTTPException,Query
from app.auth.context import TenantContext,require_tenant
from app.core.approvals import approvals
from .schemas import *
from .service import Service,NotFoundError
from .sql_repository import Repository
router=APIRouter(prefix="/brand-collaboration",tags=["brand-collaboration"])
def get_service(tenant:TenantContext=Depends(require_tenant)): return Service(Repository(tenant.tenant_id),approvals)
@router.post("/brands",response_model=BrandCandidate,status_code=201)
def discover(data:BrandDiscoveryIn,creator_mission:str=Query(min_length=3),service:Service=Depends(get_service)): return service.discover(data,creator_mission)
@router.post("/media-kits",response_model=ArtifactOut,status_code=201)
def media_kit(data:MediaKitIn,service:Service=Depends(get_service)): return service.media_kit(data)
@router.post("/sponsorship-packages",response_model=ArtifactOut,status_code=201)
def sponsorship(data:SponsorshipPackageIn,service:Service=Depends(get_service)): return service.sponsorship(data)
@router.post("/invoices",response_model=ArtifactOut,status_code=201)
def invoice(data:InvoiceIn,service:Service=Depends(get_service)): return service.invoice(data)
@router.post("/events",response_model=PartnershipEventOut,status_code=201)
def log_event(data:PartnershipEventIn,service:Service=Depends(get_service)): return service.log_event(data)
@router.post("/reports",response_model=ArtifactOut,status_code=201)
def report(data:ReportIn,service:Service=Depends(get_service)): return service.report(data)
@router.post("/artifacts/{artifact_id}/propose-send",response_model=ApprovalProposal,status_code=201)
def propose_send(artifact_id:str,recipient:str,service:Service=Depends(get_service)):
    try:return service.propose_send(artifact_id,recipient)
    except NotFoundError as e: raise HTTPException(404,"artifact not found") from e
