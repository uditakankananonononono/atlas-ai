from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m17_narrative_architect.routes import get_publication_adapter,get_revision_store
from app.modules.m17_narrative_architect.revision_store import RevisionStore
C=TestClient(app);U='/api/v1/narrative-architect/revision-publication/execute';P='/api/v1/narrative-architect/evidence-completeness/revision-acceptance/persist';H={'X-Atlas-Tenant':'owner','X-Atlas-Actor':'u'}
class Adapter:
 def publish(self,audience,revision):return {'audience_boundary':audience,'revision_sha256':revision,'provider_id':'p'}
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);sessions=sessionmaker(bind=e,expire_on_commit=False)
 app.dependency_overrides[get_revision_store]=lambda:RevisionStore('owner',sessions)
 app.dependency_overrides[get_publication_adapter]=lambda:Adapter()
def teardown_function():app.dependency_overrides.clear()
def acc(essay_id='e',disclosure=True):
 return {'essay_id':essay_id,'from_version':'v1','to_version':'v2','revision_sha256':'a'*64,'accepted_suggestions':[{'suggestion_id':'s1','suggestion_sha256':'b'*64,'owner_record_sha256':'c'*64}],'reviewed_by_owner':True,'reviewed_at':'2026-09-22T04:00:00Z','audience_boundary':'admissions','disclosure_approved':disclosure}
def persist(**kw):
 r=C.post(P,json=acc(**kw),headers=H);assert r.status_code==200;return r.json()['acceptance_sha256']
def p(acceptance_sha256,**over):
 body={'essay_id':'e','to_version':'v2','revision_sha256':'a'*64,'acceptance_sha256':acceptance_sha256,'reviewed_by_owner':True,'audience_boundary':'admissions','disclosure_approved':True};body.update(over);return body
def test_publishes_exact_reviewed_revision_to_approved_audience():
 a=persist();r=C.post(U,json=p(a),headers=H);assert r.status_code==200;b=r.json();assert b['published'] and b['audience_boundary']=='admissions' and b['publication_receipt']['revision_sha256']=='a'*64 and b['acceptance_sha256']==a
def test_fails_closed_without_review_or_disclosure_approval():
 r=C.post(U,json=p('b'*64),headers=H);assert r.status_code==409 and 'persisted revision acceptance is required before publication' in r.text
 a=persist();r=C.post(U,json=p(a,reviewed_by_owner=False),headers=H);assert r.status_code==409 and 'owner review' in r.text
 a2=persist(essay_id='e2',disclosure=False);r=C.post(U,json=p(a2,essay_id='e2'),headers=H);assert r.status_code==409 and 'disclosure approval' in r.text
 persist(essay_id='e3');r=C.post(U,json=p('d'*64,essay_id='e3'),headers=H);assert r.status_code==409 and 'does not match persisted revision acceptance' in r.text
def test_rejects_mismatched_publication_receipt():
 class Bad:
  def publish(self,a,r):return {'audience_boundary':'public','revision_sha256':r}
 a=persist();app.dependency_overrides[get_publication_adapter]=lambda:Bad();r=C.post(U,json=p(a),headers=H);assert r.status_code==409 and 'does not match approved audience and revision' in r.text
