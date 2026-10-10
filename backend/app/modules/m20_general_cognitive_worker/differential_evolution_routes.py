from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .differential_evolution import solve
router=APIRouter(prefix='/differential-evolution',tags=['m20-differential-evolution'])
class Request(BaseModel):
    data:dict[str,Any]
    seed:int=Field(0,ge=0,le=2**32-1,strict=True)
@router.post('/solve')
def run(request:Request):
    try:return solve(request.data,request.seed)
    except ValueError as exc:raise HTTPException(422,str(exc))from exc
