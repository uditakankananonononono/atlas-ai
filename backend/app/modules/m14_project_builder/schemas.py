"""Typed contracts for Module 14's bounded multi-agent project builder."""
from datetime import datetime
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

# --- Scoped project generation ----------------------------------------------
class ScopeConstraintsView(BaseModel):
    deadline:datetime|None=None; max_effort_hours:float|None=Field(default=None,gt=0)
    max_budget_usd:float|None=Field(default=None,ge=0); hours_per_day:float=Field(default=8.0,gt=0)
    deliverable_requirements:list[str]=Field(default_factory=list,max_length=100)
    excluded_activities:list[str]=Field(default_factory=list,max_length=100)
class ScopeRequest(BaseModel):
    constraints:ScopeConstraintsView=Field(default_factory=ScopeConstraintsView)
    kind:str|None=None; brief_keywords:list[str]=Field(default_factory=list,max_length=100)
class ScopeView(BaseModel):
    project_id:str; kind:str; kind_confidence:float=Field(ge=0,le=1); feasible:bool
    issues:list[str]=[]; estimated_effort_hours:float=0; estimated_finish:datetime|None=None
    in_scope:list[str]=[]; out_of_scope:list[str]=[]; assumptions:list[str]=[]; risks:list[str]=[]
    markdown:str=""

# --- Milestones ---------------------------------------------------------------
MilestoneStatusLiteral=Literal["pending","in_progress","blocked","completed","failed","skipped"]
class MilestoneView(BaseModel):
    milestone_id:str; project_id:str; title:str; phase:str
    depends_on:list[str]=[]; estimated_effort_hours:float=Field(ge=0)
    deliverables:list[str]=[]; acceptance_criteria:list[str]=[]
    status:MilestoneStatusLiteral="pending"; progress:float=Field(default=0,ge=0,le=1)
    planned_start:datetime|None=None; planned_end:datetime|None=None
    actual_start:datetime|None=None; actual_end:datetime|None=None
class MilestonePlanRequest(BaseModel):
    kind:str=Field(min_length=1); start:datetime; hours_per_day:float=Field(default=8.0,gt=0)
class MilestoneProgressView(BaseModel):
    overall_progress:float=Field(ge=0,le=1); total_effort_hours:float
    completed_effort_hours:float; per_phase:dict[str,float]; counts_by_status:dict[str,int]
class MilestoneAdvanceRequest(BaseModel):
    status:MilestoneStatusLiteral; at:datetime|None=None; progress:float|None=Field(default=None,ge=0,le=1)
    evidence:dict[str,str]|None=None
class SlippageView(BaseModel):
    milestone_id:str; kind:str; detail:str; overdue_by_seconds:float|None=None; progress_gap:float|None=None

# --- Artifacts ----------------------------------------------------------------
class ArtifactRegisterRequest(BaseModel):
    task_id:str=Field(min_length=1,max_length=120); kind:str=Field(min_length=1,max_length=60)
    uri:str=Field(min_length=1,max_length=1000); content_base64:str=Field(min_length=0)
    provenance:dict[str,Any]=Field(default_factory=dict)
class ArtifactValidationView(BaseModel):
    artifact_id:str; passed:bool; score:float=Field(ge=0,le=1)
    findings:list[dict[str,str]]=[]; remediation:list[str]=[]
class ArtifactSetValidationView(BaseModel):
    project_id:str; passed:bool; score:float=Field(ge=0,le=1)
    artifacts:list[ArtifactValidationView]=[]; findings:list[dict[str,str]]=[]

# --- Feedback and exports -----------------------------------------------------
class FeedbackRequest(BaseModel):
    feedback:str=Field(min_length=3,max_length=10000); provider:str=Field(default="openai",min_length=1)
class FeedbackResponse(BaseModel):
    project:ProjectView; revision_applied:bool; requires_human_review:bool=True
class ExportView(BaseModel):
    project_id:str; readme:str; manifest:dict[str,Any]; verification:dict[str,Any]
    zip_sha256:str|None=None
