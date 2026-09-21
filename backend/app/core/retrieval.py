"""Tenant-scoped chunk/embed/ANN/rerank retrieval with citation preservation."""
from __future__ import annotations
import hashlib,re,uuid
from dataclasses import dataclass
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session,sessionmaker
from app.core.vector_store import MemoryEmbeddingRow

@dataclass(frozen=True)
class SourceDocument:
 source_id:str; title:str; text:str; locator:str; metadata:dict[str,Any]

def chunk_document(doc:SourceDocument,max_chars:int=1800,overlap:int=200)->list[dict[str,Any]]:
 if max_chars<200 or overlap<0 or overlap>=max_chars:raise ValueError('invalid chunk window')
 text=re.sub(r'\s+',' ',doc.text).strip()
 if not text:raise ValueError('source text is empty')
 chunks=[];start=0;index=0
 while start<len(text):
  end=min(len(text),start+max_chars)
  if end<len(text):
   boundary=text.rfind(' ',start+max_chars//2,end)
   if boundary>start:end=boundary
  body=text[start:end].strip(); digest=hashlib.sha256(f'{doc.source_id}:{index}:{body}'.encode()).hexdigest()
  chunks.append({'id':str(uuid.UUID(digest[:32])),'text':body,'metadata':{**doc.metadata,'source_id':doc.source_id,'title':doc.title,'locator':doc.locator,'chunk_index':index,'sha256':hashlib.sha256(body.encode()).hexdigest()}})
  if end==len(text):break
  start=end-overlap;index+=1
 return chunks

class RetrievalPipeline:
 def __init__(self,tenant_id:str,namespace:str,embedder,session_factory:sessionmaker):
  if not tenant_id or not namespace:raise ValueError('tenant and namespace required')
  self.tenant_id,self.namespace,self.embedder,self.sessions=tenant_id,namespace,embedder,session_factory
 async def ingest(self,documents:list[SourceDocument])->dict[str,int]:
  chunks=[chunk for doc in documents for chunk in chunk_document(doc)]
  vectors=await self.embedder.embed([x['text'] for x in chunks])
  if len(vectors)!=len(chunks):raise ValueError('embedding count mismatch')
  with self.sessions.begin() as db:
   for chunk,vector in zip(chunks,vectors):
    if len(vector)!=1024:raise ValueError('embedding dimension must be 1024')
    row=db.get(MemoryEmbeddingRow,chunk['id']);values={'tenant_id':self.tenant_id,'namespace':self.namespace,'text':chunk['text'],'metadata_json':chunk['metadata'],'embedding':vector}
    if row is None:db.add(MemoryEmbeddingRow(id=chunk['id'],**values))
    else:
     if row.tenant_id!=self.tenant_id:raise PermissionError('cross-tenant chunk collision')
     for key,value in values.items():setattr(row,key,value)
  return {'documents':len(documents),'chunks':len(chunks)}
 async def retrieve(self,query:str,limit:int=8,candidates:int=40)->list[dict[str,Any]]:
  if not query.strip() or not 1<=limit<=50 or candidates<limit:raise ValueError('invalid retrieval request')
  vector=(await self.embedder.embed([query]))[0]
  if len(vector)!=1024:raise ValueError('embedding dimension must be 1024')
  with self.sessions() as db:
   dialect=db.get_bind().dialect.name
   stmt=select(MemoryEmbeddingRow).where(MemoryEmbeddingRow.tenant_id==self.tenant_id,MemoryEmbeddingRow.namespace==self.namespace)
   if dialect=='postgresql':stmt=stmt.order_by(MemoryEmbeddingRow.embedding.cosine_distance(vector)).limit(candidates)
   rows=list(db.scalars(stmt))
  terms=set(re.findall(r'[a-z0-9]+',query.lower()))
  def score(row):
   lexical=len(terms&set(re.findall(r'[a-z0-9]+',row.text.lower())))/max(1,len(terms))
   try:dense=1-float(row.embedding.cosine_distance(vector))
   except Exception:
    a=list(row.embedding);dot=sum(x*y for x,y in zip(a,vector));na=sum(x*x for x in a)**.5;nb=sum(x*x for x in vector)**.5;dense=dot/(na*nb) if na and nb else 0
   return .8*dense+.2*lexical,dense,lexical
  ranked=sorted(((score(row),row) for row in rows),key=lambda x:x[0][0],reverse=True)[:limit]
  return [{'id':row.id,'text':row.text,'score':round(scores[0],6),'dense_score':round(scores[1],6),'lexical_score':round(scores[2],6),'citation':{'source_id':row.metadata_json['source_id'],'title':row.metadata_json['title'],'locator':row.metadata_json['locator'],'chunk_index':row.metadata_json['chunk_index'],'sha256':row.metadata_json['sha256']}} for scores,row in ranked]
