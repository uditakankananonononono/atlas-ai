"""J1 optional authenticated API. Explicit host paths only; no caller paths."""
from typing import Any
from threading import RLock
from fastapi import APIRouter, Depends, HTTPException
from app.auth.context import TenantContext, require_tenant
from app.modules.c30 import policy
from .j1_forecast import ForecastLedger, ForecastRefusal

router = APIRouter(prefix='/api/v1/c37/forecast', tags=['j1-forecast'])
_ledgers = {}
_lock = RLock()


def bind_forecast_ledger(ledger):
    if not isinstance(ledger, ForecastLedger):
        raise ValueError('ForecastLedger required')
    with _lock:
        if ledger.tenant_id not in _ledgers and len(_ledgers) >= 128:
            raise ValueError('J1 bound tenant cap reached')
        if any(other.tenant_id != ledger.tenant_id and other.path.resolve() == ledger.path.resolve()
               for other in _ledgers.values()):
            raise ValueError('J1 ledger path already bound to another tenant')
        _ledgers[ledger.tenant_id] = ledger


def bound(tenant: TenantContext = Depends(require_tenant)):
    with _lock:
        value = _ledgers.get(tenant.tenant_id)
        if value is None or value.tenant_id != tenant.tenant_id:
            raise HTTPException(503, 'J1 ledger not bound for authenticated tenant')
        return value


def error(exc):
    code = exc.code if isinstance(exc, ForecastRefusal) else str(exc).split(':')[0]
    raise HTTPException(422, {'code': code, 'detail': str(exc)}) from exc


@router.post('/run')
def run_forecast(packet: dict[str, Any], ledger: ForecastLedger = Depends(bound)):
    action = packet.get('action')
    if action not in ('predict', 'resolve'):
        try:
            policy.check(str(action), 'INTEL')
        except ValueError as exc:
            error(exc)
    expected = {'action', 'claim', 'probability', 'horizon', 'source', 'made_at'} if action == 'predict' else {'action', 'prediction_id', 'outcome', 'resolved_at'}
    if action == 'predict' and ('horizon' not in packet or packet['horizon'] is None or packet['horizon'] == ''):
        error(ForecastRefusal('INTEL_REFUSED_NOHORIZON', 'prediction requires an explicit horizon'))
    if set(packet) != expected:
        error(ForecastRefusal('INTEL_REFUSED_SCHEMA', 'request fields mismatch'))
    data = {k: v for k, v in packet.items() if k != 'action'}
    try:
        row = ledger.append_prediction(**data) if action == 'predict' else ledger.resolve(**data)
    except ForecastRefusal as exc:
        error(exc)
    return {'unit': 'J1', 'kind': 'prediction' if action == 'predict' else 'resolution', 'record': row,
            'scope': policy.scope(['append-only supplied prediction or outcome'], ['verified outcome', 'future skill', 'market feed', 'trade execution'],
                                  'supplied input', row.get('made_at', row.get('resolved_at')))}


@router.get('/report')
def report_forecast(calibrated: bool = True, bins: int = 10, ledger: ForecastLedger = Depends(bound)):
    try:
        return ledger.report(calibrated=calibrated, bins=bins)
    except ForecastRefusal as exc:
        error(exc)
