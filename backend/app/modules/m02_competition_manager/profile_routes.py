from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from app.auth.context import TenantContext,require_tenant
from app.core.embeddings import get_embedding_provider
from app.integrations.google_grounding import GoogleWorkspaceGrounder
from .profile_corpus import ProfileCorpus
router=APIRouter(prefix='/competition-manager/profile-corpus',tags=['competition-profile-corpus'])
class DocsIn(BaseModel):document_ids:list[str]=Field(min_length=1,max_length=100);embedding_provider:str='openai'
class SheetsIn(BaseModel):spreadsheet_id:str;ranges:list[str]=Field(min_length=1,max_length=100);embedding_provider:str='openai'
class RetrieveIn(BaseModel):query:str=Field(min_length=3,max_length=10000);limit:int=Field(8,ge=1,le=50);embedding_provider:str='openai'
def corpus(t,provider):return ProfileCorpus(t.tenant_id,get_embedding_provider(provider))
@router.post('/google-docs')
async def docs(x:DocsIn,t:TenantContext=Depends(require_tenant)):
 g=GoogleWorkspaceGrounder()
 try:return await corpus(t,x.embedding_provider).ingest([await g.document(i) for i in x.document_ids])
 finally:await g.close()
@router.post('/google-sheets')
async def sheets(x:SheetsIn,t:TenantContext=Depends(require_tenant)):
 g=GoogleWorkspaceGrounder()
 try:return await corpus(t,x.embedding_provider).ingest(await g.sheet(x.spreadsheet_id,x.ranges))
 finally:await g.close()
@router.post('/retrieve')
async def retrieve(x:RetrieveIn,t:TenantContext=Depends(require_tenant)):return await corpus(t,x.embedding_provider).retrieve(x.query,x.limit)
