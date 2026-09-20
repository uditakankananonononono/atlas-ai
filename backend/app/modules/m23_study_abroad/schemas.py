from typing import Literal
from pydantic import BaseModel,Field
class EssayCoachingIn(BaseModel):prompt:str=Field(min_length=5,max_length=5000);student_draft:str=Field(min_length=20,max_length=100000);system:Literal['common_app','coalition','uc_piq','ucas','ouac','graduate_sop','diversity_statement','research_statement'];identity_evidence:list[str]=Field(default_factory=list,max_length=100)
class EssayCoachingOut(BaseModel):questions:list[str];outline_feedback:list[str];critique:dict[str,str];final_prose:str|None=None;guardrail:Literal['student-authored-final']='student-authored-final'
class StudentProfileIn(BaseModel):values:list[str];turning_points:list[str];strengths:list[str];academics:dict=Field(default_factory=dict);finances:dict=Field(default_factory=dict);goals:list[str]=Field(default_factory=list)
class UniversityIn(BaseModel):id:str;name:str;country:str;programs:list[str];annual_tuition_usd:float|None=None;admission_rate:float|None=None;requirements:dict=Field(default_factory=dict);official_url:str
