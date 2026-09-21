from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .atomic_concepts_0093_0115 import META,run
router=APIRouter(prefix='/atomic-concepts-93-115',tags=['atomic-concepts'])
class Request(BaseModel):method:str;data:dict[str,Any]=Field(default_factory=dict)
@router.get('/methods')
def methods():return [{'atomic_row':r,'atomic_row_id':x[0],'method':x[1]} for r,x in META.items()]
@router.post('/analyze')
def analyze(req:Request):
 try:return run(req.method,req.data)
 except (ValueError,KeyError,TypeError) as e:raise HTTPException(422,str(e))
