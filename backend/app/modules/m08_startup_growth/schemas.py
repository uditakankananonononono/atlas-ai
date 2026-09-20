"""Contracts for Module 8, Startup Growth."""
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field
class LandingPageIn(BaseModel):
    project_id:str=Field(min_length=1,max_length=120); product_name:str=Field(min_length=1,max_length=160); hero:str=Field(min_length=3,max_length=1000)
    features:list[str]=Field(min_length=1,max_length=20); waitlist_table:str=Field(default="waitlist",pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
    brand:dict[str,str]=Field(default_factory=dict)
class PitchDeckIn(BaseModel):
    project_id:str; company:str; problem:str; solution:str; market_size:str; traction:list[str]=Field(default_factory=list,max_length=30); ask:str
    chart_series:dict[str,list[float]]=Field(default_factory=dict)
class DocumentationIn(BaseModel):
    project_id:str; title:str; feature_list:list[str]=Field(default_factory=list,max_length=100); code_files:dict[str,str]=Field(default_factory=dict)
    outputs:list[Literal["openapi","redoc","user_manual","technical_blog"]]=Field(default_factory=lambda:["openapi","redoc","user_manual"])
class BuildOut(BaseModel):
    id:str; project_id:str; kind:Literal["landing_page","pitch_deck","documentation"]; manifest:dict[str,Any]; sha256:str; created_at:datetime
class PublishProposal(BaseModel):
    approval_id:str; action_type:Literal["push_startup_site","deploy_startup_site","share_pitch_deck","publish_documentation"]; payload:dict[str,Any]; status:Literal["pending"]="pending"
