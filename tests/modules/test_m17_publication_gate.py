from fastapi.testclient import TestClient
from app.main import app
from app.modules.m17_narrative_architect.routes import get_publication_adapter
C=TestClient(app);U='/api/v1/narrative-architect/revision-publication/execute';H={'X-Atlas-Tenant':'owner','X-Atlas-Actor':'u'}
class Adapter:
 def publish(self,audience,revision):return {'audience_boundary':audience,'revision_sha256':revision,'provider_id':'p'}
def setup_function():app.dependency_overrides[get_publication_adapter]=lambda:Adapter()
def teardown_function():app.dependency_overrides.clear()
def p():return {'essay_id':'e','to_version':'v2','revision_sha256':'a'*64,'acceptance_sha256':'b'*64,'reviewed_by_owner':True,'audience_boundary':'admissions','disclosure_approved':True}
def test_publishes_exact_reviewed_revision_to_approved_audience():
 r=C.post(U,json=p(),headers=H);assert r.status_code==200;b=r.json();assert b['published'] and b['audience_boundary']=='admissions' and b['publication_receipt']['revision_sha256']=='a'*64
def test_fails_closed_without_review_or_disclosure_approval():
 x=p();x['reviewed_by_owner']=False;r=C.post(U,json=x,headers=H);assert r.status_code==409 and 'owner review' in r.text
 x=p();x['disclosure_approved']=False;r=C.post(U,json=x,headers=H);assert r.status_code==409 and 'disclosure approval' in r.text
def test_rejects_mismatched_publication_receipt():
 class Bad:
  def publish(self,a,r):return {'audience_boundary':'public','revision_sha256':r}
 app.dependency_overrides[get_publication_adapter]=lambda:Bad();r=C.post(U,json=p(),headers=H);assert r.status_code==409 and 'does not match' in r.text
