from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .cognitive_1960_2009 import ROWS,run
router=APIRouter(prefix="/cognitive-1960-2009",tags=["cognitive-1960-2009"])
class Request(BaseModel):method:str=Field(min_length=1);data:dict[str,Any]=Field(default_factory=dict);seed:int=Field(0,ge=0)
@router.get("/methods")
def methods():return [{"method":m,"feature_row":r} for m,r in ROWS.items()]
@router.post("/analyze")
def analyze(request:Request):
 try:return run(request.method,request.data,request.seed)
 except (ValueError,TypeError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc
