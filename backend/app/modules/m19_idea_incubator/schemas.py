from enum import Enum
from pydantic import BaseModel,Field,HttpUrl
class Stage(str,Enum): INTAKE="intake";LANDSCAPE="landscape";VALIDATION="validation";WIREFRAME="wireframe";SCAFFOLD="scaffold";TEST="test";VIABILITY="viability";PREVIEW="preview"
class IntakeIn(BaseModel): one_liner:str=Field(min_length=3,max_length=1000); transcript:str|None=None; budget_cap:float=Field(default=25,ge=0); target_user:str|None=None; constraints:list[str]=[]
class LeanCanvasOut(BaseModel): problem:list[str];customer_segments:list[str];unique_value_proposition:str;solution:list[str];channels:list[str];revenue_streams:list[str];cost_structure:list[str];key_metrics:list[str];unfair_advantage:str|None=None;riskiest_assumptions:list[str]
class GateOut(BaseModel): stage:Stage;proceed:bool;reasons:list[str];missing_evidence:list[str];expected_cost:float=Field(ge=0);requires_approval:bool=False
class RunOut(BaseModel): id:str;state:str;stage:Stage;canvas:LeanCanvasOut;gates:list[GateOut];spent:float=0;budget_cap:float
class PreviewIn(BaseModel): artifacts:list[str];estimated_cost:float=Field(ge=0)
class PackageIn(BaseModel): run_id:str; evidence:list[dict]=[]; artifacts:list[str]=[]
class PackageOut(BaseModel): executive_summary:str;recommendation:str;recommendation_confidence:float=Field(ge=0,le=1);market_claims:list[dict];technical_feasibility:list[str];prototype_artifacts:list[str];prototype_preview:HttpUrl|None=None;unresolved_risks:list[str];next_experiments:list[str]
