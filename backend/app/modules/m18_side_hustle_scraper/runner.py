"""Step-by-step, artifact-first hustle experiment runner.

Preparation is automatic and reversible. Every external effect is represented as
an exact action payload and independently gated through Module 0. This module
never posts, messages, purchases, or spends.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass,field
from enum import Enum
from hashlib import sha256
from typing import Any
from uuid import uuid4
from app.modules.m00_approval_center.service import Service as ApprovalService,default_service

class StepState(str,Enum):
 READY="ready";BLOCKED="blocked_for_approval";COMPLETED="completed"
@dataclass
class ExperimentStep:
 id:str;kind:str;title:str;artifact:dict[str,Any];external_action:dict[str,Any]|None=None
 state:StepState=StepState.READY;approval_id:str|None=None
@dataclass
class HustleRun:
 id:str;title:str;hypothesis:str;max_budget:float;steps:list[ExperimentStep]=field(default_factory=list);receipts:list[dict[str,Any]]=field(default_factory=list);outcomes:list[dict[str,Any]]=field(default_factory=list)

def _id(run_id:str,kind:str)->str:return sha256(f"{run_id}:{kind}".encode()).hexdigest()[:20]
class HustleRunner:
 def __init__(self,approvals:ApprovalService|None=None):self.approvals=approvals or default_service();self._runs={}
 def create(self,*,title:str,first_experiment:str,max_budget:float=0,source_urls:list[str]|None=None)->HustleRun:
  if not title.strip() or not first_experiment.strip():raise ValueError("title and first_experiment are required")
  if max_budget<0:raise ValueError("max_budget cannot be negative")
  rid=str(uuid4());sources=source_urls or []
  specs=[
   ("landing_page","Draft landing page",{"format":"markdown","headline":title,"problem":first_experiment,"call_to_action":"Join the no-obligation interest list","source_urls":sources},{"action_type":"publish_landing_page","destination":"owner_selected","content":"review landing-page artifact"}),
   ("listing","Draft marketplace listing",{"format":"markdown","title":title,"description":first_experiment,"price":"owner must choose","status":"draft"},{"action_type":"publish_listing","destination":"owner_selected","content":"review listing artifact"}),
   ("outreach","Draft customer outreach",{"format":"text","audience":"owner must choose exact recipients","message":f"I'm testing {title}. {first_experiment}","status":"draft"},{"action_type":"send_outreach","recipients":[],"content":"review outreach artifact"}),
   ("budget","Budget plan",{"currency":"owner must choose","cap":max_budget,"items":[],"spend_authorized":False},{"action_type":"spend_test_budget","amount_cap":max_budget,"merchant":"owner_selected"}),
   ("measurement","Measurement checklist",{"hypothesis":first_experiment,"metrics":["qualified interest","conversion","actual spend","owner time"],"stop_conditions":["budget cap reached","owner stops run","harm or policy concern"],"observations":[]},None),
  ]
  run=HustleRun(rid,title,first_experiment,max_budget,[ExperimentStep(_id(rid,k),k,t,a,e) for k,t,a,e in specs]);self._runs[rid]=run;return run
 def get(self,run_id:str)->HustleRun:
  if run_id not in self._runs:raise KeyError(run_id)
  return self._runs[run_id]
 def complete_preparation(self,run_id:str,step_id:str)->ExperimentStep:
  step=self._step(run_id,step_id)
  if step.external_action:raise ValueError("external-effect steps require per-action approval")
  step.state=StepState.COMPLETED;return step
 def request_action(self,run_id:str,step_id:str,user_id:str)->ExperimentStep:
  step=self._step(run_id,step_id)
  if not step.external_action:raise ValueError("step has no external action")
  payload={"run_id":run_id,"step_id":step.id,"artifact":step.artifact,"exact_action":step.external_action}
  gate=self.approvals.gate(module_id=18,action_type=step.external_action["action_type"],payload=payload,user_id=user_id,idempotency_key=f"m18:{run_id}:{step.id}")
  step.approval_id=gate["approval"]["id"] if gate.get("approval") else None;step.state=StepState.BLOCKED;return step
 def authorize_action(self,run_id:str,step_id:str,user_id:str,actor:str)->dict[str,Any]:
  step=self._step(run_id,step_id)
  if not step.approval_id or not step.external_action:raise ValueError("step has no reviewed approval")
  payload={"run_id":run_id,"step_id":step.id,"artifact":step.artifact,"exact_action":step.external_action}
  permit=self.approvals.consume_effect(step.approval_id,module_id=18,action_type=step.external_action["action_type"],payload=payload,user_id=user_id,effect_id=f"m18:{run_id}:{step.id}",actor=actor)
  step.state=StepState.COMPLETED
  return {"permit":permit,"action":step.external_action,"artifact":step.artifact,"executed":False,"note":"permit only; a separately configured official adapter must perform the exact action"}
 def record_adapter_receipt(self,run_id:str,step_id:str,*,adapter:str,provider_receipt_id:str,status:str,observed_at:str,payload_sha256:str)->dict[str,Any]:
  step=self._step(run_id,step_id)
  if step.state is not StepState.COMPLETED or not step.approval_id:raise ValueError("a consumed approval is required before recording an adapter receipt")
  if status not in {"succeeded","failed","unknown"}:raise ValueError("receipt status must be succeeded, failed, or unknown")
  if len(payload_sha256)!=64 or any(c not in "0123456789abcdef" for c in payload_sha256.lower()):raise ValueError("payload_sha256 must be a SHA-256 hex digest")
  receipt={"step_id":step_id,"approval_id":step.approval_id,"adapter":adapter,"provider_receipt_id":provider_receipt_id,"status":status,"observed_at":observed_at,"payload_sha256":payload_sha256.lower()}
  receipt["receipt_sha256"]=sha256(repr(sorted(receipt.items())).encode()).hexdigest();self.get(run_id).receipts.append(receipt);return receipt
 def record_outcome(self,run_id:str,*,metric:str,value:float,unit:str,observed_at:str,source_url:str|None=None,receipt_sha256:str|None=None)->dict[str,Any]:
  run=self.get(run_id)
  if not metric.strip() or not unit.strip() or not observed_at.strip():raise ValueError("metric, unit, and observed_at are required")
  if receipt_sha256 and receipt_sha256 not in {x["receipt_sha256"] for x in run.receipts}:raise ValueError("outcome receipt does not belong to this run")
  outcome={"metric":metric,"value":value,"unit":unit,"observed_at":observed_at,"source_url":source_url,"receipt_sha256":receipt_sha256,"claim":"observed input; not independently verified by Atlas"}
  run.outcomes.append(outcome);return outcome
 def _step(self,run_id,step_id):
  run=self.get(run_id)
  for step in run.steps:
   if step.id==step_id:return step
  raise KeyError(step_id)
 def view(self,run:HustleRun)->dict[str,Any]:
  data=asdict(run)
  for s in data["steps"]:s["state"]=s["state"].value if isinstance(s["state"],StepState) else s["state"]
  return data

import json,sqlite3
from pathlib import Path
class DurableRunStore:
 """Tenant-partitioned durable snapshots for runs, receipts and outcomes."""
 def __init__(self,path:str|Path):
  self.path=str(path)
  with self._db() as db:db.execute('CREATE TABLE IF NOT EXISTS hustle_runs(tenant_id TEXT NOT NULL,run_id TEXT NOT NULL,snapshot TEXT NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(tenant_id,run_id))')
 def _db(self):
  db=sqlite3.connect(self.path);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL');return db
 def save(self,tenant_id:str,run:HustleRun)->None:
  data=asdict(run)
  for step in data['steps']:step['state']=step['state'].value if isinstance(step['state'],StepState) else step['state']
  with self._db() as db:db.execute('INSERT INTO hustle_runs(tenant_id,run_id,snapshot) VALUES(?,?,?) ON CONFLICT(tenant_id,run_id) DO UPDATE SET snapshot=excluded.snapshot,updated_at=CURRENT_TIMESTAMP',(tenant_id,run.id,json.dumps(data,sort_keys=True,separators=(',',':'))))
 def load(self,tenant_id:str,run_id:str)->HustleRun:
  with self._db() as db:row=db.execute('SELECT snapshot FROM hustle_runs WHERE tenant_id=? AND run_id=?',(tenant_id,run_id)).fetchone()
  if not row:raise KeyError(run_id)
  d=json.loads(row[0]);steps=[ExperimentStep(id=x['id'],kind=x['kind'],title=x['title'],artifact=x['artifact'],external_action=x.get('external_action'),state=StepState(x['state']),approval_id=x.get('approval_id')) for x in d['steps']]
  return HustleRun(d['id'],d['title'],d['hypothesis'],d['max_budget'],steps,d.get('receipts',[]),d.get('outcomes',[]))
 def list(self,tenant_id:str)->list[HustleRun]:
  with self._db() as db:ids=[x[0] for x in db.execute('SELECT run_id FROM hustle_runs WHERE tenant_id=? ORDER BY updated_at DESC',(tenant_id,)).fetchall()]
  return [self.load(tenant_id,x) for x in ids]
class DurableHustleRunner(HustleRunner):
 def __init__(self,tenant_id:str,store:DurableRunStore,approvals:ApprovalService|None=None):super().__init__(approvals);self.tenant_id=tenant_id;self.store=store
 def get(self,run_id:str)->HustleRun:
  if run_id not in self._runs:self._runs[run_id]=self.store.load(self.tenant_id,run_id)
  return self._runs[run_id]
 def persist(self,run_id:str)->HustleRun:
  run=self.get(run_id);self.store.save(self.tenant_id,run);return run
 def create(self,**kwargs)->HustleRun:
  run=super().create(**kwargs);self.store.save(self.tenant_id,run);return run
 def request_action(self,*args,**kwargs):
  step=super().request_action(*args,**kwargs);self.persist(args[0]);return step
 def authorize_action(self,*args,**kwargs):
  result=super().authorize_action(*args,**kwargs);self.persist(args[0]);return result
 def record_adapter_receipt(self,*args,**kwargs):
  result=super().record_adapter_receipt(*args,**kwargs);self.persist(args[0]);return result
 def record_outcome(self,*args,**kwargs):
  result=super().record_outcome(*args,**kwargs);self.persist(args[0]);return result
