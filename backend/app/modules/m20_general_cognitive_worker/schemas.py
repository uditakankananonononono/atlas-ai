from typing import Any
from pydantic import BaseModel,Field
class GoalIn(BaseModel):
    goal:str=Field(min_length=3,max_length=8000);constraints:dict[str,Any]={};budget:dict[str,float]={"seconds":900,"tokens":100000,"money":0}
