import asyncio
from sqlalchemy import JSON,String,Text,create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.retrieval import RetrievalPipeline,SourceDocument
from app.core.vector_store import MemoryEmbeddingRow
class E:
 async def embed(self,texts):
  return [[float('robot' in x.lower()),float('health' in x.lower())]+[0.0]*1022 for x in texts]
def test_ingest_chunk_embed_rerank_and_citations_are_tenant_scoped(tmp_path):
 engine=create_engine(f"sqlite:///{tmp_path/'r.db'}");Base.metadata.create_all(engine);factory=sessionmaker(bind=engine)
 a=RetrievalPipeline('a','profile',E(),factory);b=RetrievalPipeline('b','profile',E(),factory)
 doc=SourceDocument('d1','Robot essay','I built a robot for water health testing.','docs/d1',{'revision':'r1'})
 assert asyncio.run(a.ingest([doc]))['chunks']==1
 hit=asyncio.run(a.retrieve('robot'));assert hit[0]['citation']['source_id']=='d1' and hit[0]['citation']['sha256']
 assert asyncio.run(b.retrieve('robot'))==[]
