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
        try: doc=yaml.safe_load(raw)
        except yaml.YAMLError as error: raise WorkflowValidationError("workflow is not valid YAML") from error
        if doc is None: doc={}
        if type(doc) is not dict: raise WorkflowValidationError("workflow must be a mapping")
        items=doc.get("nodes",[])
        if type(items) is not list: raise WorkflowValidationError("nodes must be a list")
        nodes=[]; ids=set()
        for item in items:
            if type(item) is not dict: raise WorkflowValidationError("each node must be a mapping")
            nid=item.get("id"); task=item.get("task"); deps=item.get("depends_on",[]); config=item.get("config",{})
            if type(nid) is not str or not nid.strip() or type(task) is not str or not task.strip():
                raise WorkflowValidationError("each node needs nonblank text id and task")
            if type(deps) is not list or any(type(d) is not str for d in deps):
                raise WorkflowValidationError(f"{nid} depends_on must be a list of node ids")
            if type(config) is not dict: raise WorkflowValidationError(f"{nid} config must be a mapping")
            if nid in ids: raise WorkflowValidationError(f"duplicate node: {nid}")
            ids.add(nid); nodes.append(Node(nid,task,tuple(deps),config))
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
            ready=[n for n in wf.nodes if n.id in pending and set(n.depends_on)<=results.keys()]
            if not ready: raise RuntimeError("DAG made no progress")
            output=await asyncio.gather(*(execute(n) for n in ready),return_exceptions=True)
            failures=[]
            for n,value in zip(ready,output):
                if isinstance(value,BaseException):
                    if not isinstance(value,(Exception,asyncio.CancelledError)): raise value
                    failures.append((n,value)); continue
                results[n.id]=value; pending.remove(n.id)
            if failures:
                def unknown(exc):
                    seen=set()
                    while exc is not None and id(exc) not in seen:
                        seen.add(id(exc))
                        if getattr(exc,"outcome",None)=="unknown": return True
                        exc=exc.__cause__
                    return False
                from .wiring import WorkflowReviewRequired
                n,value=next((f for f in failures if unknown(f[1])),None) or next((f for f in failures if isinstance(f[1],WorkflowReviewRequired)),None) or failures[0]
                if isinstance(value,WorkflowReviewRequired): error=value
                else:
                    error=RuntimeError(f"node {n.id} failed"); error.__cause__=value
                error.partial_results=dict(results)
                error.failed_node=n.id
                error.failed_nodes=[f[0].id for f in failures]
                raise error
        return results
