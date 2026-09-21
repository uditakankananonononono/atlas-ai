from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .emerging_biomed_960_1009 import ROWS,run
router=APIRouter(prefix="/emerging-biomed-960-1009",tags=["emerging-biomed"])
class Request(BaseModel):method:str=Field(min_length=1);data:dict[str,Any]=Field(default_factory=dict)
@router.get('/methods')
def methods():return [{"method":m,"feature_row":r} for m,r in ROWS.items()]
@router.post('/analyze')
def analyze(body:Request):
 try:return run(body.method,body.data)
 except (ValueError,TypeError,KeyError,ZeroDivisionError) as e:raise HTTPException(422,str(e)) from e
