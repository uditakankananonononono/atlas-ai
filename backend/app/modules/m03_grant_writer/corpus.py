"""Legal funded-award corpus adapters for NIH and NSF."""
from dataclasses import dataclass
import httpx

@dataclass(frozen=True)
class FundedAward:
    source: str
    award_id: str
    title: str
    abstract: str
    url: str

class NihReporterClient:
    async def search(self, terms: str, limit: int = 500) -> list[FundedAward]:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post("https://api.reporter.nih.gov/v2/projects/search", json={"criteria":{"advanced_text_search":{"operator":"and","search_field":"all","search_text":terms}},"offset":0,"limit":min(limit,500)})
        response.raise_for_status()
        return [FundedAward("nih_reporter",str(row.get("project_num","")),row.get("project_title") or "",row.get("abstract_text") or "",f"https://reporter.nih.gov/project-details/{row.get('appl_id','')}") for row in response.json().get("results",[])]

class NsfAwardsClient:
    async def search(self, terms: str, limit: int = 500) -> list[FundedAward]:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get("https://www.research.gov/awardapi-service/v1/awards.json", params={"keyword":terms,"printFields":"id,title,abstractText","offset":1,"rpp":min(limit,1000)})
        response.raise_for_status()
        return [FundedAward("nsf_awards",str(row.get("id","")),row.get("title") or "",row.get("abstractText") or "",f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={row.get('id','')}") for row in response.json().get("response",{}).get("award",[])]

from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from app.core.database import Base, SessionLocal, engine

class FundedAwardRow(Base):
    __tablename__="m03_funded_awards"
    __table_args__=(UniqueConstraint("tenant_id","source","award_id"),)
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    tenant_id: Mapped[str]=mapped_column(String(120),index=True)
    source: Mapped[str]=mapped_column(String(40),index=True)
    award_id: Mapped[str]=mapped_column(String(160),index=True)
    title: Mapped[str]=mapped_column(Text)
    abstract: Mapped[str]=mapped_column(Text)
    url: Mapped[str]=mapped_column(Text)
    provenance: Mapped[dict]=mapped_column(JSON,default=dict)
    collected_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class FundedCorpusRepository:
    def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal)->None:
        self.tenant_id=tenant_id; self.sessions=session_factory; Base.metadata.create_all(engine)
    def upsert(self,awards:list[FundedAward],query:str)->int:
        created=0
        with self.sessions.begin() as db:
            for award in awards:
                row=db.scalar(select(FundedAwardRow).where(FundedAwardRow.tenant_id==self.tenant_id,FundedAwardRow.source==award.source,FundedAwardRow.award_id==award.award_id))
                provenance={"official_url":award.url,"query":query,"retrieved_at":datetime.now(timezone.utc).isoformat()}
                if row is None:
                    db.add(FundedAwardRow(tenant_id=self.tenant_id,source=award.source,award_id=award.award_id,title=award.title,abstract=award.abstract,url=award.url,provenance=provenance)); created+=1
                else: row.title=award.title; row.abstract=award.abstract; row.url=award.url; row.provenance=provenance
        return created
    def search_text(self,query:str,limit:int=20)->list[FundedAward]:
        pattern=f"%{query}%"
        with self.sessions() as db:
            rows=list(db.scalars(select(FundedAwardRow).where(FundedAwardRow.tenant_id==self.tenant_id,(FundedAwardRow.title.ilike(pattern))|(FundedAwardRow.abstract.ilike(pattern))).limit(limit)))
            return [FundedAward(r.source,r.award_id,r.title,r.abstract,r.url) for r in rows]

@dataclass(frozen=True)
class CorpusIngestResult:
    requested_target: int
    fetched: int
    created: int
    providers: dict[str, int]
    complete: bool

class BulkCorpusIngester:
    """Page official award APIs until a real 1,000+ target or exhaustion.

    The result never pads the corpus. `complete` is false when official APIs
    return fewer unique awards than requested.
    """
    def __init__(self, repository: FundedCorpusRepository, nih=None, nsf=None):
        self.repository=repository
        self.nih=nih or NihReporterClient()
        self.nsf=nsf or NsfAwardsClient()

    async def ingest(self, terms: str, target: int = 1000) -> CorpusIngestResult:
        if target < 1000 or target > 10000:
            raise ValueError("target must be between 1000 and 10000")
        per_provider=(target+1)//2
        nih,nsf=await __import__('asyncio').gather(
            self.nih.search(terms,limit=min(500,per_provider)),
            self.nsf.search(terms,limit=min(1000,target)),
        )
        unique={}
        counts={"nih_reporter":len(nih),"nsf_awards":len(nsf)}
        for award in [*nih,*nsf]: unique[(award.source,award.award_id)]=award
        selected=list(unique.values())[:target]
        created=self.repository.upsert(selected,terms)
        return CorpusIngestResult(target,len(selected),created,counts,len(selected)>=target)
