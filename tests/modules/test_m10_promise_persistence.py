import hashlib,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m10_email_assistant.routes import get_promise_repository
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository
C=TestClient(app);U='/api/v1/email-assistant/promise-state-reconciliation/persist';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'}
def sha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def request(snapshot):return {'reconciliation':{'previous_snapshot':snapshot,'previous_snapshot_sha256':sha(snapshot),'update_messages':[],'reviewed_decisions':[]}}
def setup_function():
 engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False);app.dependency_overrides[get_promise_repository]=lambda:SqlEmailRepository('t',sessions)
def teardown_function():app.dependency_overrides.clear()
def test_persists_first_snapshot_and_reads_tenant_scoped_head():
 s={'thread_id':'thread','promises':[]};r=C.post(U,json=request(s),headers=H);assert r.status_code==200;b=r.json();assert b['persisted'] and b['tenant_id']=='t' and len(b['reconciled_snapshot_sha256'])==64;repo=app.dependency_overrides[get_promise_repository]();assert repo.get_promise_snapshot('thread').snapshot_sha256==b['reconciled_snapshot_sha256']
def test_compare_and_swap_rejects_stale_writer_without_overwrite():
 s={'thread_id':'thread','promises':[]};first=C.post(U,json=request(s),headers=H);assert first.status_code==200
 stale={'thread_id':'thread','promises':[{'promise_id':'p','commitment':'x','source_message_id':'m','source_excerpt':'I will x','state':'open','revision':1,'last_review_sha256':None}]};r=C.post(U,json=request(stale),headers=H);assert r.status_code==409 and 'compare-and-swap failed' in r.text
 repo=app.dependency_overrides[get_promise_repository]();assert repo.get_promise_snapshot('thread').snapshot_sha256==first.json()['reconciled_snapshot_sha256']
def test_second_write_requires_stored_head_and_advances_atomically():
 s={'thread_id':'thread','promises':[]};first=C.post(U,json=request(s),headers=H).json();persisted=first['reconciled_snapshot'];p=request(persisted);r=C.post(U,json=p,headers=H);assert r.status_code==200 and r.json()['previous_snapshot_sha256']==first['reconciled_snapshot_sha256']
