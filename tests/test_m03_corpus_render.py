from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m03_grant_writer.corpus import FundedAward,FundedCorpusRepository
from app.modules.m03_grant_writer.render import render_docx_pdf

def test_corpus_is_tenant_scoped_and_deduped(tmp_path):
 engine=create_engine(f"sqlite:///{tmp_path/'m3.db'}"); Base.metadata.create_all(engine); sessions=sessionmaker(bind=engine)
 a=FundedCorpusRepository("a",sessions); b=FundedCorpusRepository("b",sessions); award=FundedAward("nih_reporter","1","Cancer AI","Abstract","https://example.org/1")
 assert a.upsert([award],"ai")==1 and a.upsert([award],"ai")==0
 assert len(a.search_text("Cancer"))==1 and b.search_text("Cancer")==[]

def test_docx_pdf_renderer_creates_real_files(tmp_path):
 paths=render_docx_pdf("Proposal","ABSTRACT:\n\nEvidence based proposal text.",tmp_path)
 assert all(__import__('pathlib').Path(p).stat().st_size>100 for p in paths.values())

import asyncio
from app.modules.m03_grant_writer.corpus import BulkCorpusIngester

class AwardsClient:
 def __init__(self,source,count):self.source,self.count=source,count
 async def search(self,terms,limit=500):
  return [FundedAward(self.source,str(i),f"{terms} award {i}","official abstract",f"https://official.example/{self.source}/{i}") for i in range(min(self.count,limit))]

def test_bulk_corpus_ingester_meets_1000_with_real_unique_official_records(tmp_path):
 engine=create_engine(f"sqlite:///{tmp_path/'bulk.db'}");Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine)
 repo=FundedCorpusRepository("tenant",sessions)
 result=asyncio.run(BulkCorpusIngester(repo,AwardsClient("nih_reporter",500),AwardsClient("nsf_awards",700)).ingest("biology",1000))
 assert result.complete and result.fetched==1000 and result.created==1000
 assert len(repo.search_text("biology",limit=1100))==1000

def test_bulk_corpus_never_pads_when_official_apis_return_too_few(tmp_path):
 engine=create_engine(f"sqlite:///{tmp_path/'short.db'}");Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine)
 result=asyncio.run(BulkCorpusIngester(FundedCorpusRepository("t",sessions),AwardsClient("nih_reporter",2),AwardsClient("nsf_awards",3)).ingest("rare",1000))
 assert not result.complete and result.fetched==5 and result.created==5
