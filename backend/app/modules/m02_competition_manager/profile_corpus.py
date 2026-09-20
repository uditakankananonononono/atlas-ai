"""Tenant corpus of owner-authored application source material."""
from __future__ import annotations
from datetime import datetime,timezone
import math
from sqlalchemy import JSON,DateTime,String,Text,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class ProfileDocumentRow(Base):
 __tablename__='m02_profile_documents';__table_args__=(UniqueConstraint('tenant_id','source_type','source_id','locator'),)
 id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);source_type:Mapped[str]=mapped_column(String(40));source_id:Mapped[str]=mapped_column(String(500));locator:Mapped[str]=mapped_column(String(1000));title:Mapped[str]=mapped_column(Text);text:Mapped[str]=mapped_column(Text);provenance:Mapped[dict]=mapped_column(JSON);embedding:Mapped[list]=mapped_column(JSON);indexed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
def cos(a,b):
 n=math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b));return 0 if not n else sum(x*y for x,y in zip(a,b))/n
class ProfileCorpus:
 def __init__(self,tenant_id,embedder,session_factory:sessionmaker=SessionLocal):self.tenant_id,self.embedder,self.sessions=tenant_id,embedder,session_factory;Base.metadata.create_all(engine)
 async def ingest(self,sources):
  texts=[x.text for x in sources];vectors=await self.embedder.embed(texts);created=0
  with self.sessions.begin() as db:
   for src,vec in zip(sources,vectors):
    row=db.scalar(select(ProfileDocumentRow).where(ProfileDocumentRow.tenant_id==self.tenant_id,ProfileDocumentRow.source_type==src.source_type,ProfileDocumentRow.source_id==src.source_id,ProfileDocumentRow.locator==src.locator))
    vals={'title':src.provenance.get('title') or src.locator,'text':src.text,'provenance':src.provenance,'embedding':vec}
    if row is None:db.add(ProfileDocumentRow(tenant_id=self.tenant_id,source_type=src.source_type,source_id=src.source_id,locator=src.locator,**vals));created+=1
    else:
     for k,v in vals.items():setattr(row,k,v)
  return {'indexed':len(sources),'created':created}
 async def retrieve(self,query,limit=8):
  q=(await self.embedder.embed([query]))[0]
  with self.sessions() as db:rows=list(db.scalars(select(ProfileDocumentRow).where(ProfileDocumentRow.tenant_id==self.tenant_id)))
  rows.sort(key=lambda x:cos(q,x.embedding),reverse=True)
  return [{'id':x.id,'source_type':x.source_type,'source_id':x.source_id,'locator':x.locator,'title':x.title,'text':x.text,'provenance':x.provenance,'score':round(cos(q,x.embedding),4)} for x in rows[:limit]]
