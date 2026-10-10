"""Explicit owner-triggered capture; unsupported capture is unavailable, not fallback."""
import os
from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from app.auth.context import TenantContext,require_tenant
from .snapshots import SnapshotService,SnapshotError
router=APIRouter(prefix='/portfolio/ranking-snapshots',tags=['idea-incubator-snapshots'])
class SnapshotParameters(BaseModel):
    model_config=ConfigDict(extra='forbid')
    as_of:datetime
    half_life_days:float=Field(default=90.0,gt=0,le=3650)
    include_terminal:bool=False
    limit:int|None=Field(default=None,ge=1,le=500)
    stale_experiment_policy:str='exclude'
def get_snapshot_service():
    version=os.getenv('ATLAS_CODE_VERSION','')
    if not version:raise HTTPException(503,'configured deployed code version required')
    return SnapshotService(code_version=version)
def failure(exc):
    text=str(exc)
    status=404 if text=='snapshot unavailable' else 503 if 'REPEATABLE READ' in text else 409 if 'capacity' in text or 'transaction conflict' in text else 422
    return HTTPException(status,text)
@router.post('',status_code=201)
def capture(body:SnapshotParameters,ctx:TenantContext=Depends(require_tenant),svc=Depends(get_snapshot_service)):
    try:return svc.capture(ctx,**body.model_dump())
    except SnapshotError as exc:raise failure(exc) from exc
@router.post('/find')
def find(body:SnapshotParameters,ctx:TenantContext=Depends(require_tenant),svc=Depends(get_snapshot_service)):
    try:return svc.find(ctx,**body.model_dump())
    except SnapshotError as exc:raise failure(exc) from exc
@router.get('/{sid}')
def read(sid:str,ctx:TenantContext=Depends(require_tenant),svc=Depends(get_snapshot_service)):
    try:return svc.get(ctx,sid)
    except SnapshotError as exc:raise failure(exc) from exc
@router.get('/{sid}/compare')
def compare(sid:str,ctx:TenantContext=Depends(require_tenant),svc=Depends(get_snapshot_service)):
    try:return svc.compare(ctx,sid)
    except SnapshotError as exc:raise failure(exc) from exc
