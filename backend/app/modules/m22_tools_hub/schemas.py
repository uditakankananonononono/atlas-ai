from typing import Any
from pydantic import BaseModel,Field
class DiscoveryIn(BaseModel):query:str=Field(min_length=2,max_length=500)
class InstallIn(BaseModel):candidate_id:str;adapter_type:str;config:dict[str,Any]={};requested_scopes:list[str]=[]
