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
        from .store import SQLStore
        sessions = PlaywrightSessions()
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
