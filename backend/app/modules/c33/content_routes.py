"""Authenticated draft composition only, no posting/account effects."""
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .content import compose
router=APIRouter(prefix='/c33',tags=['S2.11'])
@router.post('/content')
def content(request:dict,tenant:TenantContext=Depends(require_tenant)):
    try:return compose(request)
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc
