"""S3.2 authenticated static source generator; rendered quality is not scored."""
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .site import run
router=APIRouter(prefix='/c34',tags=['S3.2'])
@router.post('/site')
def site(request:dict,tenant:TenantContext=Depends(require_tenant)):
    try:return run(request)
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc
