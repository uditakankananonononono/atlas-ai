from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .social_research_1710_1759 import SocialResearchError,capabilities,execute
router=APIRouter(prefix='/social-research-1710-1759',tags=['m20-social-research-1710-1759'])
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def list_capabilities():return capabilities()
@router.post('/{method}')
def run(method:str,request:Request):
 try:return execute(method,request.payload)
 except SocialResearchError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
