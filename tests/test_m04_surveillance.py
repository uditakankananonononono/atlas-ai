import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m04_research_scientist.schemas import PaperInput
from app.modules.m04_research_scientist.surveillance import SurveillancePipeline,SurveillanceRepository
class Embedder:
 async def embed(self,texts):return [[1,0],[.8,.6],[0,1]][:len(texts)]
def p(i,title,kw):return PaperInput(paper_id=i,title=title,abstract="A sufficiently long official abstract for durable surveillance.",source="arxiv",keywords=kw)
def test_surveillance_is_durable_tenant_scoped_embedding_clustered_and_gap_backed(tmp_path):
 e=create_engine(f"sqlite:///{tmp_path/'s.db'}");Base.metadata.create_all(e);sessions=sessionmaker(bind=e)
 a=SurveillancePipeline(SurveillanceRepository("a",sessions),Embedder());b=SurveillancePipeline(SurveillanceRepository("b",sessions),Embedder())
 papers=[p("p1","Tumor atlas",["tumor","spatial"]),p("p2","Spatial immune niches",["spatial","immune"]),p("p3","Quantum control",["quantum"])]
 assert asyncio.run(a.ingest(papers))=={"received":3,"created":3}
 assert a.clusters(.75)==[["p1","p2"]]
 assert b.clusters(.1)==[]
 gaps=a.gaps(.5,.9)
 assert {(x.left_paper_id,x.right_paper_id) for x in gaps}=={("p1","p2"),("p2","p3")}
 assert all(x.gap.startswith("Test whether") for x in gaps)
def test_surveillance_upsert_deduplicates_paper_ids(tmp_path):
 e=create_engine(f"sqlite:///{tmp_path/'d.db'}");Base.metadata.create_all(e);sessions=sessionmaker(bind=e);x=SurveillancePipeline(SurveillanceRepository("t",sessions),Embedder());paper=p("p1","Title one",["x"])
 assert asyncio.run(x.ingest([paper]))["created"]==1
 assert asyncio.run(x.ingest([paper]))["created"]==0
