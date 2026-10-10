from typing import Any
from fastapi import APIRouter,HTTPException,Depends
from app.auth.context import TenantContext,require_tenant
from .digital_twin import TwinRegistry
router=APIRouter(prefix='/digital-twins',tags=['m20-digital-twins'])
_registries={}
def bind_registry(registry):
    if not isinstance(registry,TwinRegistry):raise ValueError('TwinRegistry required')
    _registries[registry.tenant_id]=registry
def registry(tenant:TenantContext=Depends(require_tenant)):
    found=_registries.get(tenant.tenant_id)
    if found is None or found.tenant_id!=tenant.tenant_id:raise HTTPException(503,'twin registry not bound for authenticated tenant')
    return found
def call(action,*args,**kwargs):
    try:return action(*args,**kwargs)
    except ValueError as exc:raise HTTPException(422,str(exc))from exc
    except KeyError as exc:raise HTTPException(404,str(exc))from exc
    except TypeError as exc:raise HTTPException(422,'malformed twin parameters')from exc
@router.post('',status_code=201)
def create(data:dict[str,Any],store=Depends(registry)):return call(store.create,**data)
@router.get('/{name}')
def get(name:str,store=Depends(registry)):return call(store.get,name)
@router.post('/{name}/assimilate')
def assimilate(name:str,data:dict[str,Any],store=Depends(registry)):return call(store.assimilate,name,**data)
@router.post('/{name}/forecast')
def forecast(name:str,data:dict[str,Any],store=Depends(registry)):return call(store.forecast,name,**data)
