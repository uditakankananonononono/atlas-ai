"""Generate draft canvas/package text locally; persist truth, not imagined execution."""
from __future__ import annotations
import hashlib,json,uuid
from datetime import datetime,timezone,timedelta
from typing import Awaitable,Callable,Protocol
from pydantic import ValidationError
from app.core.providers import ProviderError
from app.core.models import ApprovalRequest
from .schemas import *
from .run_repository import RunRepository,RunConflict
GenerateFn=Callable[...,Awaitable[tuple[str,str]]]; MODULE_ID=19
class ApprovalStore(Protocol):
 def put(self,item:ApprovalRequest)->ApprovalRequest: ...
def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
class Service:
 def __init__(self,*,generate:GenerateFn,approval_store:ApprovalStore,provider:str='ollama',model:str|None=None,repository=None,tenant_id='local'):
  self._generate=generate;self._approvals=approval_store;self._provider=provider;self._model=model
  self.repository=repository or RunRepository(tenant_id)
 async def intake(self,request:IntakeIn,idempotency_key:str|None=None)->RunOut:
  key=idempotency_key or str(uuid.uuid4())
  if not key.strip() or len(key)>200:raise ValueError('idempotency key must be 1..200 characters')
  run,created=self.repository.begin(key,digest(request.model_dump(mode='json')),request.budget_cap)
  if not created:
   if run.state in {'unavailable','invalid_model_output'}:raise ProviderError((run.error or 'intake failed')+'; run_id='+run.id)
   return run
  prompt='Return lean canvas JSON. All statements are unverified hypotheses. Do not invent traction, users or evidence. INPUT='+request.model_dump_json()
  try:
   model,answer=await self._generate(prompt,self._provider,self._model)
   run.canvas=LeanCanvasOut.model_validate_json(answer)
  except (ProviderError,ValidationError) as exc:
   run.state='unavailable' if isinstance(exc,ProviderError) else 'invalid_model_output'
   run.error='local model unavailable or not configured' if isinstance(exc,ProviderError) else 'model returned invalid canvas JSON'
   run.lease_expires_at=None;self.repository.save(run,run.version,'intake_failed',{'error':run.error})
   raise ProviderError(run.error+'; no canvas fabricated; run_id='+run.id) from exc
  run.state='awaiting_evidence';run.lease_expires_at=None
  run.gates=[GateOut(stage=Stage.INTAKE,proceed=False,reasons=['draft canvas only; downstream stage executors unavailable'],missing_evidence=run.canvas.riskiest_assumptions,expected_cost=0)]
  return self.repository.save(run,run.version,'canvas_generated',{'provider':self._provider,'model':model,'verified_market_evidence':False})
 def get(self,run_id):return self.repository.get(run_id)
 def request_preview(self,run_id:str,request:PreviewIn)->ApprovalRequest:
  run=self.get(run_id); hashed=digest(request.model_dump(mode='json'))
  if run.preview_request_hash:
   if run.preview_request_hash!=hashed:raise RunConflict('different preview already requested')
   if run.approval:return ApprovalRequest.model_validate(run.approval)
   raise RunConflict('preview request unresolved; reconcile approval store before retrying')
  if run.state!='awaiting_evidence':raise RunConflict('run is not ready for preview review')
  if run.spent+request.estimated_cost>run.budget_cap:raise ValueError('budget cap exceeded')
  run.state='preview_requesting';run.preview_request_hash=hashed;run.lease_expires_at=datetime.now(timezone.utc)+timedelta(minutes=3)
  run=self.repository.save(run,run.version,'preview_review_requested',request.model_dump(mode='json'))
  item=ApprovalRequest(id=str(uuid.uuid4()),module_id=MODULE_ID,action_type='deploy_sandbox_preview',payload={'tenant_id':self.repository.tenant_id,'run_id':run_id,'artifacts':request.artifacts,'estimated_cost':request.estimated_cost,'effect':'Approval request only. No preview deployment consumer is implemented.','executor_available':False})
  try:item=self._approvals.put(item)
  except Exception:
   run.state='approval_reconciliation_required';run.lease_expires_at=None;run.error='approval submission uncertain; no automatic retry'
   self.repository.save(run,run.version,'preview_approval_uncertain');raise
  run.state='pending_approval';run.lease_expires_at=None;run.approval=item.model_dump(mode='json')
  self.repository.save(run,run.version,'preview_approval_recorded',{'approval_id':item.id,'executed':False})
  return item
 async def package(self,request:PackageIn)->PackageOut:
  run=self.get(request.run_id);hashed=digest(request.model_dump(mode='json'))
  if run.package_request_hash:
   if run.package_request_hash!=hashed:raise RunConflict('different package request already recorded')
   if run.package:return PackageOut.model_validate(run.package)
   raise RunConflict('package generation unresolved or failed; no automatic retry')
  if run.state!='awaiting_evidence' or run.canvas is None:raise RunConflict('canvas is not available or run is busy')
  run.package_request_hash=hashed;run.state='package_generating';run.lease_expires_at=datetime.now(timezone.utc)+timedelta(minutes=3)
  run=self.repository.save(run,run.version,'package_requested',{'supplied_evidence':request.evidence,'supplied_artifacts':request.artifacts,'provenance':'caller_supplied_unverified'})
  try:
   model,answer=await self._generate('Return draft viability package JSON. Never fabricate links or market facts. INPUT='+json.dumps({'canvas':run.canvas.model_dump(),'evidence':request.evidence,'artifacts':request.artifacts}),self._provider,self._model)
   result=PackageOut.model_validate_json(answer)
   result.execution_status='draft_unverified';result.format='json';result.pdf_rendered=False
   # Model text is not authority that a prototype exists.
   if result.prototype_preview is not None or not set(result.prototype_artifacts)<=set(request.artifacts):raise ValueError('unverified prototype output')
  except (ProviderError,ValidationError,ValueError) as exc:
   run.state='package_failed';run.error='local model unavailable or invalid package output';run.lease_expires_at=None
   self.repository.save(run,run.version,'package_failed',{'error':run.error})
   raise ProviderError(run.error) from exc
  run.state='awaiting_evidence';run.lease_expires_at=None;run.package=result.model_dump(mode='json')
  self.repository.save(run,run.version,'package_json_generated',{'model':model,'pdf_rendered':False,'claims_verified':False})
  return result
