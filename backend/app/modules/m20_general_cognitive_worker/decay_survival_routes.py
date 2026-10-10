from typing import Any
from fastapi import APIRouter,HTTPException,Depends
from app.auth.context import TenantContext,require_tenant
from .decay_survival import DecaySurvival
router=APIRouter(prefix='/decay-survival',tags=['m20-decay-survival'])
_models={}
def bind_model(value):
    if not isinstance(value,DecaySurvival):raise ValueError('DecaySurvival required')
    _models[value.tenant_id]=value
def model(tenant:TenantContext=Depends(require_tenant)):
    value=_models.get(tenant.tenant_id)
    if value is None or value.tenant_id!=tenant.tenant_id:raise HTTPException(503,'model not bound for authenticated tenant')
    return value
def call(action,*args,**kwargs):
    try:return action(*args,**kwargs)
    except (ValueError,TypeError,OverflowError)as exc:raise HTTPException(422,str(exc))from exc
    except RuntimeError as exc:raise HTTPException(409,str(exc))from exc
@router.post('/ingest')
def ingest(data:dict[str,Any],store=Depends(model)):return call(store.ingest,data.get('records'))
@router.post('/forecast')
def forecast(data:dict[str,Any],store=Depends(model)):return call(store.forecast,**data)
@router.post('/track')
def track(data:dict[str,Any],store=Depends(model)):return call(store.track,**data)
@router.post('/refresh')
def refresh(data:dict[str,Any],store=Depends(model)):return call(store.refresh,**data)
@router.post('/evaluate')
def evaluate(data:dict[str,Any],store=Depends(model)):return call(store.evaluate,**data)
