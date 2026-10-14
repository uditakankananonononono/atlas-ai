"""S2.10 supplied taxonomy enumeration, no viral outcome claim."""
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .niches import generate
router=APIRouter(prefix='/c33',tags=['S2.10'])

@router.post('/niches')
def niches(request:dict,tenant:TenantContext=Depends(require_tenant)):
    if not {'taxonomy','audiences','formats'}<=set(request) or set(request)-{'taxonomy','audiences','formats','scores'}:
        raise HTTPException(400,'SOCIAL_REFUSED_FIELDS')
    try:return generate(**request)
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc
