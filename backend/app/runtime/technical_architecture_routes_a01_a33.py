from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from typing import Any
from .technical_architecture_a01_a33 import *
router=APIRouter(prefix='/technical-architecture-a01-a33',tags=['technical-architecture'])
_ltm=UniversalLTM(lambda text:[float(len(text)),float(len(text.split()))])
class LTMRequest(BaseModel):tenant_id:str;artifact:dict[str,Any]=Field(default_factory=dict)
@router.get('/mapping')
def source_mapping():return mapping()
@router.post('/ltm/ingest')
def ltm_ingest(request:LTMRequest):
 try:return _ltm.ingest(request.tenant_id,request.artifact)
 except ArchitectureError as exc:raise HTTPException(422,detail=str(exc)) from exc
