"""Cross-module runtime: one tenant context, shared approvals, typed handoffs."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Awaitable,Callable
from pydantic import BaseModel,Field

@dataclass(frozen=True)
class RuntimeContext:
    tenant_id:str;actor_id:str;correlation_id:str

class Handoff(BaseModel):
    source_module:int;target_module:int;operation:str;payload:dict[str,Any]
    evidence:list[dict[str,Any]]=Field(default_factory=list)
    requires_approval:bool=False

Handler=Callable[[RuntimeContext,Handoff],Awaitable[dict[str,Any]]]
class AtlasRuntime:
    def __init__(self):self.handlers={};self.trace=[]
    def register(self,module_id:int,operation:str,handler:Handler):
        key=(module_id,operation)
        if key in self.handlers:raise ValueError(f"duplicate runtime handler: {key}")
        self.handlers[key]=handler
    async def dispatch(self,context:RuntimeContext,handoff:Handoff):
        if not context.tenant_id or not context.actor_id:raise PermissionError("tenant and actor are required")
        handler=self.handlers.get((handoff.target_module,handoff.operation))
        if not handler:raise LookupError(f"no integrated handler for module {handoff.target_module}:{handoff.operation}")
        event={"correlation_id":context.correlation_id,"tenant_id":context.tenant_id,"source_module":handoff.source_module,"target_module":handoff.target_module,"operation":handoff.operation,"evidence":handoff.evidence}
        self.trace.append({**event,"state":"started"})
        try:result=await handler(context,handoff)
        except Exception as exc:
            self.trace.append({**event,"state":"failed","error":type(exc).__name__});raise
        self.trace.append({**event,"state":"completed","result_keys":sorted(result)})
        return result
    def topology(self):return [{"module_id":m,"operation":o} for m,o in sorted(self.handlers)]
