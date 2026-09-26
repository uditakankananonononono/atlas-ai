from fastapi import APIRouter, Depends, HTTPException

from app.auth.context import TenantContext, require_tenant
from app.modules.m00_approval_center.service import default_service

from .forms import FieldDescriptor
from .schemas import FillIn, NavigateIn, SessionIn, SubmitExecuteIn, SubmitIn
from .security import NavigationBlocked
from .service import Service

router = APIRouter(prefix="/browser-agent", tags=["browser-agent"])
_service = None


def get_service():
    global _service
    if _service is None:
        from .playwright_adapter import PlaywrightSessions
        from .session_bridge.dispatch import BridgedSessions, HybridSessions
        from .session_bridge.routes import get_registry
        from .store import SQLStore
        sessions = HybridSessions(PlaywrightSessions(), BridgedSessions(get_registry()))
        _service = Service(sessions, default_service(), SQLStore())
    return _service


@router.post("/session/close")
async def close_session(body: SessionIn, tenant: TenantContext = Depends(require_tenant), service=Depends(get_service)):
    closed = await service.sessions.close_session(tenant.tenant_id, body.session_id)
    return {"status": "closed" if closed else "not_found"}


@router.post("/navigate")
async def navigate(body: NavigateIn, tenant: TenantContext = Depends(require_tenant), service=Depends(get_service)):
    try:
        return await service.navigate(tenant.tenant_id, body.session_id, body.url, body.persistent)
    except NavigationBlocked as error:
        raise HTTPException(400, str(error)) from error


@router.post("/fill")
async def fill(body: FillIn, tenant: TenantContext = Depends(require_tenant), service=Depends(get_service)):
    fields = [FieldDescriptor(**item.model_dump()) for item in body.fields]
    return await service.fill(tenant.tenant_id, body.session_id, fields, body.data)


@router.post("/screenshot")
async def screenshot(session_id: str, tenant: TenantContext = Depends(require_tenant), service=Depends(get_service)):
    return {"path": await service.screenshot(tenant.tenant_id, session_id)}


@router.post("/extract")
async def extract(session_id: str, tenant: TenantContext = Depends(require_tenant), service=Depends(get_service)):
    return {"html": await service.extract(tenant.tenant_id, session_id)}


@router.post("/submit/request", status_code=201)
async def request_submit(body: SubmitIn, tenant: TenantContext = Depends(require_tenant), service=Depends(get_service)):
    try:
        return await service.request_submit(tenant.tenant_id, tenant.actor_id, body.session_id, body.selector, body.values)
    except NavigationBlocked as error:
        raise HTTPException(400, str(error)) from error


@router.post("/submit/execute")
async def execute_submit(body: SubmitExecuteIn, tenant: TenantContext = Depends(require_tenant), service=Depends(get_service)):
    try:
        return await service.submit(tenant.tenant_id, body.session_id, body.selector, body.values, body.approval_id)
    except PermissionError as error:
        raise HTTPException(409, str(error)) from error
    except NavigationBlocked as error:
        raise HTTPException(400, str(error)) from error

from .readback import ReadbackDiffRequest,diff_readback
@router.post('/submit/readback-diff')
def submit_readback_diff(body:ReadbackDiffRequest,tenant:TenantContext=Depends(require_tenant)):
 return {'tenant_id':tenant.tenant_id,**diff_readback(body)}

from .pre_submit_capture import PreSubmitCaptureRequest,capture_pre_submit
@router.post('/submit/pre-submit-capture')
async def pre_submit_capture(body:PreSubmitCaptureRequest,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)):
 try:return {'tenant_id':tenant.tenant_id,**await capture_pre_submit(service.sessions,tenant.tenant_id,body)}
 except ValueError as error:raise HTTPException(422,str(error)) from error

from .capture_persistence import PersistCaptureRequest,persist_capture
@router.post('/submit/pre-submit-capture/persist')
async def persist_pre_submit_capture(body:PersistCaptureRequest,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)):
 try:return {'tenant_id':tenant.tenant_id,**await persist_capture(body,tenant.tenant_id,service.store)}
 except ValueError as error:raise HTTPException(409,str(error)) from error
from pydantic import BaseModel as _CBM,Field as _CBF
from .capture_bound_submit import execute_capture_bound_submit,request_capture_bound_submit
class CaptureBoundSubmitIn(SubmitIn):
 capture_sha256:str=_CBF(pattern=r'^[0-9a-f]{64}$')
class CaptureBoundExecuteIn(CaptureBoundSubmitIn):
 approval_id:str=_CBF(min_length=1,max_length=200)
@router.post('/submit/capture-bound/request',status_code=201)
async def request_capture_bound(body:CaptureBoundSubmitIn,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)):
 try:return await request_capture_bound_submit(service,tenant.tenant_id,tenant.actor_id,body.session_id,body.selector,body.values,body.capture_sha256)
 except PermissionError as e:raise HTTPException(409,str(e)) from e
 except NavigationBlocked as e:raise HTTPException(400,str(e)) from e
@router.post('/submit/capture-bound/execute')
async def execute_capture_bound(body:CaptureBoundExecuteIn,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)):
 try:return await execute_capture_bound_submit(service,service.store.sessions,tenant.tenant_id,body.session_id,body.selector,body.values,body.approval_id,body.capture_sha256)
 except PermissionError as e:raise HTTPException(409,str(e)) from e
 except NavigationBlocked as e:raise HTTPException(400,str(e)) from e
 except RuntimeError as e:raise HTTPException(502,str(e)) from e

from .session_bridge.routes import router as bridge_router
router.include_router(bridge_router)
