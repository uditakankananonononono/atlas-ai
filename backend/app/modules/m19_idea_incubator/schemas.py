from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel,Field,HttpUrl,field_validator

# Existing autonomous-incubation contract.
class Stage(str,Enum): INTAKE="intake";LANDSCAPE="landscape";VALIDATION="validation";WIREFRAME="wireframe";SCAFFOLD="scaffold";TEST="test";VIABILITY="viability";PREVIEW="preview"
class IntakeIn(BaseModel):
    one_liner:str=Field(min_length=3,max_length=1000);transcript:str|None=None;budget_cap:float=Field(default=25,ge=0);target_user:str|None=None;constraints:list[str]=Field(default_factory=list)
class LeanCanvasOut(BaseModel):
    problem:list[str];customer_segments:list[str];unique_value_proposition:str;solution:list[str];channels:list[str];revenue_streams:list[str];cost_structure:list[str];key_metrics:list[str];unfair_advantage:str|None=None;riskiest_assumptions:list[str]
class GateOut(BaseModel):
    stage:Stage;proceed:bool;reasons:list[str];missing_evidence:list[str];expected_cost:float=Field(ge=0);requires_approval:bool=False
class RunOut(BaseModel): id:str;state:str;stage:Stage;canvas:LeanCanvasOut;gates:list[GateOut];spent:float=0;budget_cap:float
class PreviewIn(BaseModel): artifacts:list[str];estimated_cost:float=Field(ge=0)
class PackageIn(BaseModel): run_id:str;evidence:list[dict]=Field(default_factory=list);artifacts:list[str]=Field(default_factory=list)
class PackageOut(BaseModel): executive_summary:str;recommendation:str;recommendation_confidence:float=Field(ge=0,le=1);market_claims:list[dict];technical_feasibility:list[str];prototype_artifacts:list[str];prototype_preview:HttpUrl|None=None;unresolved_risks:list[str];next_experiments:list[str]

# Durable evidence, feasibility, experiment and decision ledger.
class IdeaStage(str,Enum): CAPTURED="captured";DISCOVERY="discovery";VALIDATION="validation";EXPERIMENTING="experimenting";APPROVED="approved";PARKED="parked";REJECTED="rejected"
class EvidenceKind(str,Enum): INTERVIEW="interview";MARKET_DATA="market_data";COMPETITOR="competitor";TECHNICAL="technical";REGULATORY="regulatory";EXPERIMENT="experiment";OTHER="other"
class EvidencePolarity(str,Enum): SUPPORTS="supports";CONTRADICTS="contradicts";NEUTRAL="neutral"
class ExperimentStatus(str,Enum): PLANNED="planned";RUNNING="running";SUCCEEDED="succeeded";FAILED="failed";INCONCLUSIVE="inconclusive";CANCELLED="cancelled"
class FeasibilityOutcome(str,Enum): PASS="pass";CONDITIONAL="conditional";FAIL="fail"
class IdeaCreate(BaseModel):
    title:str=Field(min_length=1,max_length=180);problem:str=Field(min_length=1,max_length=5000);proposed_solution:str=Field(min_length=1,max_length=5000);tags:list[str]=Field(default_factory=list);metadata:dict[str,Any]=Field(default_factory=dict)
    @field_validator("title","problem","proposed_solution")
    @classmethod
    def not_blank(cls,value):
        if not value.strip():raise ValueError("must not be blank")
        return value.strip()
class Idea(IdeaCreate): id:str;stage:IdeaStage=IdeaStage.CAPTURED;version:int=1;created_at:datetime;updated_at:datetime
class EvidenceCreate(BaseModel):
    kind:EvidenceKind;claim:str=Field(min_length=1,max_length=5000);source:str=Field(min_length=1,max_length=2000);polarity:EvidencePolarity;strength:float=Field(ge=0,le=1);confidence:float=Field(ge=0,le=1);observed_at:datetime;metadata:dict[str,Any]=Field(default_factory=dict)
class Evidence(EvidenceCreate): id:str;idea_id:str;created_at:datetime
class DimensionScore(BaseModel): score:float=Field(ge=0,le=100);confidence:float=Field(ge=0,le=1);notes:str=Field(default="",max_length=3000)
class FeasibilityTestCreate(BaseModel):
    desirability:DimensionScore;technical:DimensionScore;viability:DimensionScore;strategic_fit:DimensionScore;compliance:DimensionScore;weights:dict[str,float]|None=None;blockers:list[str]=Field(default_factory=list);assumptions:list[str]=Field(default_factory=list)
class FeasibilityTest(FeasibilityTestCreate): id:str;idea_id:str;weighted_score:float;weighted_confidence:float;outcome:FeasibilityOutcome;tested_at:datetime
class ExperimentCreate(BaseModel): name:str=Field(min_length=1,max_length=180);hypothesis:str=Field(min_length=1,max_length=3000);method:str=Field(min_length=1,max_length=5000);metric:str=Field(min_length=1,max_length=500);target:float;unit:str=Field(default="",max_length=80);deadline:datetime|None=None
class ExperimentUpdate(BaseModel): status:ExperimentStatus;observed_value:float|None=None;learnings:str=Field(default="",max_length=5000)
class Experiment(ExperimentCreate): id:str;idea_id:str;status:ExperimentStatus=ExperimentStatus.PLANNED;observed_value:float|None=None;learnings:str="";created_at:datetime;updated_at:datetime
class DecisionCreate(BaseModel): to_stage:IdeaStage;rationale:str=Field(min_length=1,max_length=5000);expected_version:int|None=Field(default=None,ge=1);metadata:dict[str,Any]=Field(default_factory=dict)
class Decision(BaseModel): id:str;idea_id:str;from_stage:IdeaStage;to_stage:IdeaStage;rationale:str;actor_id:str;metadata:dict[str,Any]=Field(default_factory=dict);decided_at:datetime;idea_version:int
class EvidenceSummary(BaseModel): supporting_count:int;contradicting_count:int;neutral_count:int;support_score:float;contradiction_score:float;net_score:float;confidence:float
class IdeaDossier(BaseModel): idea:Idea;evidence:list[Evidence];evidence_summary:EvidenceSummary;feasibility_tests:list[FeasibilityTest];experiments:list[Experiment];decisions:list[Decision]
