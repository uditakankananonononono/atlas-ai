from typing import Literal
from pydantic import BaseModel,Field
class EssayCoachingIn(BaseModel):prompt:str=Field(min_length=5,max_length=5000);student_draft:str=Field(min_length=20,max_length=100000);system:Literal['common_app','coalition','uc_piq','ucas','ouac','graduate_sop','diversity_statement','research_statement'];identity_evidence:list[str]=Field(default_factory=list,max_length=100)
class EssayCoachingOut(BaseModel):questions:list[str];outline_feedback:list[str];critique:dict[str,str];final_prose:str|None=None;guardrail:Literal['student-authored-final']='student-authored-final'
class StudentProfileIn(BaseModel):values:list[str];turning_points:list[str];strengths:list[str];academics:dict=Field(default_factory=dict);finances:dict=Field(default_factory=dict);goals:list[str]=Field(default_factory=list)
class UniversityIn(BaseModel):id:str;name:str;country:str;programs:list[str];annual_tuition_usd:float|None=None;admission_rate:float|None=None;requirements:dict=Field(default_factory=dict);official_url:str
class IdentityInterviewStartIn(BaseModel):
    track:Literal['college','career']
class IdentityInterviewTurnIn(BaseModel):
    student_response:str=Field(min_length=10,max_length=20000)
    modality:Literal['chat','voice']='chat'
    evidence_tags:list[str]=Field(default_factory=list,max_length=30)
class MajorMentorIn(BaseModel):profile:dict;majors:list[dict]=Field(min_length=1,max_length=200)
class SchoolMatchIn(BaseModel):profile:dict;schools:list[dict]=Field(min_length=1,max_length=500)
class ActivityPlannerIn(BaseModel):profile:dict;activities:list[dict]=Field(min_length=1,max_length=200);weekly_hours:float=Field(gt=0,le=168)
class PassionProjectIn(BaseModel):profile:dict;constraints:dict=Field(default_factory=dict);ideas:list[dict]=Field(min_length=1,max_length=200)
class TopicFinderIn(BaseModel):prompt:str=Field(min_length=5,max_length=5000);evidence:list[dict]=Field(min_length=1,max_length=100)
class OutlineCoachIn(BaseModel):prompt:str=Field(min_length=5,max_length=5000);student_thesis:str=Field(min_length=5,max_length=5000);evidence:list[dict]=Field(min_length=1,max_length=100)
class HookCoachIn(BaseModel):student_hook:str=Field(min_length=5,max_length=5000);evidence:list[str]=Field(min_length=1,max_length=100)
class ConclusionCoachIn(BaseModel):student_conclusion:str=Field(min_length=5,max_length=10000);thesis:str=Field(min_length=5,max_length=5000)
class ClarityReviewIn(BaseModel):draft:str=Field(min_length=20,max_length=100000)
