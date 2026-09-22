from app.modules.m17_narrative_architect.publication_gate import PublicationGateRequest,publish_through_gate
class Adapter:
 def publish(self,a,r):return {'audience_boundary':a,'revision_sha256':r}
def test_publication_requires_exact_persisted_acceptance():
 b=PublicationGateRequest(essay_id='e',to_version='v2',revision_sha256='a'*64,acceptance_sha256='b'*64,reviewed_by_owner=True,audience_boundary='admissions',disclosure_approved=True)
 acceptance={**b.model_dump(),'from_version':'v1'}
 assert publish_through_gate(b,Adapter(),acceptance)['published']
 for changed in ({**acceptance,'acceptance_sha256':'c'*64},{**acceptance,'disclosure_approved':False}):
  try:publish_through_gate(b,Adapter(),changed)
  except ValueError:pass
  else:raise AssertionError('unverified acceptance published')
