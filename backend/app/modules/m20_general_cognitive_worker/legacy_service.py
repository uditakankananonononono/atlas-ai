"""Module 20: evidence-oriented cognitive worker with bounded autonomy."""
from __future__ import annotations

import asyncio, copy, hashlib, json, math, re, uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol

from sqlalchemy.exc import SQLAlchemyError

from app.core.models import ApprovalRequest
from app.modules.m00_approval_center.service import ApprovalConflictError, ApprovalNotFoundError

MODULE_ID=20
PENDING_REVIEW_TTL_SECONDS=24*3600   # review window for a PENDING step approval
APPROVED_VALIDITY_SECONDS=15*60      # valid iff 0 <= now - decided_at <= 900s, inclusive, checked inside Module 0 consume_effect
GATED_RISKS=("external","irreversible")
def now(): return datetime.now(timezone.utc)

class Risk(str,Enum): READ="read"; REVERSIBLE="reversible"; EXTERNAL="external"; IRREVERSIBLE="irreversible"
class State(str,Enum): PENDING="pending"; WAITING_APPROVAL="waiting_approval"; RUNNING="running"; SUCCEEDED="succeeded"; FAILED="failed"; BLOCKED="blocked"

@dataclass
class SensoryEvent:
    source:str; kind:str; payload:dict[str,Any]; external_id:str|None=None; confidence:float=1.; observed_at:datetime=field(default_factory=now); id:str=field(default_factory=lambda:str(uuid.uuid4()))
@dataclass
class Memory:
    kind:str; content:dict[str,Any]; provenance:dict[str,Any]; salience:float=.5; id:str=field(default_factory=lambda:str(uuid.uuid4()))
@dataclass
class Skill:
    name:str; goal_pattern:str; steps:list[dict[str,Any]]; version:int=1; evidence:dict[str,Any]=field(default_factory=dict)
@dataclass
class Tool:
    name:str; description:str; risk:Risk; capabilities:set[str]; handler:Callable[[dict[str,Any],str],Awaitable[dict[str,Any]]]; timeout:int=60; max_retries:int=2
@dataclass
class Step:
    title:str; tool:str|None; arguments:dict[str,Any]; depends_on:set[str]=field(default_factory=set); risk:Risk=Risk.READ; max_attempts:int=3; id:str=field(default_factory=lambda:str(uuid.uuid4())); state:State=State.PENDING; attempts:int=0; approval_id:str|None=None; result:dict[str,Any]|None=None; error:str|None=None; outcome_unknown:bool=False
@dataclass
class Plan:
    goal:str; steps:list[Step]; constraints:dict[str,Any]; id:str=field(default_factory=lambda:str(uuid.uuid4()))
@dataclass
class Trace:
    phase:str; summary:str; evidence:list[dict[str,Any]]; alternatives:list[str]; decision:str; policy_basis:list[str]; at:datetime=field(default_factory=now)
@dataclass
class Run:
    goal:str; budget:dict[str,float]; plan:Plan; id:str=field(default_factory=lambda:str(uuid.uuid4())); status:State=State.PENDING; traces:list[Trace]=field(default_factory=list); spent:dict[str,float]=field(default_factory=lambda:{"seconds":0,"tokens":0,"money":0}); tenant_id:str|None=None; actor_id:str|None=None

class ApprovalStore(Protocol):
    def put(self,item:ApprovalRequest,*,ttl_seconds:int|None=None)->ApprovalRequest: ...
    def list(self)->list[ApprovalRequest]: ...
class Model(Protocol):
    async def __call__(self,purpose:str,payload:dict[str,Any])->dict[str,Any]: ...

class SensoryIngestion:
    def __init__(self,sources:set[str],max_bytes:int=1_000_000): self.sources,self.max_bytes,self.seen=sources,max_bytes,set()
    def ingest(self,event:SensoryEvent)->bool:
        if event.source not in self.sources: raise ValueError("unregistered sensory source")
        if not 0<=event.confidence<=1: raise ValueError("invalid confidence")
        if len(repr(event.payload).encode())>self.max_bytes: raise ValueError("payload too large")
        key=(event.source,event.external_id) if event.external_id else (event.source,event.id)
        if key in self.seen:return False
        self.seen.add(key);return True

