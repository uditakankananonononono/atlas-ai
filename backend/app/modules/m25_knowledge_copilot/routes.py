from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .schemas import *
from .service import Repository,Service
router=APIRouter(prefix='/knowledge-copilot',tags=['knowledge-copilot']); _service=Service(Repository())
def service():return _service
def call(fn,*args):
 try:return fn(*args)
 except KeyError as e:raise HTTPException(404,str(e))
 except PermissionError as e:raise HTTPException(403,str(e))
 except (ValueError,RuntimeError) as e:raise HTTPException(409,str(e))
@router.post('/sessions',response_model=SessionView,status_code=201)
def start(data:CaptureStart,t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return s.start_capture(t.tenant_id,t.actor_id,data)
@router.get('/sessions/{sid}',response_model=SessionView)
def get(sid:str,t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return call(s.view,t.tenant_id,t.actor_id,sid)
@router.post('/sessions/{sid}/state/{state}',response_model=SessionView)
def state(sid:str,state:CaptureState,t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return call(s.recording_state,t.tenant_id,t.actor_id,sid,state)
@router.post('/sessions/{sid}/audio',response_model=SessionView)
def audio(sid:str,data:AudioStart,t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return call(s.start_audio,t.tenant_id,t.actor_id,sid,data)
@router.post('/sessions/{sid}/timeline',response_model=TimelineItem,status_code=201)
def ingest(sid:str,data:IngestEvent,t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return call(s.ingest,t.tenant_id,t.actor_id,sid,data)
@router.post('/sessions/{sid}/copilot',response_model=CopilotDraft)
def copilot(sid:str,data:CopilotRequest,t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return call(s.copilot,t.tenant_id,t.actor_id,sid,data)
@router.post('/sessions/{sid}/claims',response_model=list[ClaimEvidence])
def claims(sid:str,data:list[ClaimInput],t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return call(s.claim_table,t.tenant_id,t.actor_id,sid,data)
@router.post('/approvals',response_model=ApprovalRecord,status_code=201)
def proposal(data:ApprovalRequest,t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return s.propose(t.tenant_id,t.actor_id,data)
@router.post('/approvals/{rid}/decision',response_model=ApprovalRecord)
def decision(rid:str,data:ApprovalDecision,t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return call(s.decide,t.tenant_id,t.actor_id,rid,data)
@router.post('/sessions/{sid}/failures',response_model=SessionView)
def failure(sid:str,data:FailureReport,t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return call(s.failure,t.tenant_id,t.actor_id,sid,data)
@router.get('/audit')
def audit(t:TenantContext=Depends(require_tenant),s:Service=Depends(service)):return s.audit_log(t.tenant_id,t.actor_id)

class ArtifactEventIn(BaseModel):
 event:dict
@router.post('/artifact-events/validate')
def validate_artifact_event(data:ArtifactEventIn,t:TenantContext=Depends(require_tenant)):
 from .artifact_events import ingest_artifact_event
 try:
  event={**data.event,'tenant_id':t.tenant_id}
  return ingest_artifact_event(event)
 except ValueError as error:raise HTTPException(422,str(error)) from error
