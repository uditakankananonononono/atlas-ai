"""Module 20: evidence-oriented cognitive worker with bounded autonomy."""
from __future__ import annotations

import asyncio, re, uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol

from app.core.models import ApprovalRequest, ApprovalStatus

MODULE_ID=20
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
    title:str; tool:str|None; arguments:dict[str,Any]; depends_on:set[str]=field(default_factory=set); risk:Risk=Risk.READ; max_attempts:int=3; id:str=field(default_factory=lambda:str(uuid.uuid4())); state:State=State.PENDING; attempts:int=0; approval_id:str|None=None; result:dict[str,Any]|None=None; error:str|None=None
@dataclass
class Plan:
    goal:str; steps:list[Step]; constraints:dict[str,Any]; id:str=field(default_factory=lambda:str(uuid.uuid4()))
@dataclass
class Trace:
    phase:str; summary:str; evidence:list[dict[str,Any]]; alternatives:list[str]; decision:str; policy_basis:list[str]; at:datetime=field(default_factory=now)
@dataclass
class Run:
    goal:str; budget:dict[str,float]; plan:Plan; id:str=field(default_factory=lambda:str(uuid.uuid4())); status:State=State.PENDING; traces:list[Trace]=field(default_factory=list); spent:dict[str,float]=field(default_factory=lambda:{"seconds":0,"tokens":0,"money":0})

class ApprovalStore(Protocol):
    def put(self,item:ApprovalRequest)->ApprovalRequest: ...
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
            await self.scheduler.run(ready,lambda s:self._step(run,s))
            after=[(s.id,s.state,s.attempts) for s in ready]
            if before==after:break
        return run
    async def _step(self,run:Run,step:Step):
        if step.risk in {Risk.EXTERNAL,Risk.IRREVERSIBLE}:
            if not step.approval_id:
                req=self.approvals.put(ApprovalRequest(id=str(uuid.uuid4()),module_id=MODULE_ID,action_type=f"cognitive:{step.tool or 'step'}",payload={"run_id":run.id,"step_id":step.id,"title":step.title,"arguments":step.arguments,"risk":step.risk.value}))
                step.approval_id=req.id;step.state=State.WAITING_APPROVAL;return
            req=next((x for x in self.approvals.list() if x.id==step.approval_id),None)
            if not req or req.status==ApprovalStatus.PENDING:return
            if req.status!=ApprovalStatus.APPROVED:step.state=State.BLOCKED;return
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
    async def start(self,goal:str,constraints:dict[str,Any],budget:dict[str,float]):
        memories=self.ltm.recall(goal);plan=await self.planner.plan(goal,{**constraints,"memory":[m.content for m in memories]});run=Run(goal,budget,plan);run.traces.append(Trace("intake","Goal accepted",[{"memory_id":m.id} for m in memories],["clarify","plan"],"plan",["bounded budget","tenant context supplied by route"]));self.runs[run.id]=run;return await self.loop.execute(run)
