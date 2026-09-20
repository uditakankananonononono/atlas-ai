"""Goal decomposition, specialist orchestration, quality loops and Git versioning."""
from __future__ import annotations
import json
from hashlib import sha256
from pathlib import Path
from typing import Awaitable,Callable,Protocol
from uuid import uuid4
from app.core.models import ApprovalRequest
from app.core.providers import generate as byok_generate
from .schemas import *
GenerateFn=Callable[[str,str,str|None],Awaitable[tuple[str,str]]]
class ApprovalSink(Protocol):
    def put(self,item:ApprovalRequest)->ApprovalRequest:...
class Service:
    def __init__(self,approval_sink:ApprovalSink,generate_fn:GenerateFn=byok_generate,repository=None):self._approvals=approval_sink;self._generate=generate_fn;self._repository=repository;self._projects:dict[tuple[str,str],ProjectView]={}
    def create(self,tenant_id:str,request:CreateProjectRequest)->ProjectView:
        item=ProjectView(id=str(uuid4()),tenant_id=tenant_id,goal=request.goal,brief=request.brief,budget=request.budget,status="draft")
        
        if self._repository: return self._repository.save(item)
        self._projects[(tenant_id,item.id)]=item;return item
    def get(self,tenant_id:str,project_id:str)->ProjectView:
        
        if self._repository:
            item=self._repository.get(project_id)
            if item:return item
            raise KeyError("project not found")
        try:return self._projects[(tenant_id,project_id)]
        except KeyError as exc:raise KeyError("project not found") from exc
    async def plan(self,project:ProjectView,provider:str="openai")->PlanResponse:
        prompt=("Return JSON only with tasks, assumptions, risks, quality_gates. Decompose the goal into a dependency DAG. "
                "Every task uses exactly one specialist: literature, data, coder, analyst, writer. Include measurable acceptance criteria. "
                f"Goal: {project.goal}\nBrief: {json.dumps(project.brief,sort_keys=True)}")
        _,text=await self._generate(prompt,provider,None)
        try:raw=json.loads(text)
        except json.JSONDecodeError as exc:raise ValueError("planner returned invalid JSON") from exc
        plan=ProjectPlan(goal=project.goal,**raw)
        roots={t.id for t in plan.tasks if not t.dependencies}
        for task in plan.tasks:task.status="ready" if task.id in roots else "blocked"
        project.plan=plan;project.status="planned";old=project.revision;project.revision+=1
        if self._repository: project=self._repository.save(project,expected_revision=old)
        return PlanResponse(project=project)
    def propose_execution(self,project:ProjectView)->ExecutionProposal:
        if project.status!="planned" or not project.plan:raise ValueError("project must be planned first")
        stored=self._approvals.put(ApprovalRequest(id=str(uuid4()),module_id=14,action_type="execute_project_plan",payload={"project_id":project.id,"tenant_id":project.tenant_id,"budget":project.budget.model_dump(),"task_count":len(project.plan.tasks)}))
        project.status="awaiting_approval";old=project.revision;project.revision+=1
        if self._repository:self._repository.save(project,expected_revision=old)
        return ExecutionProposal(approval_id=stored.id,project_id=project.id,status=stored.status.value)
    @staticmethod
    def ready_tasks(plan:ProjectPlan)->list[ProjectTask]:
        complete={t.id for t in plan.tasks if t.status=="completed"}
        return [t for t in plan.tasks if t.status in {"blocked","ready"} and set(t.dependencies)<=complete]
    @staticmethod
    def artifact(project_id:str,task_id:str,kind:str,uri:str,payload:bytes,provenance:dict)->ArtifactManifest:
        return ArtifactManifest(id=str(uuid4()),project_id=project_id,task_id=task_id,kind=kind,uri=uri,sha256=sha256(payload).hexdigest(),provenance=provenance)
    @staticmethod
    def commit(working_tree:Path,message:str,relative_paths:list[str])->str:
        root=working_tree.resolve();paths=[]
        for item in relative_paths:
            path=(root/item).resolve()
            if root not in path.parents:raise ValueError("versioned path escapes project workspace")
            paths.append(item)
        try:
            from git import Actor,Repo
        except ImportError as exc:raise RuntimeError("GitPython is required for repository versioning") from exc
        repo=Repo(root);repo.index.add(paths);actor=Actor("Atlas Project Builder","atlas@localhost")
        return repo.index.commit(message,author=actor,committer=actor).hexsha
