from typing import Any
from fastapi import APIRouter,HTTPException,Depends
from app.auth.context import TenantContext,require_tenant
from .curiosity_investigator import CuriosityInvestigator
router=APIRouter(prefix='/curiosity-investigator',tags=['m20-curiosity-investigator'])
_investigators={}
def bind_investigator(value):
    if not isinstance(value,CuriosityInvestigator):raise ValueError('CuriosityInvestigator required')
    _investigators[value.tenant_id]=value
def investigator(tenant:TenantContext=Depends(require_tenant)):
    value=_investigators.get(tenant.tenant_id)
    if value is None or value.tenant_id!=tenant.tenant_id:raise HTTPException(503,'investigator not bound for authenticated tenant')
    return value
def call(action,*args,**kwargs):
    try:return action(*args,**kwargs)
    except (ValueError,TypeError,OverflowError)as exc:raise HTTPException(422,str(exc))from exc
    except RuntimeError as exc:raise HTTPException(409,str(exc))from exc
@router.post('/authorize')
def authorize(data:dict[str,Any],store=Depends(investigator)):return call(store.authorize,**data)
@router.post('/enqueue')
def enqueue(data:dict[str,Any],store=Depends(investigator)):return call(store.enqueue,data.get('records'))
@router.post('/run')
def run(data:dict[str,Any],store=Depends(investigator)):return call(store.run,**data)
@router.get('/queue')
def queue(store=Depends(investigator)):return {'queue':call(store.queue),'boundary':store.boundary}
