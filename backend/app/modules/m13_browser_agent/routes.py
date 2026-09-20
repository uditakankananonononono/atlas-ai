from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from app.modules.m00_approval_center.service import default_service
from .forms import FieldDescriptor
from .schemas import NavigateIn,FillIn,SubmitIn,SubmitExecuteIn
from .service import Service
router=APIRouter(prefix="/browser-agent",tags=["browser-agent"])
_service=None
def get_service():
    global _service
    if _service is None:
        from .playwright_adapter import PlaywrightSessions
        from .store import SQLStore
        _service=Service(PlaywrightSessions(),default_service(),SQLStore())
    return _service
@router.post("/navigate")
async def navigate(body:NavigateIn,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)): return await service.navigate(tenant.tenant_id,body.session_id,body.url,body.persistent)
@router.post("/fill")
async def fill(body:FillIn,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)): return await service.fill(tenant.tenant_id,body.session_id,[FieldDescriptor(**x) for x in body.fields],body.data)
@router.post("/screenshot")
async def screenshot(session_id:str,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)): return {"path":await service.screenshot(tenant.tenant_id,session_id)}
@router.post("/extract")
async def extract(session_id:str,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)): return {"html":await service.extract(tenant.tenant_id,session_id)}
@router.post("/submit/request",status_code=201)
async def request_submit(body:SubmitIn,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)): return await service.request_submit(tenant.tenant_id,tenant.actor_id,body.session_id,body.selector,body.values)
@router.post("/submit/execute")
async def execute_submit(body:SubmitExecuteIn,tenant:TenantContext=Depends(require_tenant),service=Depends(get_service)):
    try:return await service.submit(tenant.tenant_id,body.session_id,body.selector,body.values,body.approval_id)
    except PermissionError as error: raise HTTPException(409,str(error)) from error
