from typing import Any
from fastapi import APIRouter,HTTPException,Depends
from app.auth.context import TenantContext,require_tenant
from .bayesian_models import BayesianModelRegistry
router=APIRouter(prefix='/bayesian-models',tags=['m20-bayesian-models'])
_registries={}
def bind_registry(value):
    if not isinstance(value,BayesianModelRegistry):raise ValueError('BayesianModelRegistry required')
    _registries[value.tenant_id]=value
def registry(tenant:TenantContext=Depends(require_tenant)):
    value=_registries.get(tenant.tenant_id)
    if value is None or value.tenant_id!=tenant.tenant_id:raise HTTPException(503,'registry not bound for authenticated tenant')
    return value
def call(action,*args,**kwargs):
    try:return action(*args,**kwargs)
    except (ValueError,TypeError)as exc:raise HTTPException(422,str(exc))from exc
    except RuntimeError as exc:raise HTTPException(409,str(exc))from exc
@router.post('/configure')
def configure(data:dict[str,Any],store=Depends(registry)):return call(store.configure,**data)
@router.post('/evidence')
def evidence(data:dict[str,Any],store=Depends(registry)):return call(store.ingest,data.get('records'))
@router.get('')
def compare(store=Depends(registry)):return call(store.compare)
