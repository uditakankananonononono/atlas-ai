from pathlib import Path
import base64
import binascii
from pydantic import BaseModel, Field
from app.ingest.asr_provisioning import config_from_env
from app.ingest.offline_asr import ASRError
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
            if _factory is None:_factory=KnowledgeServiceFactory(root, asr_config=config_from_env())
            elif str(_factory.root)!=root:raise ServiceUnavailable(UNAVAILABLE)
            config=config_from_env()
            if (config is None) != (_factory.asr_config is None):raise ServiceUnavailable(UNAVAILABLE)
            if config is not None and (config != _factory.asr_config or _factory.profile != 'deterministic-embedder-v1+offline-whisper-v1:'+config.identity()):raise ServiceUnavailable(UNAVAILABLE)
        with _factory.service(t.tenant_id,t.actor_id) as service:yield service
    except OwnerMismatch:raise HTTPException(403,'knowledge owner access required') from None
    except (ServiceUnavailable,ASRError):raise HTTPException(503,UNAVAILABLE) from None
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


class AudioIngestRequest(BaseModel):
    source: SourceRegistration
    actor_id: str = Field(min_length=1)
    audio_base64: str = Field(min_length=1, max_length=26668)


@router.post('/ingest-audio')
def ingest_audio(data: AudioIngestRequest, s: LocalKnowledgePipeline = Depends(get_service)):
    """Explicit bounded PCM-WAV transport; source consent checks stay in pipeline."""
    from app.ingest.offline_asr import KnowledgeTranscriber
    if not isinstance(s.transcriber, KnowledgeTranscriber):
        raise HTTPException(503, UNAVAILABLE)
    try:
        audio = base64.b64decode(data.audio_base64, validate=True)
        if not 0 < len(audio) <= MAX_INGEST_CONTENT:
            raise ValueError()
    except (ValueError, binascii.Error):
        raise HTTPException(422, 'invalid bounded audio encoding') from None
    try:
        v = s.ingest(IngestRequest(source=data.source, actor_id=data.actor_id,
                                  content=audio, mime_type='audio/wav'))
        return {'version':v.number,'content_hash':v.content_hash,'segments':len(v.segments)}
    except (KnowledgeError,AdapterUnavailable,ASRError) as exc:
        raise HTTPException(422,str(exc)) from None
