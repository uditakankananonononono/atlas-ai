from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
import yaml

class WorkflowValidationError(ValueError): pass
NodeRunner=Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]

@dataclass(frozen=True)
class Node:
    id: str; task: str; depends_on: tuple[str,...]; config: dict[str,Any]

@dataclass(frozen=True)
class Workflow:
    name: str; nodes: tuple[Node,...]
    @classmethod
    def from_yaml(cls, raw: str) -> "Workflow":
        doc=yaml.safe_load(raw) or {}; nodes=[]; ids=set()
        for item in doc.get("nodes",[]):
            nid=item["id"]
            if nid in ids: raise WorkflowValidationError(f"duplicate node: {nid}")
            ids.add(nid); nodes.append(Node(nid,item["task"],tuple(item.get("depends_on",[])),item.get("config",{})))
        for n in nodes:
            missing=set(n.depends_on)-ids
            if missing: raise WorkflowValidationError(f"{n.id} has missing dependencies: {sorted(missing)}")
        cls._assert_acyclic(nodes)
        return cls(doc.get("name","workflow"),tuple(nodes))
    @staticmethod
    def _assert_acyclic(nodes: list[Node]):
        deps={n.id:set(n.depends_on) for n in nodes}; ready=[k for k,v in deps.items() if not v]; seen=0
        while ready:
            current=ready.pop(); seen+=1
            for k,v in deps.items():
                v.discard(current)
                if not v and k not in ready and k!=current: ready.append(k)
            deps.pop(current,None)
        if seen != len(nodes): raise WorkflowValidationError("workflow contains a cycle")

class DagEngine:
    """Runs independent nodes concurrently and passes only declared parent outputs."""
    def __init__(self, runner: NodeRunner, max_concurrency: int=8): self.runner=runner; self.limit=asyncio.Semaphore(max_concurrency)
    async def run(self, wf: Workflow, inputs: dict[str,Any]) -> dict[str,dict[str,Any]]:
        nodes={n.id:n for n in wf.nodes}; results={}; pending=set(nodes)
        async def execute(n: Node):
            context={"workflow_inputs":inputs,"parents":{d:results[d] for d in n.depends_on}}
            async with self.limit: return await self.runner(n.task,n.config,context)
        while pending:
            ready=[nodes[i] for i in pending if set(nodes[i].depends_on)<=results.keys()]
            if not ready: raise RuntimeError("DAG made no progress")
            output=await asyncio.gather(*(execute(n) for n in ready),return_exceptions=True)
            for n,value in zip(ready,output):
                if isinstance(value,Exception): raise RuntimeError(f"node {n.id} failed") from value
                results[n.id]=value; pending.remove(n.id)
        return results
