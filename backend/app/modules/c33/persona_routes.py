"""S2.12 supplied-sample style guidance, never real-person impersonation."""
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .persona import profile
router=APIRouter(prefix='/c33',tags=['S2.12'])

@router.post('/persona')
def persona(request:dict,tenant:TenantContext=Depends(require_tenant)):
    if not {'field','samples'}<=set(request) or set(request)-{'field','samples','real_person'}:
        raise HTTPException(400,'SOCIAL_REFUSED_FIELDS')
    try:return profile(**request)
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc
