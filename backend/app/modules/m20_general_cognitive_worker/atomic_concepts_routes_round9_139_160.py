from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .atomic_concepts_round9_139_160 import CONCEPTS,ConceptError,execute
router=APIRouter(prefix="/atomic-concepts/139-160",tags=["atomic concepts 139-160"])
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get("")
def list_concepts():return [{"atomic_row_id":k,"concept":v} for k,v in CONCEPTS.items()]
@router.post("/{atomic_row_id}")
def run(atomic_row_id:str,request:Request):
 try:return execute(atomic_row_id,request.payload)
 except ConceptError as exc:raise HTTPException(422,str(exc)) from exc
