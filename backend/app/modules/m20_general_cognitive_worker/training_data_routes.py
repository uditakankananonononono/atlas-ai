"""Mount at /api/v1. Server-installed permits only; reports isolated by tenant.

No transport is exposed by these routes. Source rights cannot be granted by a client.
"""
from copy import deepcopy
from threading import RLock
from fastapi import APIRouter, Depends, HTTPException
from app.auth.context import TenantContext, require_tenant
from .training_data_units import TrainingUnits, Refusal
router=APIRouter(tags=['training-data-T1-T4'])
_STORES={}
_LOCK=RLock()
_PATHS={'T1':'/c35/case-corpus','T2':'/c20/m22/search','T3':'/c32/books','T4':'/c31/advice-first'}

def bind_training_units(tenant_id,engine):
    if not isinstance(tenant_id,str) or not tenant_id or not isinstance(engine,TrainingUnits):raise ValueError('tenant and engine required')
    with _LOCK:_STORES[tenant_id]={'engine':engine,'reports':{}}

def _store(tenant):
    with _LOCK:store=_STORES.get(tenant.tenant_id)
    if store is None:raise HTTPException(503,'training engine not configured for authenticated tenant')
    return store

def _endpoints(unit):
    def run(payload:dict,tenant:TenantContext=Depends(require_tenant)):
        store=_store(tenant)
        try:report=store['engine'].run(unit,payload)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        with _LOCK:store['reports'][unit]=deepcopy(report)
        return report
    def report(tenant:TenantContext=Depends(require_tenant)):
        store=_store(tenant)
        with _LOCK:value=deepcopy(store['reports'].get(unit))
        if value is None:raise HTTPException(404,'no report for tenant and unit')
        return value
    run.__name__='run_'+unit;report.__name__='report_'+unit
    return run,report

for unit,path in _PATHS.items():
    run,report=_endpoints(unit)
    router.add_api_route(path+'/run',run,methods=['POST'])
    router.add_api_route(path+'/report',report,methods=['GET'])


def configure_training_units(tenant_id, permits):
    """Server-only setup for supplied offline records; never grants source rights."""
    from app.modules.c30 import policy
    policy.clean_text(tenant_id, 'POLICY', 'tenant_id', 120)
    # Copy the caller's explicit permits. No registry candidates become grants.
    def offline_policy(action):
        allowed_keys = {'type'} | set(policy.RULES)
        if set(action) - allowed_keys:
            raise Refusal('POLICY_REFUSED_BAD_DESCRIPTOR:action')
        for flag in policy.RULES:
            if flag in action and type(action[flag]) is not bool:
                raise Refusal('POLICY_REFUSED_BAD_DESCRIPTOR:action')
            if action.get(flag) is True:
                policy.check(flag, 'POLICY')
        descriptor = {'class': 'offline', 'module_id': 20,
                      'tenant_id': tenant_id, 'action_type': action.get('type', 'analyze'),
                      'payload': deepcopy(action)}
        decision = policy.classify(descriptor)
        if decision['decision'] != 'allow':
            raise Refusal(decision['code'] or 'POLICY_REFUSED_ACTION')
        return True
    engine = TrainingUnits(permits=deepcopy(permits), policy=offline_policy)
    bind_training_units(tenant_id, engine)


def mount_training_routes(app):
    """Mount fail-closed handlers; unconfigured tenants remain unavailable."""
    app.include_router(router, prefix='/api/v1', dependencies=[Depends(require_tenant)])
