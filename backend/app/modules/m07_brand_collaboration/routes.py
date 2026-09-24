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
@router.post('/technical-76-84/{row_id}')
def technical_76_84(row_id:int,payload:dict):
 from .technical_76_84 import run
 try:return run(row_id,payload)
 except (ValueError,TypeError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


# -- deliverable obligation tracker ------------------------------------------------
from datetime import datetime as _dt
from pydantic import BaseModel as _BM, Field as _F
from .obligations import ObligationError, ObligationNotFound, ObligationTracker


class ObligationIn(_BM):
    brand_id: str; kind: str = _F(pattern=r"^(deliverable|usage_rights|exclusivity|disclosure|report|other)$")
    title: str = _F(min_length=1, max_length=500); clause_text: str = _F(min_length=1, max_length=8000)
    clause_locator: str = _F(min_length=1, max_length=200); quantity: int = _F(default=1, ge=1, le=1000)
    due_at: _dt | None = None; ends_at: _dt | None = None
    amount_minor: int = _F(default=0, ge=0); currency: str = _F(default="USD", pattern=r"^[A-Z]{3}$")
class EvidenceIn(_BM):
    url: str | None = _F(default=None, max_length=2000); sha256: str | None = _F(default=None, pattern=r"^[0-9a-f]{64}$"); note: str = _F(default="", max_length=2000)
class ApprovalLinkIn(_BM):
    approval_id: str
class InvoiceLinkIn(_BM):
    artifact_id: str; payment_due_at: _dt
class PaymentIn(_BM):
    amount_minor: int = _F(gt=0); note: str = _F(default="", max_length=2000)
class WaiveIn(_BM):
    reason: str = _F(min_length=3, max_length=2000)


def get_tracker(tenant: TenantContext = Depends(require_tenant)) -> ObligationTracker:
    repo = Repository(tenant.tenant_id)
    return ObligationTracker(tenant.tenant_id, brands=repo.brand, artifacts=repo.artifact, approvals=approvals)


def _ob(call):
    try: return call()
    except ObligationNotFound as e: raise HTTPException(404, str(e)) from e
    except ObligationError as e: raise HTTPException(422, str(e)) from e


@router.post("/obligations", status_code=201)
def create_obligation(data: ObligationIn, t: ObligationTracker = Depends(get_tracker)): return _ob(lambda: t.create(**data.model_dump()))
@router.get("/obligations/{obligation_id}")
def get_obligation(obligation_id: str, t: ObligationTracker = Depends(get_tracker)): return _ob(lambda: t.get(obligation_id))
@router.post("/obligations/{obligation_id}/evidence")
def obligation_evidence(obligation_id: str, data: EvidenceIn, t: ObligationTracker = Depends(get_tracker)): return _ob(lambda: t.add_evidence(obligation_id, **data.model_dump()))
@router.post("/obligations/{obligation_id}/approvals")
def obligation_approval(obligation_id: str, data: ApprovalLinkIn, t: ObligationTracker = Depends(get_tracker)): return _ob(lambda: t.link_approval(obligation_id, data.approval_id))
@router.post("/obligations/{obligation_id}/invoice")
def obligation_invoice(obligation_id: str, data: InvoiceLinkIn, t: ObligationTracker = Depends(get_tracker)): return _ob(lambda: t.link_invoice(obligation_id, data.artifact_id, payment_due_at=data.payment_due_at))
@router.post("/obligations/{obligation_id}/payments")
def obligation_payment(obligation_id: str, data: PaymentIn, t: ObligationTracker = Depends(get_tracker)): return _ob(lambda: t.record_payment(obligation_id, **data.model_dump()))
@router.post("/obligations/{obligation_id}/waive")
def obligation_waive(obligation_id: str, data: WaiveIn, t: ObligationTracker = Depends(get_tracker)): return _ob(lambda: t.waive(obligation_id, reason=data.reason))
@router.get("/brands/{brand_id}/obligations")
def brand_obligations(brand_id: str, t: ObligationTracker = Depends(get_tracker)): return t.brand_tracker(brand_id)
