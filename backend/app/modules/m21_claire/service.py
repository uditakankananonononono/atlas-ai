"""Claire PA: sandbox-scoped realization with transparent evidence and approval pauses."""
from __future__ import annotations
import copy,hashlib,json,math,uuid
from datetime import datetime
from dataclasses import dataclass,field
from typing import Any,Protocol
from app.core.models import ApprovalRequest,ApprovalStatus
from .models import ActionRequest
from .policy import ActionPolicy
from app.modules.m00_approval_center.service import ApprovalConflictError,ApprovalNotFoundError
from app.modules.m20_general_cognitive_worker.service import Service as CognitiveService,Run,State
MODULE_ID=21
PENDING_REVIEW_TTL_SECONDS=24*3600   # review window for a PENDING request (Module 0 expires only pending rows)
APPROVED_VALIDITY_SECONDS=15*60      # how long an APPROVED permit may be consumed: 0 <= now - decided_at <= 900s, inclusive
class LocalActionOutcomeUnknown(RuntimeError):
 """Raised after a permit was consumed and the client call failed: the effect may or may not have happened."""
def _nonblank(v)->bool:return isinstance(v,str) and bool(v.strip())
def _plain_json(v:Any)->Any:
 """Strict plain JSON (no tuples, bytes, NaN, non-str keys); returns an independent deep copy."""
 def chk(x):
  if x is None or isinstance(x,(bool,str,int)):return
  if isinstance(x,float):
   if math.isfinite(x):return
  elif isinstance(x,list):
   for y in x:chk(y)
   return
  elif isinstance(x,dict):
   for k,y in x.items():
    if not isinstance(k,str):raise ValueError("local action must be plain JSON")
    chk(y)
   return
  raise ValueError("local action must be plain JSON")
 if not isinstance(v,dict):raise ValueError("local action must be plain JSON")
 chk(v);return json.loads(json.dumps(v))
def _canonical(v:Any)->str:return json.dumps(v,sort_keys=True,separators=(",",":"))
class LocalClient(Protocol):
 """Mutual-TLS paired local daemon. The daemon enforces OS permissions and shows on-device approvals."""
 async def capabilities(self)->set[str]:...
 async def preview(self,action:dict[str,Any])->dict[str,Any]:...
 async def execute(self,action:dict[str,Any],approval_token:str|None)->dict[str,Any]:...
 async def audit(self,event:dict[str,Any])->None:...
class ApprovalStore(Protocol):
 def put(self,item:ApprovalRequest,*,ttl_seconds:int|None=None)->ApprovalRequest:...
 def list(self)->list[ApprovalRequest]:...
@dataclass
class ClaireGoal:
 goal:str;acceptance:list[str];limits:dict[str,Any];id:str=field(default_factory=lambda:str(uuid.uuid4()));run_id:str|None=None;status:str="draft";artifacts:list[dict[str,Any]]=field(default_factory=list);evidence:list[dict[str,Any]]=field(default_factory=list);escalation:str|None=None
