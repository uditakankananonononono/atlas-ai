from typing import Any
from pydantic import BaseModel,Field
class GoalIn(BaseModel):goal:str=Field(min_length=3,max_length=8000);acceptance:list[str]=[];limits:dict[str,Any]={}
class EnvironmentChangeIn(BaseModel):operation:str;preview:dict[str,Any]