class WorkingMemory:
    def __init__(self,token_budget:int=12000): self.token_budget=token_budget;self.items:deque[tuple[str,Any,float,int]]=deque()
    def put(self,key:str,value:Any,salience:float=.5):
        self.items=deque(x for x in self.items if x[0]!=key);self.items.append((key,value,salience,max(1,len(repr(value))//4)))
        while sum(x[3] for x in self.items)>self.token_budget:self.items.remove(min(self.items,key=lambda x:x[2]))
    def context(self):return {x[0]:x[1] for x in sorted(self.items,key=lambda x:x[2],reverse=True)}

class LongTermMemory:
    def __init__(self):self.episodic:list[Memory]=[];self.semantic:list[Memory]=[]
    def remember(self,item:Memory):getattr(self,item.kind).append(item)
    def recall(self,query:str,limit:int=12):
        terms=set(re.findall(r"\w+",query.lower()));all_items=self.episodic+self.semantic
        return sorted(all_items,key=lambda m:(len(terms&set(re.findall(r"\w+",repr(m.content).lower()))),m.salience),reverse=True)[:limit]

class SkillLibrary:
    def __init__(self):self.skills:dict[str,list[Skill]]={}
    def register(self,skill:Skill):
        if not skill.steps:raise ValueError("skill needs steps")
        self.skills.setdefault(skill.name,[]).append(skill)
    def match(self,goal:str):return [v[-1] for v in self.skills.values() if re.search(v[-1].goal_pattern,goal,re.I)]

class HTNPlanner:
    def __init__(self,skills:SkillLibrary,model:Model):self.skills,self.model=skills,model
    async def plan(self,goal:str,constraints:dict[str,Any])->Plan:
        matched=self.skills.match(goal);raw=matched[0].steps if matched else (await self.model("htn_plan",{"goal":goal,"constraints":constraints}))["steps"]
        steps=[Step(x["title"],x.get("tool"),x.get("arguments",{}),set(x.get("depends_on",[])),Risk(x.get("risk","read")),min(5,max(1,x.get("max_attempts",3))),x.get("id",str(uuid.uuid4()))) for x in raw]
        ids={s.id for s in steps}
        if any(not s.depends_on<=ids for s in steps):raise ValueError("unknown dependency")
        self._acyclic(steps);return Plan(goal,steps,constraints)
    @staticmethod
    def _acyclic(steps):
        graph={s.id:s.depends_on for s in steps};active=set();seen=set()
        def visit(n):
            if n in active:raise ValueError("cyclic plan")
            if n in seen:return
            active.add(n)
            for d in graph[n]:visit(d)
            active.remove(n);seen.add(n)
        for n in graph:visit(n)

class ToolRegistry:
    def __init__(self):self.tools:dict[str,Tool]={}
    def register(self,tool:Tool):self.tools[tool.name]=tool
    async def dispatch(self,step:Step,key:str):
        if step.tool is None:return {"ok":True,"note":"cognitive step"}
        tool=self.tools.get(step.tool)
        if not tool:raise ValueError("tool unavailable")
        if tool.risk!=step.risk:raise ValueError("tool risk differs from reviewed plan")
        return await asyncio.wait_for(tool.handler(step.arguments,key),tool.timeout)

class ConcurrencyScheduler:
    def __init__(self,max_parallel:int=6):self.gate=asyncio.Semaphore(max_parallel)
    async def run(self,steps,fn):
        async def one(s):
            async with self.gate:return await fn(s)
        return await asyncio.gather(*(one(s) for s in steps),return_exceptions=True)

def _plain_json(v:Any)->Any:
    """Strict plain JSON (no tuples, bytes, NaN, non-str keys); returns an independent deep copy."""
    def chk(x):
        if x is None or isinstance(x,(bool,str,int)):return
        if isinstance(x,float) and math.isfinite(x):return
        if isinstance(x,list):
            for y in x:chk(y)
            return
        if isinstance(x,dict):
            for k,y in x.items():
                if not isinstance(k,str):raise ValueError("not plain JSON")
                chk(y)
            return
        raise ValueError("not plain JSON")
    chk(v);return json.loads(json.dumps(v))
def _nonblank(v)->bool:return isinstance(v,str) and bool(v.strip())
def step_digest(run_id:str,step_id:str,tool:str|None,risk:str,arguments:dict[str,Any])->str:
    return hashlib.sha256(json.dumps({"run_id":run_id,"step_id":step_id,"tool":tool,"risk":risk,"arguments":arguments},sort_keys=True,separators=(",",":")).encode()).hexdigest()
def _block(step:Step,code:str):
    step.state=State.BLOCKED;step.error=code

class DeliberativeLoop:
    def __init__(self,approvals:ApprovalStore,tools:ToolRegistry,scheduler:ConcurrencyScheduler):self.approvals,self.tools,self.scheduler=approvals,tools,scheduler
    async def execute(self,run:Run)->Run:
        run.status=State.RUNNING;by_id={s.id:s for s in run.plan.steps}
        while True:
            if any(s.state in {State.FAILED,State.BLOCKED} for s in run.plan.steps):run.status=State.BLOCKED;break
            if all(s.state==State.SUCCEEDED for s in run.plan.steps):run.status=State.SUCCEEDED;break
            ready=[s for s in run.plan.steps if s.state in {State.PENDING,State.WAITING_APPROVAL} and all(by_id[d].state==State.SUCCEEDED for d in s.depends_on)]
            if not ready:run.status=State.BLOCKED;break
            before=[(s.id,s.state,s.attempts) for s in ready]
            outcomes=await self.scheduler.run(ready,lambda s:self._step(run,s))
            for step,outcome in zip(ready,outcomes):
                if isinstance(outcome,BaseException):
                    if step.outcome_unknown:step.state=State.BLOCKED   # fixed unknown state is never overwritten and no raw text is kept
                    elif step.approval_id is not None or step.risk.value in GATED_RISKS:
                        step.error=type(outcome).__name__;step.state=State.BLOCKED   # gated steps: class name only, never external error text
                    else:
                        step.error=f"{type(outcome).__name__}: {outcome}"
                        step.state=State.BLOCKED
                    run.traces.append(Trace("execution",f"Infrastructure blocked {step.title}",[],["fix infrastructure"],"escalate",["fail closed; no hidden scheduler exception"]))
            after=[(s.id,s.state,s.attempts) for s in ready]
            if before==after:break
        return run
    async def _gated_step(self,run:Run,step:Step):
        """EXTERNAL/IRREVERSIBLE (or once-filed) step: real Module 0 approval bound to tenant/run/step/digest, single use, fresh. Fixed error codes only."""
        st=self.approvals
        if not(_nonblank(run.tenant_id) and _nonblank(run.actor_id)) or not all(hasattr(st,n) for n in ("put","full_view","consume_effect")):return _block(step,"binding_unavailable")
        tool_name=step.tool or "step"
        if not step.approval_id:
            try:args=_plain_json(step.arguments)
            except ValueError:return _block(step,"arguments_invalid")
            digest=step_digest(run.id,step.id,step.tool,step.risk.value,args)
            req=st.put(ApprovalRequest(id=str(uuid.uuid4()),module_id=MODULE_ID,action_type=f"cognitive:{tool_name}",payload={"tenant_id":run.tenant_id,"run_id":run.id,"step_id":step.id,"title":step.title,"tool":step.tool,"arguments":args,"risk":step.risk.value,"step_digest":digest}),ttl_seconds=PENDING_REVIEW_TTL_SECONDS)
            step.approval_id=req.id;step.state=State.WAITING_APPROVAL;return
        try:view=st.full_view(step.approval_id)
        except (ApprovalNotFoundError,KeyError):return _block(step,"approval_unavailable")
        except SQLAlchemyError:return _block(step,"approval_store_unavailable")
        if not isinstance(view,dict):return _block(step,"approval_unavailable")
        status=str(getattr(view.get("status"),"value",view.get("status")))
        if status=="pending":step.state=State.WAITING_APPROVAL;return
        if status=="denied":return _block(step,"approval_denied")
        if status=="expired":return _block(step,"approval_expired")
        if status!="approved":return _block(step,"approval_unavailable")
        # one consistent snapshot of tool/risk/arguments, taken before consume and used for the dispatch itself (no relookup, no await in between)
        tool=self.tools.tools.get(step.tool) if step.tool else None
        risk=step.risk
        try:args=_plain_json(step.arguments)
        except ValueError:return _block(step,"arguments_invalid")
        digest=step_digest(run.id,step.id,step.tool,risk.value,args)
        payload=view.get("payload");by=view.get("approved_by")
        if (isinstance(view.get("module_id"),bool) or view.get("module_id")!=MODULE_ID or view.get("action_type")!=f"cognitive:{tool_name}" or view.get("user_id")!=run.tenant_id
                or not isinstance(payload,dict) or payload.get("run_id")!=run.id or payload.get("step_id")!=step.id or payload.get("step_digest")!=digest
                or not isinstance(view.get("decided_at"),datetime) or not _nonblank(by) or by.strip()==run.actor_id.strip()):return _block(step,"approval_mismatch")
        if step.tool is not None and (tool is None or tool.risk!=risk):   # cheap pre-dispatch refusals keep the approval unconsumed and are retried as before
            step.attempts+=1;step.error="ValueError";step.state=State.PENDING if step.attempts<step.max_attempts else State.FAILED;return
        snap_tool=step.tool;snap_handler=tool.handler if tool is not None else None;snap_timeout=tool.timeout if tool is not None else None   # handler/timeout/tool name frozen with the args, BEFORE consume
        effect_id=str(uuid.uuid4());stored=copy.deepcopy(payload)
        try:permit=st.consume_effect(step.approval_id,module_id=MODULE_ID,action_type=f"cognitive:{tool_name}",payload=stored,user_id=run.tenant_id,effect_id=effect_id,actor=run.actor_id,max_age_seconds=APPROVED_VALIDITY_SECONDS)
        except ApprovalConflictError as e:
            return _block(step,{"approval is stale":"approval_stale","approval has already been consumed":"approval_consumed","approval has expired":"approval_expired"}.get(str(e),"approval_refused"))
        except (ApprovalNotFoundError,ValueError):return _block(step,"approval_refused")
        except SQLAlchemyError:return _block(step,"approval_store_unavailable")   # nothing was consumed or dispatched
        if not isinstance(permit,dict) or permit.get("allowed") is not True or permit.get("approval_id")!=step.approval_id or permit.get("effect_id")!=effect_id:return _block(step,"approval_refused")
        step.attempts+=1;step.state=State.RUNNING;step.outcome_unknown=True;step.error="outcome_unknown"   # marked BEFORE the handler is entered; stays through timeout/cancel/scheduler errors
        key=f"{run.id}:{step.id}:{step.attempts}"
        try:
            result={"ok":True,"note":"cognitive step"} if snap_tool is None else await asyncio.wait_for(snap_handler(args,key),snap_timeout)
        except Exception:
            step.state=State.BLOCKED;run.traces.append(Trace("execution",f"Outcome unknown: {step.title}",[],["reconcile before any retry"],"escalate",["approval consumed","no retry"]));return
        step.result=result;step.state=State.SUCCEEDED;step.outcome_unknown=False;step.error=None
        run.traces.append(Trace("execution",f"Completed {step.title}",[step.result],[],"continue",["bound approval consumed once"]))
    async def _step(self,run:Run,step:Step):
        if step.approval_id is not None or step.risk.value in GATED_RISKS:   # a step once filed approval-required stays gated even if its risk is later mutated
            return await self._gated_step(run,step)
        step.state=State.RUNNING;step.attempts+=1
        try:
            step.result=await self.tools.dispatch(step,f"{run.id}:{step.id}:{step.attempts}");step.state=State.SUCCEEDED
            run.traces.append(Trace("execution",f"Completed {step.title}",[step.result],[],"continue",["tool registry","approval gate"]))
        except Exception as e:
            step.error=f"{type(e).__name__}: {e}";step.state=State.PENDING if step.attempts<step.max_attempts else State.FAILED
            run.traces.append(Trace("execution",f"Attempt failed: {step.title}",[],["retry","escalate"],"retry" if step.state==State.PENDING else "escalate",["bounded retries"]))

class Retrospective:
    async def review(self,run:Run,model:Model):
        result=await model("retrospective",{"goal":run.goal,"status":run.status,"traces":[t.summary for t in run.traces]})
        run.traces.append(Trace("retrospective",result.get("summary","reviewed"),result.get("evidence",[]),result.get("alternatives",[]),result.get("next","none"),["evidence based learning"]));return result

class AtlasSupervisor:
    def assess(self,runs:list[Run],max_failures:int=3):
        failures=sum(r.status in {State.FAILED,State.BLOCKED} for r in runs);over=[r.id for r in runs if any(r.spent.get(k,0)>r.budget.get(k,float('inf')) for k in r.spent)]
        return {"healthy":failures<max_failures and not over,"failed_runs":failures,"over_budget":over,"action":"pause_and_escalate" if failures>=max_failures or over else "continue"}

class Service:
    """Composes all 12 requested parts; traces expose evidence/decisions, not hidden scratchpad."""
    def __init__(self,approval_store:ApprovalStore,model:Model,max_parallel:int=6):
        self.sensory=SensoryIngestion({"api","webhook","file","email","calendar","browser","user"});self.working=WorkingMemory();self.ltm=LongTermMemory();self.skills=SkillLibrary();self.planner=HTNPlanner(self.skills,model);self.tools=ToolRegistry();self.scheduler=ConcurrencyScheduler(max_parallel);self.loop=DeliberativeLoop(approval_store,self.tools,self.scheduler);self.retrospective=Retrospective();self.supervisor=AtlasSupervisor();self.model=model;self.runs={}
    async def start(self,goal:str,constraints:dict[str,Any],budget:dict[str,float],*,tenant_id:str|None=None,actor_id:str|None=None):
        memories=self.ltm.recall(goal);plan=await self.planner.plan(goal,{**constraints,"memory":[m.content for m in memories]});run=Run(goal,budget,plan,tenant_id=tenant_id,actor_id=actor_id);run.traces.append(Trace("intake","Goal accepted",[{"memory_id":m.id} for m in memories],["clarify","plan"],"plan",["bounded budget","tenant context supplied by route"]));self.runs[run.id]=run;return await self.loop.execute(run)
