from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m17_narrative_architect.routes import get_revision_store
from app.modules.m17_narrative_architect.revision_store import RevisionStore
C=TestClient(app);U='/api/v1/narrative-architect/evidence-completeness/revision-acceptance/persist';H={'X-Atlas-Tenant':'owner','X-Atlas-Actor':'u'}
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);sessions=sessionmaker(bind=e,expire_on_commit=False);app.dependency_overrides[get_revision_store]=lambda:RevisionStore('owner',sessions)
def teardown_function():app.dependency_overrides.clear()
def p(a='v1',b='v2'):return {'essay_id':'e','from_version':a,'to_version':b,'revision_sha256':'a'*64,'accepted_suggestions':[{'suggestion_id':b,'suggestion_sha256':'b'*64,'owner_record_sha256':'c'*64}],'reviewed_by_owner':True,'reviewed_at':'2026-09-22T04:00:00Z','audience_boundary':'admissions','disclosure_approved':False}
def test_persists_append_only_revision_chain():
 r=C.post(U,json=p(),headers=H);assert r.status_code==200 and r.json()['persisted'];r=C.post(U,json=p('v2','v3'),headers=H);assert r.status_code==200 and r.json()['to_version']=='v3'
def test_rejects_chain_break_and_duplicate_target():
 assert C.post(U,json=p(),headers=H).status_code==200;r=C.post(U,json=p('v0','v3'),headers=H);assert r.status_code==409 and 'chain break' in r.text
 r=C.post(U,json=p('v2','v2'),headers=H);assert r.status_code in (409,422)
