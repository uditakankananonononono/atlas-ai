from typing import Any
from fastapi import APIRouter,HTTPException,Depends
from app.auth.context import TenantContext,require_tenant
from .meta_transfer import TransferLearner
router=APIRouter(prefix='/meta-transfer',tags=['m20-meta-transfer'])
_learners={}
def bind_learner(value):
    if not isinstance(value,TransferLearner):raise ValueError('TransferLearner required')
    _learners[value.tenant_id]=value
def learner(tenant:TenantContext=Depends(require_tenant)):
    value=_learners.get(tenant.tenant_id)
    if value is None or value.tenant_id!=tenant.tenant_id:raise HTTPException(503,'transfer learner not bound for authenticated tenant')
    return value
@router.post('/learn')
def learn(data:dict[str,Any],store=Depends(learner)):
    try:return store.learn(data)
    except ValueError as exc:raise HTTPException(422,str(exc))from exc
    except RuntimeError as exc:raise HTTPException(409,str(exc))from exc
@router.post('/transfer')
def transfer(data:dict[str,Any],store=Depends(learner)):return store.transfer(data)
