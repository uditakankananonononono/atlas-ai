"""Optional authenticated C3 surface. Integrator mounts this router explicitly.

Reports are ephemeral, latest-only per bound tenant; no caller controls tenant.
Bind only the expected finite tenant set. No unbounded report history.
"""
from copy import deepcopy
from threading import RLock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from app.auth.context import TenantContext, require_tenant
from .c3_layers import Refusal, run

router = APIRouter(prefix='/api/v1/c31/layers', tags=['c3-layers'])
_lock = RLock()
_reports: dict[str, dict | None] = {}


def bind_layers_tenant(tenant_id: str):
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError('nonempty tenant required')
    with _lock:
        if tenant_id not in _reports and len(_reports) >= 128:
            raise ValueError('C3 tenant capacity reached')
        _reports.setdefault(tenant_id, None)


def bound(tenant: TenantContext = Depends(require_tenant)):
    with _lock:
        if tenant.tenant_id not in _reports:
            raise HTTPException(503, 'C3 not bound for authenticated tenant')
    return tenant


@router.post('/run')
def run_layers(packet: dict[str, Any], tenant: TenantContext = Depends(bound)):
    try:
        result = run(packet)
    except Refusal as exc:
        raise HTTPException(422, {'code': exc.code, 'detail': str(exc)}) from exc
    with _lock:
        _reports[tenant.tenant_id] = deepcopy(result)
    return result


@router.get('/report')
def report_layers(tenant: TenantContext = Depends(bound)):
    with _lock:
        result = _reports[tenant.tenant_id]
        if result is None:
            raise HTTPException(404, 'No C3 report for authenticated tenant')
        return deepcopy(result)
