from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .lifecycle_unverified_01_62 import ROWS,BY_METHOD,run
router=APIRouter(prefix='/lifecycle-workbench',tags=['study-abroad-lifecycle'])
class Request(BaseModel):method:str;data:dict[str,Any]=Field(default_factory=dict)
@router.get('/methods')
def methods():return [{'row':r,'method':m} for r,m in ROWS.items()]
@router.post('/analyze')
def analyze(req:Request):
 try:return run(req.method,req.data)
 except (ValueError,KeyError,TypeError) as e:raise HTTPException(422,str(e))
