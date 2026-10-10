from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .genetic_algorithm import solve
router=APIRouter(prefix='/genetic-algorithms',tags=['m20-genetic-algorithms'])
class Request(BaseModel):
    data:dict[str,Any]
    seed:int=Field(0,ge=0,le=2**32-1,strict=True)
@router.post('/solve')
def run(request:Request):
    try:return solve(request.data,request.seed)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
