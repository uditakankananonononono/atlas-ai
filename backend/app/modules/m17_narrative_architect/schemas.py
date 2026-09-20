from pydantic import BaseModel,ConfigDict,Field,HttpUrl
class CollectIn(BaseModel):
    query:str=Field(min_length=3,max_length=500); platforms:list[str]=["reddit","youtube","pinterest","public_web"]; limit_per_platform:int=Field(default=20,ge=1,le=100)
class SourceOut(BaseModel):
    url:HttpUrl; platform:str; content_hash:str; rights:str="link_and_excerpt_only"; injection_flags:list[str]=[]
class AdviceOut(BaseModel):
    source:SourceOut; excerpt:str; topic:str; actionable_tips:list[str]; confidence:float=Field(ge=0,le=1)
class IdentityIn(BaseModel):
    traits:list[str]; pivotal_experiences:list[str]; values:list[str]; voice_samples:list[str]=[]; forbidden_topics:list[str]=[]
class ConceptIn(BaseModel):
    prompt:str=Field(min_length=3,max_length=4000); profile:IdentityIn; count:int=Field(default=7,ge=5,le=10)
class ConceptOut(BaseModel):
    title:str; core_tension:str; metaphor:str; outline:list[str]; opening:str; evidence_urls:list[HttpUrl]=[]; privacy_flags:list[str]=[]
class CritiqueIn(BaseModel):
    draft:str=Field(min_length=50,max_length=30000); target_prompt:str; preserve_voice:bool=True
class SuggestionOut(BaseModel):
    start:int; end:int; replacement:str|None=None; reason:str; category:str; severity:str="suggestion"
class CritiqueOut(BaseModel):
    narrative:list[SuggestionOut]=[]; grammar:list[SuggestionOut]=[]; admissions:list[SuggestionOut]=[]; cliches:list[SuggestionOut]=[]; techniques:list[SuggestionOut]=[]; voice_drift_score:float=Field(ge=0,le=1)
