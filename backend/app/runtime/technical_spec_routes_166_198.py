from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .technical_spec_166_198 import MAP,execute
router=APIRouter(prefix='/technical-spec-166-198',tags=['technical-spec'])
class Request(BaseModel):row:int=Field(ge=166,le=198);data:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def capabilities():return [{'row':r,'requirement_id':q} for r,q in MAP.items()]
@router.post('/execute')
def run(body:Request):
 try:return execute(body.row,body.data)
 except (ValueError,TypeError,KeyError,SyntaxError,ZeroDivisionError) as e:raise HTTPException(422,str(e)) from e
