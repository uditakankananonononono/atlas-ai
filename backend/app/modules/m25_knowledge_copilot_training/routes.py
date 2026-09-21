from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .pipeline import *
from .schemas import *
router=APIRouter(prefix='/knowledge-copilot-training',tags=['knowledge-copilot-training'])
_services={}
def get_service(t:TenantContext=Depends(require_tenant)):
    key=(t.tenant_id,t.actor_id)
    return _services.setdefault(key,LocalKnowledgePipeline(Path('/tmp/atlas-knowledge'),t.tenant_id,t.actor_id))
@router.post('/ingest')
def ingest(data:IngestRequest,s:LocalKnowledgePipeline=Depends(get_service)):
    try:
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
