from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .technical_spec_0133_0165 import META,BY,run
router=APIRouter(prefix='/technical-spec-133-165',tags=['technical-spec'])
class Request(BaseModel):method:str;data:dict[str,Any]=Field(default_factory=dict)
@router.get('/methods')
def methods():return [{'row':r,'requirement_id':v[0],'source_line_start':v[1],'source_line_end':v[2],'method':v[3]} for r,v in META.items()]
@router.post('/analyze')
def analyze(req:Request):
 try:return run(req.method,req.data)
 except (ValueError,KeyError,TypeError) as e:raise HTTPException(422,str(e))
