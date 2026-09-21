from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .atomic_concepts_47_69 import run
class Request(BaseModel):atomic_row_id:str;data:dict[str,Any]=Field(default_factory=dict)
router=APIRouter(prefix='/atomic-concepts/47-69',tags=['atomic-concepts-47-69'])
@router.post('/analyze')
def analyze(body:Request):
 try:return run(body.atomic_row_id,body.data)
 except (ValueError,TypeError,KeyError) as e:raise HTTPException(422,str(e)) from e
