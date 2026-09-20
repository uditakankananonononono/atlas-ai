"""Stage-gated idea portfolio with budget limits, evidence ledger and approval-gated previews."""
from __future__ import annotations
import json,uuid
from typing import Awaitable,Callable,Protocol
from app.core.models import ApprovalRequest
from .schemas import *
GenerateFn=Callable[...,Awaitable[tuple[str,str]]]; MODULE_ID=19
class ApprovalStore(Protocol):
 def put(self,item:ApprovalRequest)->ApprovalRequest: ...
class Service:
 def __init__(self,*,generate:GenerateFn,approval_store:ApprovalStore,provider:str="openai",model:str|None=None):self._generate=generate;self._approvals=approval_store;self._provider=provider;self._model=model;self._runs:dict[str,RunOut]={}
 async def intake(self,request:IntakeIn)->RunOut:
  prompt="Return lean canvas JSON. Label riskiest assumptions. Do not invent traction, users or evidence. INPUT="+request.model_dump_json()
  _,answer=await self._generate(prompt,self._provider,self._model);canvas=LeanCanvasOut.model_validate_json(answer);rid=str(uuid.uuid4());run=RunOut(id=rid,state="queued",stage=Stage.LANDSCAPE,canvas=canvas,gates=[GateOut(stage=Stage.INTAKE,proceed=True,reasons=["intake normalized"],missing_evidence=canvas.riskiest_assumptions,expected_cost=0)],budget_cap=request.budget_cap);self._runs[rid]=run;return run
 def get(self,run_id:str)->RunOut:
  if run_id not in self._runs:raise KeyError(run_id)
  return self._runs[run_id]
 def request_preview(self,run_id:str,request:PreviewIn)->ApprovalRequest:
  run=self.get(run_id)
  if run.spent+request.estimated_cost>run.budget_cap:raise ValueError("budget cap exceeded")
  item=ApprovalRequest(id=str(uuid.uuid4()),module_id=MODULE_ID,action_type="deploy_sandbox_preview",payload={"run_id":run_id,"artifacts":request.artifacts,"estimated_cost":request.estimated_cost,"effect":"Creates an externally reachable sandbox preview; never production."})
  run.state="pending_approval";run.stage=Stage.PREVIEW;return self._approvals.put(item)
 async def package(self,request:PackageIn)->PackageOut:
  run=self.get(request.run_id);prompt="Return viability package JSON with evidence-backed recommendation, confidence, unresolved risks, and cheapest next experiments. Never fabricate links or market facts. INPUT="+json.dumps({"canvas":run.canvas.model_dump(),"evidence":request.evidence,"artifacts":request.artifacts});_,answer=await self._generate(prompt,self._provider,self._model);return PackageOut.model_validate_json(answer)
