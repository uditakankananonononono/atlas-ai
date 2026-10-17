"""Stage-gated idea portfolio with budget limits, evidence ledger and approval-gated previews."""
from __future__ import annotations
import hashlib,json,uuid
from threading import RLock
from typing import Awaitable,Callable,Protocol
from app.core.models import ApprovalRequest
from .idempotency import IdempotencyConflictError,IdempotencyInProgressError,IdempotencyUnavailableError,IntakeIdempotencyStore
from .run_store import SqlRunStore
from .schemas import *
GenerateFn=Callable[...,Awaitable[tuple[str,str]]]; MODULE_ID=19
class ApprovalStore(Protocol):
 def put(self,item:ApprovalRequest)->ApprovalRequest: ...
class Service:
 def __init__(self,*,generate:GenerateFn,approval_store:ApprovalStore,provider:str="openai",model:str|None=None,idempotency_store=None,run_store=None):self._generate=generate;self._idempotency=idempotency_store;self._store=run_store if run_store is not None else SqlRunStore();self._approvals=approval_store;self._provider=provider;self._model=model;self._runs:dict[str,RunOut]={};self._owners:dict[str,str]={};self._budget_lock=RLock()
 def _default_store(self)->SqlRunStore:
  # tenant-scoped calls go to the durable store; legacy tenantless calls stay process-local (pre-run-store API)
  return self._store
 async def intake(self,request:IntakeIn,tenant_id:str|None=None,idempotency_key:str|None=None)->RunOut:
  if idempotency_key is not None and tenant_id is None:raise ValueError("idempotency requires a tenant")
  dump=request.model_dump(mode='json',exclude={'idempotency_key'});claimed=False
  if idempotency_key is not None:
   digest=hashlib.sha256(json.dumps({'tenant_id':tenant_id,'request':dump},sort_keys=True).encode()).hexdigest()
   outcome,row=self._idempotency.claim(tenant_id,idempotency_key,digest)
   if outcome=="conflict":raise IdempotencyConflictError("idempotency key belongs to another request")
   if outcome=="in_progress":raise IdempotencyInProgressError("a request with this idempotency key is still in progress")
   if outcome=="replay":
    if self._default_store().get(tenant_id,row.run_id) is not None:return RunOut.model_validate(row.response_json)
    raise IdempotencyUnavailableError("the recorded run is process-local and unavailable after restart; the completed receipt is preserved and needs restoration or reconciliation - resubmission with a new key would repeat a completed, possibly charged generation")
   claimed=True
  prompt="Return lean canvas JSON. Label riskiest assumptions. Do not invent traction, users or evidence. INPUT="+json.dumps(dump)
  _,answer=await self._generate(prompt,self._provider,self._model);canvas=LeanCanvasOut.model_validate_json(answer);rid=str(uuid.uuid4());run=RunOut(id=rid,state="queued",stage=Stage.LANDSCAPE,canvas=canvas,gates=[GateOut(stage=Stage.INTAKE,proceed=True,reasons=["intake normalized"],missing_evidence=canvas.riskiest_assumptions,expected_cost=0)],budget_cap=request.budget_cap)
  if tenant_id is None:self._runs[rid]=run;self._owners[rid]=tenant_id
  else:self._default_store().create(tenant_id,run,priority=request.priority)
  if claimed:self._idempotency.complete(tenant_id,idempotency_key,rid,run.model_dump(mode='json'))
  return run
 def get(self,run_id:str,tenant_id:str|None=None)->RunOut:
  if tenant_id is None:
   if run_id not in self._runs or self._owners.get(run_id)!=tenant_id:raise KeyError(run_id)
   return self._runs[run_id]
  run=self._default_store().get(tenant_id,run_id)
  if run is None:raise KeyError(run_id)
  return run
 def request_preview(self,run_id:str,request:PreviewIn,tenant_id:str|None=None)->ApprovalRequest:
  if tenant_id is None:
   with self._budget_lock:
    run=self.get(run_id,tenant_id)
    if run.spent+run.reserved+request.estimated_cost>run.budget_cap:raise ValueError("budget cap exceeded")
    item=ApprovalRequest(id=str(uuid.uuid4()),module_id=MODULE_ID,action_type="deploy_sandbox_preview",payload={"run_id":run_id,"artifacts":request.artifacts,"estimated_cost":request.estimated_cost,"effect":"Creates an externally reachable sandbox preview; never production."})
    stored=self._approvals.put(item)
    run.reserved+=request.estimated_cost;run.state="pending_approval";run.stage=Stage.PREVIEW;return stored
  self._default_store().reserve_budget(tenant_id,run_id,request.estimated_cost,"pending_approval",Stage.PREVIEW,expected_stages=[request.expected_stage] if request.expected_stage is not None else None)
  item=ApprovalRequest(id=str(uuid.uuid4()),module_id=MODULE_ID,action_type="deploy_sandbox_preview",payload={"run_id":run_id,"tenant_id":tenant_id,"artifacts":request.artifacts,"estimated_cost":request.estimated_cost,"effect":"Creates an externally reachable sandbox preview; never production."})
  try:return self._approvals.put(item)
  except Exception:
   # Unknown outcome: the approval request may have been accepted before the failure surfaced.
   # Never auto-release an unknown reservation; explicit grounded reconciliation only.
   raise
 async def package(self,request:PackageIn,tenant_id:str|None=None)->PackageOut:
  run=self.get(request.run_id,tenant_id);prompt="Return viability package JSON with evidence-backed recommendation, confidence, unresolved risks, and cheapest next experiments. Never fabricate links or market facts. INPUT="+json.dumps({"canvas":run.canvas.model_dump(),"evidence":request.evidence,"artifacts":request.artifacts});_,answer=await self._generate(prompt,self._provider,self._model);result=PackageOut.model_validate_json(answer)
  if result.prototype_preview is not None:
   raise ValueError("prototype preview requires a verified deployment receipt; model links are refused")
  if not request.evidence and (result.market_claims or result.recommendation_confidence > 0.5):
   raise ValueError("high confidence/market claims require supplied evidence")
  if any(artifact not in request.artifacts for artifact in result.prototype_artifacts):
   raise ValueError("prototype artifacts must come from supplied artifacts")
  return result
