"""Authenticated saved-text scanner; no live crawling or installation."""
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .tool_scan import scan_sources
router=APIRouter(prefix='/c31',tags=['S1.1'])
@router.post('/tool-scan')
def tool_scan(request:dict,tenant:TenantContext=Depends(require_tenant)):
    try:return scan_sources(request)
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc
