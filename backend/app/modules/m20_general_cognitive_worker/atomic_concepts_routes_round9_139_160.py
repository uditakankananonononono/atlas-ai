from typing import Any
from fastapi import APIRouter,HTTPException,Depends
from threading import RLock
from app.auth.context import TenantContext,require_tenant
from pydantic import BaseModel,Field
from .atomic_concepts_round9_139_160 import CONCEPTS,ConceptError,Corpus,execute
router=APIRouter(prefix="/atomic-concepts/139-160",tags=["atomic concepts 139-160"])
_corpora:dict[tuple[str,str],Corpus]={}
_corpus_lock=RLock()
class Request(BaseModel):payload:dict[str,Any]=Field(default_factory=dict)
@router.get("")
def list_concepts():return [{"atomic_row_id":k,"concept":v} for k,v in CONCEPTS.items()]
@router.post("/{atomic_row_id}")
def run(atomic_row_id:str,request:Request,principal:TenantContext=Depends(require_tenant)):
 payload=dict(request.payload)
 if atomic_row_id.startswith('2010.'):
  if 'owner_id' in payload and payload['owner_id']!=principal.actor_id:
   raise HTTPException(403,'corpus owner must match authenticated subject')
  payload['owner_id']=principal.actor_id
 try:
  # Per-tenant, per-subject namespace, never the process-global default corpus.
  with _corpus_lock:
   corpus=_corpora.setdefault((principal.tenant_id,principal.actor_id),Corpus())
   return execute(atomic_row_id,payload,corpus=corpus)
 except ConceptError as exc:raise HTTPException(422,str(exc)) from exc
