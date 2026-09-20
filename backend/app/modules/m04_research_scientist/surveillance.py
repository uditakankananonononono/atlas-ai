"""Durable tenant literature surveillance, embedding clustering and gap evidence."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from itertools import combinations
import math
from sqlalchemy import JSON,DateTime,String,Text,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .schemas import PaperInput

class SurveillancePaperRow(Base):
    __tablename__="m04_surveillance_papers"
    __table_args__=(UniqueConstraint("tenant_id","paper_id"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    tenant_id:Mapped[str]=mapped_column(String(120),index=True)
    paper_id:Mapped[str]=mapped_column(String(200),index=True)
    title:Mapped[str]=mapped_column(Text);abstract:Mapped[str]=mapped_column(Text)
    source:Mapped[str]=mapped_column(String(40));url:Mapped[str|None]=mapped_column(Text,nullable=True)
    published_at:Mapped[str|None]=mapped_column(String(100),nullable=True)
    keywords:Mapped[list]=mapped_column(JSON,default=list);embedding:Mapped[list]=mapped_column(JSON)
    collected_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

@dataclass(frozen=True)
class GapEvidence:
    left_paper_id:str;right_paper_id:str;similarity:float;shared_keywords:list[str];gap:str

class SurveillanceRepository:
    def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal):
        self.tenant_id=tenant_id;self.sessions=session_factory;Base.metadata.create_all(engine)
    def upsert(self,papers:list[PaperInput],vectors:list[list[float]])->int:
        if len(papers)!=len(vectors):raise ValueError("paper/vector count mismatch")
        created=0
        with self.sessions.begin() as db:
            for p,v in zip(papers,vectors):
                row=db.scalar(select(SurveillancePaperRow).where(SurveillancePaperRow.tenant_id==self.tenant_id,SurveillancePaperRow.paper_id==p.paper_id))
                values=dict(title=p.title,abstract=p.abstract,source=p.source,url=str(p.url) if p.url else None,published_at=p.published_at,keywords=p.keywords,embedding=v)
                if row is None:db.add(SurveillancePaperRow(tenant_id=self.tenant_id,paper_id=p.paper_id,**values));created+=1
                else:
                    for k,val in values.items():setattr(row,k,val)
        return created
    def rows(self):
        with self.sessions() as db:return list(db.scalars(select(SurveillancePaperRow).where(SurveillancePaperRow.tenant_id==self.tenant_id)))

def cosine(a,b):
    dot=sum(x*y for x,y in zip(a,b));norm=math.sqrt(sum(x*x for x in a))*math.sqrt(sum(y*y for y in b));return 0 if not norm else dot/norm

class SurveillancePipeline:
    def __init__(self,repository,embedder):self.repository,self.embedder=repository,embedder
    async def ingest(self,papers:list[PaperInput]):
        vectors=await self.embedder.embed([f"{p.title}\n{p.abstract}" for p in papers])
        return {"received":len(papers),"created":self.repository.upsert(papers,vectors)}
    def clusters(self,threshold=.72):
        rows=self.repository.rows();parent={r.paper_id:r.paper_id for r in rows}
        def find(x):
            while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
            return x
        def union(a,b):parent[find(b)]=find(a)
        for a,b in combinations(rows,2):
            if cosine(a.embedding,b.embedding)>=threshold:union(a.paper_id,b.paper_id)
        groups={}
        for r in rows:groups.setdefault(find(r.paper_id),[]).append(r.paper_id)
        return [sorted(v) for v in groups.values() if len(v)>1]
    def gaps(self,min_similarity=.25,max_similarity=.72):
        rows=self.repository.rows();out=[]
        for a,b in combinations(rows,2):
            score=cosine(a.embedding,b.embedding)
            shared=sorted(set(a.keywords)&set(b.keywords))
            if min_similarity<=score<max_similarity:
                out.append(GapEvidence(a.paper_id,b.paper_id,round(score,4),shared,f"Test whether the mechanism in {a.paper_id} transfers to the context in {b.paper_id}."))
        return out
