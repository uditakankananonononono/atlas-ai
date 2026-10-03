from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from app.auth.context import TenantContext,require_tenant
from app.core.embeddings import get_embedding_provider
from app.integrations.google_grounding import GoogleWorkspaceGrounder
import hashlib,os
from pydantic import field_validator
from typing import Literal
from app.core.embeddings import EmbeddingError
from .profile_corpus import ProfileCorpus
from .onboarding import OnboardingService
from types import SimpleNamespace
def default_provider():return os.getenv('ATLAS_PROFILE_EMBEDDING_PROVIDER','lexical')
async def guarded(aw):
 try:return await aw
 except EmbeddingError as e:raise HTTPException(503,f'Embedding model unavailable: {e}. Use the offline keyword default (provider "lexical") or start your local model server.')
 except Exception as e:
  if type(e).__name__ in {'ConnectError','ConnectTimeout','ReadTimeout'}:raise HTTPException(503,'Embedding model server is not reachable.')
  raise
router=APIRouter(prefix='/competition-manager/profile-corpus',tags=['competition-profile-corpus'])
class DocsIn(BaseModel):doc_type:Literal['writings','essays','activity_descriptions']|None=None;document_ids:list[str]=Field(min_length=1,max_length=100);embedding_provider:str|None=None
class SheetsIn(BaseModel):spreadsheet_id:str;ranges:list[str]=Field(min_length=1,max_length=100);embedding_provider:str|None=None
class RetrieveIn(BaseModel):query:str=Field(min_length=3,max_length=10000);limit:int=Field(8,ge=1,le=50);embedding_provider:str|None=None
CLIENT_PROVIDERS={'lexical','ollama','bge','local'}
def resolve_provider(requested):
 """Clients may only pick offline/local providers; anything hosted is chosen by the server env alone."""
 default=default_provider()
 if requested is None:return default
 name=requested.lower()
 if name==default or name in CLIENT_PROVIDERS:return name
 raise HTTPException(422,f'embedding_provider must be one of {sorted(CLIENT_PROVIDERS)} or the server default')
def corpus(t,provider):
 name=resolve_provider(provider)
 try:return ProfileCorpus(t.tenant_id,get_embedding_provider(name),provider_name=name)
 except EmbeddingError as e:raise HTTPException(422,str(e))
@router.post('/google-docs')
async def docs(x:DocsIn,t:TenantContext=Depends(require_tenant)):
 try:g=GoogleWorkspaceGrounder()
 except Exception as e:raise HTTPException(503,f'Google Docs unavailable: {e}')
 try:
  srcs=[await g.document(i) for i in x.document_ids]
  if x.doc_type:
   for s in srcs:s.provenance['doc_type']=x.doc_type
  return await guarded(corpus(t,x.embedding_provider).ingest(srcs))
 except RuntimeError as e:raise HTTPException(503,f'Google Docs unavailable: {e}')
 finally:await g.close()
@router.post('/google-sheets')
async def sheets(x:SheetsIn,t:TenantContext=Depends(require_tenant)):
 g=GoogleWorkspaceGrounder()
 try:return await guarded(corpus(t,x.embedding_provider).ingest(await g.sheet(x.spreadsheet_id,x.ranges)))
 finally:await g.close()
@router.post('/retrieve')
async def retrieve(x:RetrieveIn,t:TenantContext=Depends(require_tenant)):return await guarded(corpus(t,x.embedding_provider).retrieve(x.query,x.limit))
class OnboardingCompleteIn(BaseModel):document_types:list[str];source_ids:list[int]
@router.get('/onboarding/launch-step')
def onboarding_step(t:TenantContext=Depends(require_tenant)):return OnboardingService(t.tenant_id).launch_step()
@router.post('/onboarding/complete')
def onboarding_complete(x:OnboardingCompleteIn,t:TenantContext=Depends(require_tenant)):
 try:return OnboardingService(t.tenant_id).complete(x.document_types,x.source_ids,ProfileCorpus(t.tenant_id,None).list_docs())
 except ValueError as e:raise HTTPException(422,str(e))
@router.post('/onboarding/skip')
def onboarding_skip(t:TenantContext=Depends(require_tenant)):return OnboardingService(t.tenant_id).skip()

class PasteIn(BaseModel):
 model_config={'extra':'forbid'}
 doc_type:Literal['writings','essays','activity_descriptions'];title:str=Field(min_length=1,max_length=200);text:str=Field(min_length=20,max_length=200000)
 @field_validator('title','text',mode='before')
 @classmethod
 def _strip(cls,v):return v.strip() if isinstance(v,str) else v
@router.post('/onboarding/documents')
async def onboarding_paste(x:PasteIn,t:TenantContext=Depends(require_tenant)):
 """Owner pastes their own text. Always indexed with the server's configured provider (not client-selectable)."""
 sid='paste:'+hashlib.sha256((x.doc_type+x.title+x.text).encode()).hexdigest()[:16]
 src=SimpleNamespace(text=x.text,source_type='pasted',source_id=sid,locator='paste/'+x.doc_type,provenance={'title':x.title,'doc_type':x.doc_type,'origin':'owner_paste'})
 c=corpus(t,None);out=await guarded(c.ingest([src]))
 docs=c.list_docs();row=next(d for d in docs if d['source_id']==sid)
 return {**out,'document':row,'status':OnboardingService(t.tenant_id).status(docs)}
async def drafting_model():
 """Report, without guessing, whether a local drafting model is configured and reachable."""
 model=os.getenv('ATLAS_OLLAMA_MODEL');url=os.getenv('ATLAS_OLLAMA_URL','http://ollama:11434').rstrip('/')
 if not model:return {'configured':False,'reachable':False,'detail':'No local drafting model configured (set ATLAS_OLLAMA_MODEL to a model your machine can run).'}
 try:
  import httpx
  async with httpx.AsyncClient(timeout=1.5) as c:r=await c.get(url+'/api/tags')
  names=[m.get('name') for m in r.json().get('models',[])] if r.status_code==200 else []
  ok=model in names
  return {'configured':True,'reachable':r.status_code==200,'model':model,'installed':ok,'detail':'' if ok else f'Model "{model}" is not installed on the local model server.'}
 except Exception:
  return {'configured':True,'reachable':False,'model':model,'installed':False,'detail':'Local model server is not reachable.'}
@router.get('/onboarding/status')
async def onboarding_status(t:TenantContext=Depends(require_tenant)):
 docs=ProfileCorpus(t.tenant_id,None).list_docs();prov=default_provider()
 return {**OnboardingService(t.tenant_id).status(docs),'documents_list':docs,'embedding_provider':prov,'indexing_leaves_machine':prov in {'openai'},'indexing_note':'Offline keyword indexing: text is not sent to any model service.' if prov=='lexical' else f'Indexing uses "{prov}".','drafting_model':await drafting_model()}
