"""Authenticated supplied-taxonomy audit, not real industry creation."""
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .industry import run
router=APIRouter(prefix='/c34',tags=['S3.4'])
@router.post('/industry')
def industry(request:dict,tenant:TenantContext=Depends(require_tenant)):
    try:return run(request)
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc
