from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .political_social_1760_1809 import AnalysisError,ROWS,analyze
router=APIRouter(prefix='/political-social-1760-1809',tags=['m20-political-social'])
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def capabilities():return [{'row_id':i,'name':n} for i,n in ROWS.items()]
@router.post('/{row_id}')
def run(row_id:int,request:Request):
 try:return analyze(row_id,request.payload)
 except AnalysisError as e:raise HTTPException(422,detail=str(e)) from e
