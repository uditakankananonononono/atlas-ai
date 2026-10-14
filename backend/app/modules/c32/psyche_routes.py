"""S2.9 supplied-text cue analysis; no claims of feeling or diagnosis."""
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .psyche import tag_evidence
router=APIRouter(prefix='/c32',tags=['S2.9'])

@router.post('/psyche')
def psyche(request:dict,tenant:TenantContext=Depends(require_tenant)):
    if set(request)!={'text'}:raise HTTPException(400,'TREND_REFUSED_FIELDS')
    try:return tag_evidence(request['text'])
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc
