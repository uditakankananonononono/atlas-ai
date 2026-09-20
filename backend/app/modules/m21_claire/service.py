"""Claire PA: sandbox-scoped realization with transparent evidence and approval pauses."""
from __future__ import annotations
import uuid
from dataclasses import dataclass,field
from typing import Any,Protocol
from app.core.models import ApprovalRequest,ApprovalStatus
from app.modules.m20_general_cognitive_worker.service import Service as CognitiveService,Run,State
MODULE_ID=21
class LocalClient(Protocol):
 """Mutual-TLS paired local daemon. The daemon enforces OS permissions and shows on-device approvals."""
 async def capabilities(self)->set[str]:...
 async def preview(self,action:dict[str,Any])->dict[str,Any]:...
 async def execute(self,action:dict[str,Any],approval_token:str|None)->dict[str,Any]:...
 async def audit(self,event:dict[str,Any])->None:...
class ApprovalStore(Protocol):
 def put(self,item:ApprovalRequest)->ApprovalRequest:...
 def list(self)->list[ApprovalRequest]:...
@dataclass
class ClaireGoal:
 goal:str;acceptance:list[str];limits:dict[str,Any];id:str=field(default_factory=lambda:str(uuid.uuid4()));run_id:str|None=None;status:str="draft";artifacts:list[dict[str,Any]]=field(default_factory=list);evidence:list[dict[str,Any]]=field(default_factory=list);escalation:str|None=None
class Service:
 FORBIDDEN=("self-bot","bot evasion","ban evasion","oceanofpdf","pirated","piracy","fabricate application","invent activity","fake credential","rotating proxy","login scrape","login-driven scraping","disable approval","illegal")
 def __init__(self,cognitive:CognitiveService,approvals:ApprovalStore,local_client:LocalClient|None=None,max_retries:int=3):self.cognitive,self.approvals,self.local_client,self.max_retries=cognitive,approvals,local_client,min(5,max(1,max_retries));self.goals={}
 def intake(self,goal:str,acceptance:list[str],limits:dict[str,Any]):
  if any(x in goal.lower() for x in self.FORBIDDEN):raise ValueError("goal conflicts with Claire's operating boundaries")
  item=ClaireGoal(goal,acceptance,{"environment":"atlas","optional_capabilities":["paired_local_pc"],"max_retries":self.max_retries,**limits});self.goals[item.id]=item;return item
 async def realize(self,goal_id:str):
  item=self.goals[goal_id];budget=item.limits.get("budget",{"seconds":1800,"tokens":200000,"money":0})
  run=await self.cognitive.start(item.goal,{"acceptance":item.acceptance,"environment":"atlas","optional_paired_local_pc":self.local_client is not None,"bounded_retries":self.max_retries,"local_control_requires_user_consent":True,"external_messages_and_spend_require_per_action_approval":True},budget);item.run_id=run.id;item.status=run.status.value;item.evidence=[{"phase":t.phase,"summary":t.summary,"evidence":t.evidence,"decision":t.decision,"policy_basis":t.policy_basis} for t in run.traces]
  if run.status in {State.FAILED,State.BLOCKED}:item.escalation="Claire paused after bounded attempts or an unmet approval/dependency. User decision required."
  return item
 def request_environment_change(self,goal_id:str,operation:str,preview:dict[str,Any]):
  if operation not in {"install_package","write_file","move_file","delete_file","type_text","click","browser_navigate","run_command","deploy_preview","connect_tool","send_message","spend_money"}:raise ValueError("local operation not supported")
  req=self.approvals.put(ApprovalRequest(id=str(uuid.uuid4()),module_id=MODULE_ID,action_type=f"claire:{operation}",payload={"goal_id":goal_id,"environment":"paired_local_pc","preview":preview,"rollback":"restore pre-change snapshot"}))
  return req
 async def local_action(self,goal_id:str,action:dict[str,Any],approval_token:str|None=None):
  if not self.local_client:raise RuntimeError("no signed local client is paired")
  kind=action.get("kind","")
  if any(x in repr(action).lower() for x in self.FORBIDDEN):raise ValueError("action conflicts with Claire boundaries")
  capabilities=await self.local_client.capabilities()
  if kind not in capabilities:raise ValueError("local capability was not granted by the user")
  preview=await self.local_client.preview(action)
  high_risk=kind in {"delete_file","install_package","run_command","deploy_preview","connect_tool","send_message","spend_money"} or action.get("external_effect",False)
  if high_risk and not approval_token:
   return self.request_environment_change(goal_id,kind,preview)
  result=await self.local_client.execute(action,approval_token)
  await self.local_client.audit({"goal_id":goal_id,"action":action,"preview":preview,"result":result})
  self.goals[goal_id].evidence.append({"local_action":kind,"preview":preview,"result":result})
  return result
 def supervise_atlas(self,runs:list[Run]):return self.cognitive.supervisor.assess(runs)
