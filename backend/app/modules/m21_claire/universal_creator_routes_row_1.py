from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .universal_creator_row_1 import plan
router=APIRouter(prefix="/universal-creator-row-1",tags=["claire-universal-creator"])
class Request(BaseModel):
 goal:str=Field(min_length=1,max_length=1000);kind:str;candidates:list[dict[str,Any]]=Field(default_factory=list,max_length=100);owner_facts:dict[str,Any]=Field(default_factory=dict);requested_actions:list[str]=Field(default_factory=list)
@router.post('/plan')
def create_plan(body:Request):
 try:return plan(body.goal,body.kind,body.candidates,body.owner_facts,body.requested_actions)
 except ValueError as e:raise HTTPException(422,str(e)) from e