class Service:
 FORBIDDEN=("self-bot","bot evasion","ban evasion","oceanofpdf","pirated","piracy","fabricate application","invent activity","fake credential","rotating proxy","login scrape","login-driven scraping","disable approval","illegal","lie on my behalf","lie for me","deceive","false statement","impersonate deceptively")
 def __init__(self,cognitive:CognitiveService,approvals:ApprovalStore,local_client:LocalClient|None=None,max_retries:int=3):self.cognitive,self.approvals,self.local_client,self.max_retries=cognitive,approvals,local_client,min(5,max(1,max_retries));self.goals={};self._owners={}
 def intake(self,goal:str,acceptance:list[str],limits:dict[str,Any],*,tenant_id:str|None=None,actor_id:str|None=None):
  if any(x in goal.lower() for x in self.FORBIDDEN):raise ValueError("goal conflicts with Claire's operating boundaries")
  item=ClaireGoal(goal,acceptance,{"environment":"atlas","optional_capabilities":["paired_local_pc"],"max_retries":self.max_retries,**limits});self.goals[item.id]=item;self._owners[item.id]=(tenant_id,actor_id);return item
 def owned(self,goal_id:str,tenant_id:str,actor_id:str)->ClaireGoal:
  """Goal lookup scoped to tenant+actor. Another principal's goal is indistinguishable from a missing one."""
  item=self.goals[goal_id]
  if self._owners.get(goal_id)!=(tenant_id,actor_id):raise KeyError(goal_id)
  return item
 async def realize(self,goal_id:str):
  item=self.goals[goal_id];budget=item.limits.get("budget",{"seconds":1800,"tokens":200000,"money":0})
  run=await self.cognitive.start(item.goal,{"acceptance":item.acceptance,"environment":"atlas","optional_paired_local_pc":self.local_client is not None,"bounded_retries":self.max_retries,"local_control_requires_user_consent":True,"external_messages_and_spend_require_per_action_approval":True},budget);item.run_id=run.id;item.status=run.status.value;item.evidence=[{"phase":t.phase,"summary":t.summary,"evidence":t.evidence,"decision":t.decision,"policy_basis":t.policy_basis} for t in run.traces]
  if run.status in {State.FAILED,State.BLOCKED}:item.escalation="Claire paused after bounded attempts or an unmet approval/dependency. User decision required."
  return item
 def request_environment_change(self,goal_id:str,operation:str,preview:dict[str,Any],*,tenant_id:str|None=None,extra:dict[str,Any]|None=None,ttl_seconds:int|None=None):
  if operation not in {"install_package","uninstall_package","write_file","read_file","move_file","copy_file","delete_file","type_text","click","scroll","browser_navigate","browser_download","run_command","run_workflow","deploy_preview","connect_tool","send_message","spend_money"}:raise ValueError("local operation not supported")
  item=ApprovalRequest(id=str(uuid.uuid4()),module_id=MODULE_ID,action_type=f"claire:{operation}",payload={**({"tenant_id":tenant_id} if tenant_id else {}),"goal_id":goal_id,"environment":"paired_local_pc","preview":preview,"rollback":"restore pre-change snapshot",**(extra or {})})
  return self.approvals.put(item,ttl_seconds=ttl_seconds) if ttl_seconds else self.approvals.put(item)
 def _local_goal(self,goal_id:str,tenant_id:str|None,actor_id:str|None):
  """Owner check for local_action, before anything else. Legacy = no owner record or (None,None): only (None,None) callers."""
  item=self.goals[goal_id];owner=self._owners.get(goal_id,(None,None))
  if owner==(None,None):
   if tenant_id is not None or actor_id is not None:raise KeyError(goal_id)
  elif not(_nonblank(tenant_id) and _nonblank(actor_id)) or owner!=(tenant_id,actor_id):raise KeyError(goal_id)
  return item,owner
 def _verify_local_approval(self,approval_id:str,kind:str,goal_id:str,digest:str,tenant_id:str|None,actor_id:str|None):
  """Returns (view, stored payload deep copy). Any shortfall is one fixed refusal; no exception text is surfaced."""
  refuse=ValueError("local action approval refused")
  if not _nonblank(approval_id) or not _nonblank(tenant_id) or not _nonblank(actor_id) or not hasattr(self.approvals,"full_view") or not hasattr(self.approvals,"consume_effect"):raise refuse
  try:view=self.approvals.full_view(approval_id)
  except (ApprovalNotFoundError,KeyError):raise refuse from None
  if not isinstance(view,dict):raise refuse
  payload=view.get("payload");status=view.get("status");by=view.get("approved_by")
  if (isinstance(view.get("module_id"),bool) or view.get("module_id")!=MODULE_ID or view.get("action_type")!=f"claire:{kind}" or view.get("user_id")!=tenant_id
      or not isinstance(payload,dict) or payload.get("goal_id")!=goal_id or payload.get("action_digest")!=digest
      or str(getattr(status,"value",status))!="approved" or not isinstance(view.get("decided_at"),datetime)
      or not _nonblank(by) or by.strip()==actor_id.strip() or not isinstance(payload.get("preview"),dict)):raise refuse
  return view,copy.deepcopy(payload)
 async def local_action(self,goal_id:str,action:dict[str,Any],approval_token:str|None=None,*,tenant_id:str|None=None,actor_id:str|None=None):
  if not self.local_client:raise RuntimeError("no signed local client is paired")
  snap=_plain_json(action)                    # immutable snapshot BEFORE any await; digest/preview/consume/execute all use it
  item,_owner=self._local_goal(goal_id,tenant_id,actor_id)
  kind=snap.get("kind","")
  if any(x in repr(snap).lower() for x in self.FORBIDDEN):raise ValueError("action conflicts with Claire boundaries")
  capabilities=await self.local_client.capabilities()
  if kind not in capabilities:raise ValueError("local capability was not granted by the user")
  preview=_plain_json(await self.local_client.preview(copy.deepcopy(snap)))
  high_risk=kind in {"delete_file","install_package","uninstall_package","run_command","run_workflow","deploy_preview","connect_tool","send_message","spend_money"} or snap.get("external_effect",False)
  tags=snap.get("policy_tags",())
  verdict=ActionPolicy().evaluate(ActionRequest("local",str(kind),{"policy_tags":list(tags) if isinstance(tags,(list,tuple,set,frozenset)) else []},"local action"))
  if not verdict.allowed:raise ValueError("action conflicts with Claire boundaries")
  high_risk=high_risk or verdict.requires_approval
  digest=hashlib.sha256(json.dumps({"goal_id":goal_id,"kind":kind,"action":snap},sort_keys=True,separators=(",",":")).encode()).hexdigest()
  if high_risk and not approval_token:
   return self.request_environment_change(goal_id,kind,preview,tenant_id=tenant_id,extra={"action_digest":digest},ttl_seconds=PENDING_REVIEW_TTL_SECONDS)
  if not high_risk:
   result=await self.local_client.execute(copy.deepcopy(snap),approval_token)
   await self.local_client.audit({"goal_id":goal_id,"action":copy.deepcopy(snap),"preview":preview,"result":result})
   item.evidence.append({"local_action":kind,"preview":preview,"result":result})
   return result
  view,stored=self._verify_local_approval(approval_token,kind,goal_id,digest,tenant_id,actor_id)
  reviewed=stored.get("preview")
  if _canonical(reviewed)!=_canonical(preview):raise ValueError("local action approval refused")   # fresh preview differs from the reviewed one: fresh review required
  effect_id=str(uuid.uuid4())
  try:permit=self.approvals.consume_effect(approval_token,module_id=MODULE_ID,action_type=f"claire:{kind}",payload=stored,user_id=view["user_id"],effect_id=effect_id,actor=actor_id,max_age_seconds=APPROVED_VALIDITY_SECONDS)
  except (ApprovalNotFoundError,ApprovalConflictError,ValueError):raise ValueError("local action approval refused") from None
  if not isinstance(permit,dict) or permit.get("allowed") is not True or permit.get("approval_id")!=approval_token or permit.get("effect_id")!=effect_id:raise ValueError("local action approval refused")
  entry={"local_action":kind,"approval_id":approval_token,"outcome":"unknown"};item.evidence.append(entry)   # intent marker; consumed approval is never refunded
  try:result=await self.local_client.execute(copy.deepcopy(snap),approval_token)
  except Exception as cause:raise LocalActionOutcomeUnknown("local action outcome unknown; reconcile before any retry") from cause
  entry.clear();entry.update({"local_action":kind,"approval_id":approval_token,"preview":preview,"result":result})
  try:await self.local_client.audit({"goal_id":goal_id,"action":copy.deepcopy(snap),"preview":preview,"result":result})
  except Exception:entry["audit"]="audit_failed"
  return result
 def supervise_atlas(self,runs:list[Run]):return self.cognitive.supervisor.assess(runs)
