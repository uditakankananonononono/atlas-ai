from fastapi import APIRouter,Depends,HTTPException
from app.core.approvals import approvals
from app.modules.m20_general_cognitive_worker.routes import get_service as cognitive_service
from .schemas import GoalIn,EnvironmentChangeIn
from .service import Service
router=APIRouter(prefix="/claire",tags=["claire"]);_services={};_service=None  # _service: legacy hook, a bound shared Service (tests/hosts)
MAX_TENANT_SERVICES=64  # finite, fail closed (no silent eviction of another tenant's in-memory goals)
import threading
from app.auth.context import TenantContext,require_tenant as _rt
_lock=threading.Lock()
async def get_service(ctx:TenantContext=Depends(_rt)):
 """Per-tenant Claire Service (in-memory, lost on restart). The tenant resolved by require_tenant is also set for the
 m20 cognitive service lookup, which refuses requests without a tenant. NOTE: the approvals store is still the process
 global core facade (known gap), so approvals are not tenant-partitioned here."""
 from app.modules.m20_general_cognitive_worker.routes import _tenant_var
 token=_tenant_var.set(ctx.tenant_id)
 try:
  if _service is not None:yield _service;return
  with _lock:
   s=_services.get(ctx.tenant_id)
   if s is None:
    if len(_services)>=MAX_TENANT_SERVICES:raise HTTPException(503,"Claire in-memory service capacity reached")
    s=_services[ctx.tenant_id]=Service(cognitive_service(),approvals)
  yield s
 finally:_tenant_var.reset(token)
@router.post("/goals",status_code=201)
def intake(req:GoalIn,s:Service=Depends(get_service)):
 try:return s.intake(req.goal,req.acceptance,req.limits)
 except ValueError as e:raise HTTPException(422,str(e))
@router.post("/goals/{goal_id}/realize")
async def realize(goal_id:str,s:Service=Depends(get_service)):
 try:return await s.realize(goal_id)
 except KeyError:raise HTTPException(404,"goal not found")
@router.post("/goals/{goal_id}/environment-changes",status_code=201)
def environment_change(goal_id:str,req:EnvironmentChangeIn,s:Service=Depends(get_service)):
 if goal_id not in s.goals:raise HTTPException(404,"goal not found")
 try:return s.request_environment_change(goal_id,req.operation,req.preview)
 except ValueError as e:raise HTTPException(422,str(e))

from typing import Any
from pydantic import BaseModel,Field
from app.auth.context import TenantContext,require_tenant
from .owner_workflow_279_329 import claire_owner_workflow_279_329,preference_feedback_4_6_9
class ClaireOwnerWorkflowIn(BaseModel):
    row_id:int=Field(ge=279,le=329)
    data:dict[str,Any]=Field(default_factory=dict)
class ClairePreferenceFeedbackIn(BaseModel):
    feature_id:int
    data:dict[str,Any]=Field(default_factory=dict)
@router.post('/owner-workflow-279-329')
def claire_owner_workflow_route(body:ClaireOwnerWorkflowIn,tenant:TenantContext=Depends(require_tenant)):
    try:return {'tenant_id':tenant.tenant_id,**claire_owner_workflow_279_329(body.row_id,body.data)}
    except ValueError as error:raise HTTPException(422,str(error)) from error
@router.post('/preference-feedback-4-6-9')
def claire_preference_feedback_route(body:ClairePreferenceFeedbackIn,tenant:TenantContext=Depends(require_tenant)):
    try:return {'tenant_id':tenant.tenant_id,**preference_feedback_4_6_9(body.feature_id,body.data)}
    except ValueError as error:raise HTTPException(422,str(error)) from error

# Strong bounded workflows for owner atomic concepts 1.1-3.1.
from .atomic_concepts_routes_1_23 import router as atomic_concepts_router_1_23
router.include_router(atomic_concepts_router_1_23)

from .atomic_concepts_routes_24_46 import router as atomic_concepts_router_24_46
router.include_router(atomic_concepts_router_24_46)
from .atomic_concepts_routes_47_69 import router as atomic_concepts_router_47_69
router.include_router(atomic_concepts_router_47_69)

from .local_client_protocol import PairingService
from pydantic import BaseModel
_pairings={}
def _pair(ctx:TenantContext=Depends(require_tenant)):
 with _lock:
  if ctx.tenant_id not in _pairings and len(_pairings)>=MAX_TENANT_SERVICES:raise HTTPException(503,'Claire pairing capacity reached')
  return _pairings.setdefault(ctx.tenant_id,PairingService())
class PairConfirmIn(BaseModel):
 server_nonce:str;code:str;name:str;certificate_fingerprint:str;capabilities:set[str]
@router.post('/devices/pairing-challenge')
def pairing_challenge(ttl_seconds:int=300,_pairing:PairingService=Depends(_pair)):
 c=_pairing.challenge(max(60,min(ttl_seconds,600)));return {'server_nonce':c.server_nonce,'code':c.code,'expires_at':c.expires_at}
@router.post('/devices/pair')
def pair_device(body:PairConfirmIn,_pairing:PairingService=Depends(_pair)):
 try:return _pairing.confirm(body.server_nonce,body.code,body.name,body.certificate_fingerprint,body.capabilities)
 except (KeyError,ValueError) as e:raise HTTPException(422,str(e))
@router.get('/devices')
def devices(_pairing:PairingService=Depends(_pair)):return list(_pairing.devices.values())
@router.delete('/devices/{device_id}')
def revoke_device(device_id:str,_pairing:PairingService=Depends(_pair)):
 try:_pairing.revoke(device_id);return {'device_id':device_id,'revoked':True}
 except KeyError:raise HTTPException(404,'device not found')

class DeviceReceiptIn(BaseModel):events:list[dict[str,Any]]=Field(min_length=1,max_length=10000)
@router.post('/devices/{device_id}/verify-receipt')
def verify_device_receipt(device_id:str,body:DeviceReceiptIn,_pairing:PairingService=Depends(_pair)):
 try:return _pairing.verify_receipt(device_id,body.events)
 except KeyError:raise HTTPException(404,'device not found')
 except ValueError as error:raise HTTPException(422,str(error)) from error
