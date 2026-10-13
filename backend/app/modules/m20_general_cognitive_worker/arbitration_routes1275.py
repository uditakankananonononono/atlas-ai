"""Authenticated mounted arbitration declaration bookkeeping, no legal decisions."""
import json
from fastapi import APIRouter,Depends,HTTPException,Request
from app.auth.context import TenantContext,require_tenant
from . import arbitration1275
router=APIRouter(prefix='/arbitration/1275',tags=['m20-arbitration-1275'])
MAX_BODY_BYTES=32768

def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate key')
        result[key]=value
    return result

def _reject_constant(value):raise ValueError('non-finite JSON number')

@router.post('/organize')
async def organize(request:Request,principal:TenantContext=Depends(require_tenant)):
    media=request.headers.get('content-type','').split(';',1)[0].strip().lower()
    if media!='application/json':raise HTTPException(415,'ARB1275:application/json required')
    body=bytearray()
    async for chunk in request.stream():
        if len(body)+len(chunk)>MAX_BODY_BYTES:raise HTTPException(413,'ARB1275:body exceeds byte limit')
        body.extend(chunk)
    try:
        payload=json.loads(body.decode('utf-8'),object_pairs_hook=_unique_object,parse_constant=_reject_constant)
    except (UnicodeDecodeError,ValueError,RecursionError):
        raise HTTPException(422,'ARB1275:INVALID_JSON') from None
    try:result=arbitration1275.organize(payload)
    except ValueError as exc:raise HTTPException(422,str(exc)) from None
    return {**result,'tenant_id':principal.tenant_id,'actor_id':principal.actor_id}
