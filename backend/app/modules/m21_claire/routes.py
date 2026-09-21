from fastapi import APIRouter,Depends,HTTPException
from app.core.approvals import approvals
from app.modules.m20_general_cognitive_worker.routes import get_service as cognitive_service
from .schemas import GoalIn,EnvironmentChangeIn
from .service import Service
router=APIRouter(prefix="/claire",tags=["claire"]);_service=None
def get_service():
 global _service
 if _service is None:_service=Service(cognitive_service(),approvals)
 return _service
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
_pairing=PairingService()
class PairConfirmIn(BaseModel):
 server_nonce:str;code:str;name:str;certificate_fingerprint:str;capabilities:set[str]
@router.post('/devices/pairing-challenge')
def pairing_challenge(ttl_seconds:int=300):
 c=_pairing.challenge(max(60,min(ttl_seconds,600)));return {'server_nonce':c.server_nonce,'code':c.code,'expires_at':c.expires_at}
@router.post('/devices/pair')
def pair_device(body:PairConfirmIn):
 try:return _pairing.confirm(body.server_nonce,body.code,body.name,body.certificate_fingerprint,body.capabilities)
 except (KeyError,ValueError) as e:raise HTTPException(422,str(e))
@router.get('/devices')
def devices():return list(_pairing.devices.values())
@router.delete('/devices/{device_id}')
def revoke_device(device_id:str):
 try:_pairing.revoke(device_id);return {'device_id':device_id,'revoked':True}
 except KeyError:raise HTTPException(404,'device not found')

class DeviceReceiptIn(BaseModel):events:list[dict[str,Any]]=Field(min_length=1,max_length=10000)
@router.post('/devices/{device_id}/verify-receipt')
def verify_device_receipt(device_id:str,body:DeviceReceiptIn):
 try:return _pairing.verify_receipt(device_id,body.events)
 except KeyError:raise HTTPException(404,'device not found')
 except ValueError as error:raise HTTPException(422,str(error)) from error
