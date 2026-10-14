"""S3.3 authenticated scaffold drafts, no execution or delivery side effect."""
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .tool import run
router=APIRouter(prefix='/c34',tags=['S3.3'])
@router.post('/tool')
def tool(request:dict,tenant:TenantContext=Depends(require_tenant)):
    try:return run(request)
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc
