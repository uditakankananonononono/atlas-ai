from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .negotiation_behavior_0085_0109 import ROWS,run
router=APIRouter(prefix='/negotiation-behavior-85-109',tags=['m20-negotiation-behavior'])
class Request(BaseModel):method:str;data:dict[str,Any]=Field(default_factory=dict)
@router.get('/methods')
def methods():return [{'method':m,'feature_row':r} for m,r in ROWS.items()]
@router.post('/analyze')
def analyze(req:Request):
 try:return run(req.method,req.data)
 except ValueError as e:raise HTTPException(422,str(e))
