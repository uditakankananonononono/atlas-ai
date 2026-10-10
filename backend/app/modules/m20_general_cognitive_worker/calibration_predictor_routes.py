from typing import Any
from fastapi import APIRouter,HTTPException,Depends
from app.auth.context import TenantContext,require_tenant
from .calibration_predictor import CalibrationPredictor
router=APIRouter(prefix='/calibration-predictor',tags=['m20-calibration-predictor'])
_predictors={}
def bind_predictor(value):
    if not isinstance(value,CalibrationPredictor):raise ValueError('CalibrationPredictor required')
    _predictors[value.tenant_id]=value
def predictor(tenant:TenantContext=Depends(require_tenant)):
    value=_predictors.get(tenant.tenant_id)
    if value is None or value.tenant_id!=tenant.tenant_id:raise HTTPException(503,'predictor not bound for authenticated tenant')
    return value
def call(action,*args,**kwargs):
    try:return action(*args,**kwargs)
    except (ValueError,TypeError)as exc:raise HTTPException(422,str(exc))from exc
    except RuntimeError as exc:raise HTTPException(409,str(exc))from exc
@router.post('/ingest')
def ingest(data:dict[str,Any],store=Depends(predictor)):return call(store.ingest,data.get('records'))
@router.post('/predict')
def predict(data:dict[str,Any],store=Depends(predictor)):return call(store.predict,**data)
