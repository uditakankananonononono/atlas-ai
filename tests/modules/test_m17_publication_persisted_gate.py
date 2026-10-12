from app.modules.m17_narrative_architect.publication_gate import PublicationGateRequest,publish_through_gate
from publication_fixture_helpers import SignedAdapter,register
from app.modules.m17_narrative_architect.publication_key_registry import PublicationKeyRegistry
from app.core.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
Adapter=SignedAdapter
engine=create_engine('sqlite://');Base.metadata.create_all(engine)
registry=register(PublicationKeyRegistry('owner',sessionmaker(bind=engine,expire_on_commit=False)))
def test_publication_requires_exact_persisted_acceptance():
 b=PublicationGateRequest(essay_id='e',to_version='v2',revision_sha256='a'*64,acceptance_sha256='b'*64,reviewed_by_owner=True,audience_boundary='admissions',disclosure_approved=True)
 acceptance={**b.model_dump(),'from_version':'v1'}
 assert publish_through_gate(b,Adapter(),acceptance,key_registry=registry)['published']
 for changed in ({**acceptance,'acceptance_sha256':'c'*64},{**acceptance,'disclosure_approved':False}):
  try:publish_through_gate(b,Adapter(),changed,key_registry=registry)
  except ValueError:pass
  else:raise AssertionError('unverified acceptance published')
