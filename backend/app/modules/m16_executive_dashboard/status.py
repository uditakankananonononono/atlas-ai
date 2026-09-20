"""Cross-module status aggregation.

Module identity comes from the shared module catalog/registry through an
injectable provider (lazy imports, so this module never creates import
cycles); runtime state comes from agent heartbeats, pending approvals and
attributed events stored by this module. Attribution is honest: an event
counts toward a module only when it carries module_id in its payload or a
module:<id> aggregate type.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from typing import Protocol
from .schemas import AgentState,AgentStatus,Approval,Event,ModuleStatus
STALE_AFTER=timedelta(minutes=15)
OFFLINE_AFTER=timedelta(hours=1)
@dataclass(frozen=True)
class ModuleInfo:
    id:int;slug:str;name:str;implemented:bool
class ModuleCatalog(Protocol):
    def list_modules(self)->list[ModuleInfo]:...
class RepoCatalog:
    """Default adapter over app.modules.catalog + app.modules.registry."""
    def list_modules(self)->list[ModuleInfo]:
        try:from app.modules.catalog import MODULES
        except Exception:return []
        try:
            from app.modules.registry import BY_IMPLEMENTED_ID
            implemented_ids=set(BY_IMPLEMENTED_ID)
        except Exception:implemented_ids=set()
        out=[]
        for m in MODULES:
            implemented=getattr(m,"status",None)=="implemented" or m.id in implemented_ids
            out.append(ModuleInfo(m.id,m.slug,m.name,implemented))
        return out
def event_module_id(e:Event)->int|None:
    v=e.payload.get("module_id")
    if isinstance(v,int) and not isinstance(v,bool):return v
    if e.aggregate_type.startswith("module:"):
        try:return int(e.aggregate_type.split(":",1)[1])
        except ValueError:return None
    return None
def effective_state(a:AgentStatus,now:datetime,stale_after:timedelta=STALE_AFTER,offline_after:timedelta=OFFLINE_AFTER)->AgentState:
    age=now-a.last_heartbeat
    if age>=offline_after:return AgentState.OFFLINE
    if age>=stale_after and a.state==AgentState.RUNNING:return AgentState.STALLED
    return a.state
def module_statuses(catalog:ModuleCatalog,agents:list[AgentStatus],pending_approvals:list[Approval],events_24h:list[Event],now:datetime)->list[ModuleStatus]:
    agents_by_module={a.module_id:a for a in agents}
    pending_by_module:dict[int,int]={}
    for a in pending_approvals:pending_by_module[a.module_id]=pending_by_module.get(a.module_id,0)+1
    events_by_module:dict[int,int]={}
    for e in events_24h:
        mid=event_module_id(e)
        if mid is not None:events_by_module[mid]=events_by_module.get(mid,0)+1
    out=[]
    for m in catalog.list_modules():
        agent=agents_by_module.get(m.id)
        if agent is not None:
            agent=agent.model_copy(update={"state":effective_state(agent,now)})
        out.append(ModuleStatus(module_id=m.id,slug=m.slug,name=m.name,implemented=m.implemented,agent=agent,pending_approvals=pending_by_module.get(m.id,0),events_24h=events_by_module.get(m.id,0)))
    return out
