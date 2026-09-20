"""Typed contracts for Module 14's bounded multi-agent project builder."""
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

AgentKind=Literal["literature","data","coder","analyst","writer"]
class Budget(BaseModel):
    max_iterations:int=Field(default=3,ge=1,le=20); max_agent_calls:int=Field(default=50,ge=1,le=1000)
    max_runtime_seconds:int=Field(default=3600,ge=1,le=86400); max_cost_usd:float=Field(default=25,ge=0)
class ProjectTask(BaseModel):
    id:str=Field(min_length=1,max_length=120); title:str=Field(min_length=2,max_length=500)
    objective:str=Field(min_length=3,max_length=5000); agent_kind:AgentKind
    dependencies:list[str]=Field(default_factory=list,max_length=100); acceptance_criteria:list[str]=Field(default_factory=list,max_length=50)
    status:Literal["blocked","ready","running","review","completed","failed"]="blocked"; attempt:int=0
class ProjectPlan(BaseModel):
    goal:str; tasks:list[ProjectTask]=Field(min_length=1,max_length=500); assumptions:list[str]=Field(default_factory=list)
    risks:list[str]=Field(default_factory=list); quality_gates:list[str]=Field(default_factory=list)
    @model_validator(mode="after")
    def valid_dag(self):
        ids={t.id for t in self.tasks}
        if len(ids)!=len(self.tasks): raise ValueError("task ids must be unique")
        edges={t.id:t.dependencies for t in self.tasks}
        if any(set(ds)-ids for ds in edges.values()): raise ValueError("dependency references an unknown task")
        visiting=set(); visited=set()
        def visit(node):
            if node in visiting: raise ValueError("plan contains a dependency cycle")
            if node in visited:return
            visiting.add(node)
            for dep in edges[node]:visit(dep)
            visiting.remove(node);visited.add(node)
        for node in ids:visit(node)
        return self
class CreateProjectRequest(BaseModel):
    goal:str=Field(min_length=3,max_length=5000); brief:dict[str,Any]=Field(default_factory=dict); budget:Budget=Field(default_factory=Budget)
class ProjectView(BaseModel):
    id:str; tenant_id:str; goal:str; brief:dict[str,Any]; budget:Budget; status:str; revision:int=0; plan:ProjectPlan|None=None
class PlanResponse(BaseModel): project:ProjectView; requires_human_review:bool=True
class ExecutionProposal(BaseModel): approval_id:str; project_id:str; status:str; action_type:Literal["execute_project_plan"]="execute_project_plan"
class ArtifactManifest(BaseModel):
    id:str; project_id:str; task_id:str; kind:str; uri:str; sha256:str; provenance:dict[str,Any]=Field(default_factory=dict)
class QualityResult(BaseModel): passed:bool; score:float=Field(ge=0,le=1); findings:list[str]=[]; remediation:list[str]=[]
