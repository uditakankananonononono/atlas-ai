import asyncio
from dataclasses import dataclass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.integrations.google_grounding import GroundedSource
from app.modules.m02_competition_manager.profile_corpus import ProfileCorpus
from app.modules.m02_competition_manager.grounded_drafting import GroundedApplicationDrafter
class E:
 async def embed(self,texts):return [[1,0] if 'robot' in x.lower() else [0,1] for x in texts]
def source(i,text):return GroundedSource('google_doc',i,f'docs/{i}',text,{'title':f'Owner doc {i}','revision_id':'r1'})
def test_owner_docs_are_durable_deduped_tenant_scoped_and_retrieved(tmp_path):
 e=create_engine(f"sqlite:///{tmp_path/'c.db'}");Base.metadata.create_all(e);s=sessionmaker(bind=e);a=ProfileCorpus('a',E(),s);b=ProfileCorpus('b',E(),s)
 assert asyncio.run(a.ingest([source('1','I built a robot for water testing.'),source('2','I wrote an essay about public health.')]))=={'indexed':2,'created':2}
 assert asyncio.run(a.ingest([source('1','I built a robot for water testing.')]))['created']==0
 got=asyncio.run(a.retrieve('robot engineering'));assert got[0]['source_id']=='1' and got[0]['provenance']['revision_id']=='r1'
 assert asyncio.run(b.retrieve('robot engineering'))==[]
def test_drafts_require_owner_corpus_and_preserve_source_provenance():
 async def gen(prompt,provider,model):
  assert 'Do not invent activities' in prompt and '[1] Owner doc 1' in prompt
  return 'model','I built a water-testing robot. [1]'
 d=GroundedApplicationDrafter(gen)
 try:asyncio.run(d.draft('impact','What did you build?','500 words',[]))
 except ValueError:pass
 else:raise AssertionError
 hits=[{'id':1,'title':'Owner doc 1','source_type':'google_doc','source_id':'1','locator':'docs/1','text':'I built a water-testing robot.'}]
 out=asyncio.run(d.draft('impact','What did you build?','500 words',hits));assert out['source_ids']==[1] and out['requires_human_review']
