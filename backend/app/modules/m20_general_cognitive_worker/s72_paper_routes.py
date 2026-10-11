"""Optional S7.2 authenticated API: no submitted Python code or broker hooks."""
from copy import deepcopy
from threading import RLock
from typing import Any
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .s72_paper import run,PaperRefusal

router=APIRouter(prefix='/api/v1/c36/paper',tags=['s72-paper'])
_lock=RLock();_reports={}

def bind_paper_tenant(tenant_id):
    if not isinstance(tenant_id,str) or not tenant_id.strip():raise ValueError('tenant required')
    with _lock:
        if tenant_id not in _reports and len(_reports)>=128:raise ValueError('tenant cap')
        _reports.setdefault(tenant_id,None)

def bound(tenant:TenantContext=Depends(require_tenant)):
    with _lock:
        if tenant.tenant_id not in _reports:raise HTTPException(503,'paper unit not bound for authenticated tenant')
    return tenant

def buy_hold(history):return 1.0

def moving_average(history):
    # Uses only five fully completed bars. No fitting on future data.
    if len(history)<5:return 0.0
    return float(history[-1]['close']>sum(b['close'] for b in history[-5:])/5)

STRATEGIES={'cash':lambda history:0.0,'buy_hold':buy_hold,'moving_average_5':moving_average}

@router.post('/run')
def run_paper(packet:dict[str,Any],tenant:TenantContext=Depends(bound)):
    data=deepcopy(packet);strategy_id=data.pop('strategy_id','cash')
    if not isinstance(strategy_id,str) or strategy_id not in STRATEGIES:
        raise HTTPException(422,{'code':'MONEY_REFUSED_STRATEGY','detail':'known built-in strategy_id required; no submitted code'})
    try:result=run(data,strategy=STRATEGIES[strategy_id])
    except ValueError as exc:
        raise HTTPException(422,{'code':getattr(exc,'code',str(exc).split(':')[0]),'detail':str(exc)}) from exc
    result['strategy_id']=strategy_id
    with _lock:_reports[tenant.tenant_id]=deepcopy(result)
    return result

@router.get('/report')
def report_paper(tenant:TenantContext=Depends(bound)):
    with _lock:
        result=_reports[tenant.tenant_id]
        if result is None:raise HTTPException(404,'no paper report for authenticated tenant')
        return deepcopy(result)
