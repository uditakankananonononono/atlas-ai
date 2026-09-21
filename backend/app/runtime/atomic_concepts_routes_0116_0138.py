from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel
from .atomic_concepts_0116_0138 import REG,execute
router=APIRouter(prefix='/atomic-concepts-116-138',tags=['atomic-concepts'])
class Request(BaseModel):atomic_row_id:str;data:dict[str,Any]
@router.get('/capabilities')
def caps():return [{'atomic_row_id':k,'requirement':v} for k,v in REG.items()]
@router.post('/execute')
def run(b:Request):
 try:return execute(b.atomic_row_id,b.data)
 except (ValueError,TypeError,KeyError,IndexError,ZeroDivisionError) as e:raise HTTPException(422,str(e)) from e
