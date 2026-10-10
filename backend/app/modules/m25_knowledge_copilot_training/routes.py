from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .pipeline import *
from .schemas import *
router=APIRouter(prefix='/knowledge-copilot-training',tags=['knowledge-copilot-training'])
from threading import RLock
import os
from .service_factory import KnowledgeServiceFactory,ServiceUnavailable,OwnerMismatch,UNAVAILABLE
_factory=None
_factory_lock=RLock()
def get_service(t:TenantContext=Depends(require_tenant)):
    global _factory
    try:
        with _factory_lock:
            root=os.environ.get('ATLAS_M25_DURABLE_ROOT')
            if _factory is None:_factory=KnowledgeServiceFactory(root)
            elif str(_factory.root)!=root:raise ServiceUnavailable(UNAVAILABLE)
        with _factory.service(t.tenant_id,t.actor_id) as service:yield service
    except OwnerMismatch:raise HTTPException(403,'knowledge owner access required') from None
    except ServiceUnavailable:raise HTTPException(503,UNAVAILABLE) from None
@router.post('/ingest')
def ingest(data:IngestRequest,s:LocalKnowledgePipeline=Depends(get_service)):
    try:
        if data.mime_type=='audio/wav':raise HTTPException(503,UNAVAILABLE)
        v=s.ingest(data);return {'version':v.number,'content_hash':v.content_hash,'segments':len(v.segments)}
    except (KnowledgeError,AdapterUnavailable) as e:raise HTTPException(422,str(e))
@router.post('/search')
def search(data:SearchRequest,s:LocalKnowledgePipeline=Depends(get_service)):return s.search(data.query,data.limit)
@router.get('/export')
def export(s:LocalKnowledgePipeline=Depends(get_service)):return s.export()
@router.delete('/sources/{source_id}')
def delete(source_id:str,s:LocalKnowledgePipeline=Depends(get_service)):
    try:return s.delete_verified(source_id)
    except KeyError:raise HTTPException(404,'source not found')
@router.get('/contradictions')
def contradictions(subject:str,s:LocalKnowledgePipeline=Depends(get_service)):return s.contradictions(subject)
@router.post('/claims/substantiate')
def substantiate(claims:list[Claim],s:LocalKnowledgePipeline=Depends(get_service)):
    try:return [x.model_dump(mode='json') for x in s.substantiate(claims)]
    except UnsupportedClaim as e:raise HTTPException(422,str(e))
