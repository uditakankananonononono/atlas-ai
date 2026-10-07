from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
import yaml

class WorkflowValidationError(ValueError): pass
class _WorkflowLoader(yaml.SafeLoader):pass

def _unique_mapping(loader,node,deep=False):
    result={}
    for key_node,value_node in node.value:
        key=loader.construct_object(key_node,deep=deep)
        try:
            if key in result:raise WorkflowValidationError("duplicate YAML mapping key")
            result[key]=loader.construct_object(value_node,deep=deep)
        except TypeError as exc:raise WorkflowValidationError("invalid YAML mapping key") from exc
    return result
_WorkflowLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,_unique_mapping)
class WorkflowNodeFailure(RuntimeError):
    def __init__(self,node_id:str,error:BaseException,completed:dict[str,Any],failures:list[tuple[str,BaseException]]):
        super().__init__(f"node {node_id} failed")
        self.node_id=node_id;self.error=error;self.completed=dict(completed);self.failures=failures

NodeRunner=Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]

@dataclass(frozen=True)
class Node:
    id: str; task: str; depends_on: tuple[str,...]; config: dict[str,Any]

@dataclass(frozen=True)
class Workflow:
    name: str; nodes: tuple[Node,...]
    @classmethod
    def from_yaml(cls, raw: str) -> "Workflow":
        try:doc=yaml.load(raw,Loader=_WorkflowLoader)
        except (yaml.YAMLError,RecursionError) as exc:raise WorkflowValidationError("invalid or excessively nested workflow YAML") from exc
        if not isinstance(doc,dict):raise WorkflowValidationError("workflow must be a mapping")
        items=doc.get("nodes")
        if not isinstance(items,list) or not items:raise WorkflowValidationError("workflow nodes must be a nonempty list")
        if len(items)>1000:raise WorkflowValidationError("workflow has too many nodes")
        name=doc.get("name","workflow")
        if not isinstance(name,str) or not name.strip():raise WorkflowValidationError("workflow name must be nonempty text")
        nodes=[];ids=set()
        for item in items:
            if not isinstance(item,dict):raise WorkflowValidationError("workflow node must be a mapping")
            nid=item.get("id");task=item.get("task")
            if not isinstance(nid,str) or not nid.strip():raise WorkflowValidationError("node id must be nonempty text")
            if not isinstance(task,str) or not task.strip():raise WorkflowValidationError("node task must be nonempty text")
            if nid in ids:raise WorkflowValidationError(f"duplicate node: {nid}")
            parents=item.get("depends_on",[]);config=item.get("config",{})
            if not isinstance(parents,list) or any(not isinstance(x,str) or not x.strip() for x in parents):raise WorkflowValidationError("depends_on must be a list of node ids")
            if len(set(parents))!=len(parents):raise WorkflowValidationError("duplicate dependency")
            if not isinstance(config,dict):raise WorkflowValidationError("node config must be a mapping")
            ids.add(nid);nodes.append(Node(nid,task,tuple(parents),config))
        for n in nodes:
            missing=set(n.depends_on)-ids
            if missing:raise WorkflowValidationError(f"{n.id} has missing dependencies: {sorted(missing)}")
        cls._assert_acyclic(nodes)
        return cls(name,tuple(nodes))
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
            ready=[nodes[i] for i in sorted(pending) if set(nodes[i].depends_on)<=results.keys()]
            if not ready: raise RuntimeError("DAG made no progress")
            output=await asyncio.gather(*(execute(n) for n in ready),return_exceptions=True)
            # A gather wave can complete siblings before another node fails.
            # Retain their outputs, never label them cancelled or replay them.
            failures=[]
            for n,value in zip(ready,output):
                if isinstance(value,BaseException):failures.append((n.id,value))
                else:results[n.id]=value;pending.remove(n.id)
            if failures:
                node_id,error=failures[0]
                raise WorkflowNodeFailure(node_id,error,results,failures) from error
        return results
