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
@router.get("/versions/{version_id}/preflight")
def preflight(version_id:str,tenant_id:str=Depends(tenant),service:Service=Depends(get_service)):
    try:return service.preflight(service.get(tenant_id,version_id))
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

from .publication_receipt import PrivatePublicationReceipt,verify_private_publication
@router.post('/publication-receipts/verify')
def verify_publication_receipt(body:PrivatePublicationReceipt,tenant_id:str=Depends(tenant)):
 return {'tenant_id':tenant_id,**verify_private_publication(body)}

from .provider_receipt import VerifyProviderPublication,verify_provider_publication
@router.post('/publication-receipts/provider/verify')
def verify_provider_receipt(body:VerifyProviderPublication,tenant_id:str=Depends(tenant)):
 try:return {'tenant_id':tenant_id,**verify_provider_publication(body)}
 except ValueError as error:raise HTTPException(422,str(error)) from error

from .asymmetric_provider_receipt import VerifyAsymmetricProviderPublication,verify_asymmetric_provider_publication
@router.post('/publication-receipts/provider/ed25519/verify')
def verify_ed25519_provider_receipt(body:VerifyAsymmetricProviderPublication,tenant_id:str=Depends(tenant)):
 try:return {'tenant_id':tenant_id,**verify_asymmetric_provider_publication(body)}
 except ValueError as error:raise HTTPException(422,str(error)) from error
from .approved_worker import ApprovedPublicationJob,execute_approved_publication
class UnconfiguredPublicationWorker:
 def render(self,*args):raise ValueError('renderer adapter is not configured')
 def upload_private(self,*args):raise ValueError('private upload adapter is not configured')
def get_publication_worker():return UnconfiguredPublicationWorker()
@router.post('/publication-worker/execute')
def execute_publication_worker(body:ApprovedPublicationJob,tenant_id:str=Depends(tenant),worker=Depends(get_publication_worker)):
 from app.core.approvals import approvals
 try:return {'tenant_id':tenant_id,**execute_approved_publication(body,tenant_id,approvals,worker,worker)}
 except ValueError as error:raise HTTPException(409,str(error)) from error
from .publication_receipt_persistence import verify_and_persist_publication
from .publication_receipt_store import PublicationReceiptStore
def get_publication_receipt_store(context:TenantContext=Depends(require_tenant)):return PublicationReceiptStore(context.tenant_id)
@router.post('/publication-receipts/provider/verify-and-persist')
def persist_provider_receipt(body:VerifyProviderPublication,tenant_id:str=Depends(tenant),store=Depends(get_publication_receipt_store)):
 try:return {'tenant_id':tenant_id,**verify_and_persist_publication(body,store)}
 except ValueError as error:raise HTTPException(409,str(error)) from error
from .provider_key_registry import PublicationProviderKeyRegistry,RegisterPublicationProviderKey
def get_publication_provider_key_registry(context:TenantContext=Depends(require_tenant)):return PublicationProviderKeyRegistry(context.tenant_id)
@router.post('/publication-receipts/provider-keys')
def register_publication_provider_key(body:RegisterPublicationProviderKey,tenant_id:str=Depends(tenant),registry=Depends(get_publication_provider_key_registry)):
 try:
  row=registry.register(body);return {'tenant_id':tenant_id,'provider':row.provider,'key_id':row.key_id,'fingerprint_sha256':row.fingerprint_sha256,'active':row.active,'boundary':'Registers public verification-key bytes only; administrative provisioning must establish provider identity and trust.'}
 except ValueError as error:raise HTTPException(409,str(error)) from error
@router.post('/publication-receipts/provider-keys/{provider}/{key_id}/retire')
def retire_publication_provider_key(provider:str,key_id:str,tenant_id:str=Depends(tenant),registry=Depends(get_publication_provider_key_registry)):
 try:
  row=registry.retire(provider,key_id);return {'tenant_id':tenant_id,'provider':provider,'key_id':key_id,'active':row.active,'retired_at':row.retired_at}
 except ValueError as error:raise HTTPException(404,str(error)) from error


# Approved delivery: consume a render_document approval and return a verified download.
from fastapi import Response as _Response
from .delivery import (ApprovedDeliveryService, DeliveryConflict as _DConflict, DeliveryForbidden as _DForbidden,
                       DeliveryNotFound as _DNotFound, RenderFailed as _DRenderFailed)


def get_delivery_service(context: TenantContext = Depends(require_tenant)) -> ApprovedDeliveryService:
    return ApprovedDeliveryService(context.tenant_id, actor_id=context.actor_id)


def _delivery_error(exc: Exception) -> HTTPException:
    if isinstance(exc, _DNotFound):
        return HTTPException(404, "not found")
    if isinstance(exc, _DForbidden):
        return HTTPException(403, str(exc))
    if isinstance(exc, _DConflict):
        return HTTPException(409, str(exc))
    return HTTPException(422, str(exc))


@router.post("/approvals/{approval_id}/deliver", status_code=201)
def deliver_approved_document(approval_id: str, service: ApprovedDeliveryService = Depends(get_delivery_service)):
    """Render the exact approved version once and return a signed, expiring private download link."""
    try:
        return service.deliver(approval_id)
    except (_DNotFound, _DForbidden, _DConflict, _DRenderFailed) as exc:
        raise _delivery_error(exc) from exc


@router.get("/deliveries")
def list_deliveries(limit: int = 100, service: ApprovedDeliveryService = Depends(get_delivery_service)):
    return service.list(min(max(limit, 1), 500))


@router.get("/deliveries/{approval_id}")
def read_delivery(approval_id: str, service: ApprovedDeliveryService = Depends(get_delivery_service)):
    """Read back a delivery receipt with a freshly signed download link."""
    try:
        return service.readback(approval_id)
    except _DNotFound as exc:
        raise _delivery_error(exc) from exc


@router.get("/downloads/{token}")
def download_delivered_document(token: str, service: ApprovedDeliveryService = Depends(get_delivery_service)):
    try:
        data, receipt = service.download(token)
    except (_DNotFound, _DForbidden) as exc:
        raise _delivery_error(exc) from exc
    return _Response(content=data, media_type=receipt["mime_type"],
                     headers={"Content-Disposition": f'attachment; filename="{receipt["filename"]}"',
                              "X-Content-SHA256": receipt["sha256"], "Cache-Control": "private, no-store"})


# Registered-key publication worker: atomic approval consumption, render, private upload,
# Ed25519 receipt verified against the tenant key registry, append-only receipt storage.
from .registered_key_worker import RegisteredKeyPublicationWorker as _RegisteredWorker


def get_registered_publication_worker(context: TenantContext = Depends(require_tenant)):
    from app.core.approvals import approvals
    adapter = UnconfiguredPublicationWorker()
    return _RegisteredWorker(context.tenant_id, approvals, adapter, adapter)


@router.post('/publication-worker/registered/execute')
def execute_registered_publication_worker(body: ApprovedPublicationJob, tenant_id: str = Depends(tenant),
                                          worker=Depends(get_registered_publication_worker)):
    try:
        return {'tenant_id': tenant_id, **worker.run(body)}
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
