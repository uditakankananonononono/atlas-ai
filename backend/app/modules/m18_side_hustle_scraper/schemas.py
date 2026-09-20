from pydantic import BaseModel,Field,HttpUrl
class DiscoverIn(BaseModel):
 query:str=Field(min_length=3,max_length=500); platforms:list[str]=["reddit","youtube","pinterest","public_web"]; limit_per_platform:int=Field(default=20,ge=1,le=100)
class BlueprintOut(BaseModel):
 title:str; steps:list[str]; tools:list[str]; complexity:int=Field(ge=1,le=5); time_to_first_dollar_days:int|None=None; automation_level:int=Field(ge=0,le=100); monetisation:list[str]; source_urls:list[HttpUrl]; scam_signals:list[str]=[]; assumptions:list[str]=[]
class UserContext(BaseModel):
 skills:list[str]=[]; budget:float=Field(default=0,ge=0); hours_per_week:float=Field(default=5,gt=0,le=168); country:str|None=None; excluded_categories:list[str]=[]
class AnalyzeIn(BaseModel): blueprint:BlueprintOut; user:UserContext
class SensitivityOut(BaseModel): name:str; inputs:dict[str,float]; viability_score:float=Field(ge=0,le=100)
class FeasibilityOut(BaseModel):
 strengths:list[str]; weaknesses:list[str]; opportunities:list[str]; threats:list[str]; market_saturation:float=Field(ge=0,le=1); barrier_to_entry:float=Field(ge=0,le=1); evidence_quality:float=Field(ge=0,le=1); viability_score:float=Field(ge=0,le=100); score_explanation:list[str]; sensitivities:list[SensitivityOut]; first_experiment:str; max_test_budget:float=Field(ge=0); recommendation:str
