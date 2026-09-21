from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .expanded_spec_67_131 import REGISTRY,execute
router=APIRouter(prefix='/expanded-spec-67-131',tags=['opportunity-expanded-spec'])
class Request(BaseModel):row:int=Field(ge=67,le=131);data:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def capabilities():return [{'row':r,**v} for r,v in REGISTRY.items()]
@router.post('/execute')
def run(body:Request):
 try:return execute(body.row,body.data)
 except (ValueError,TypeError,KeyError) as e:raise HTTPException(422,str(e)) from e
