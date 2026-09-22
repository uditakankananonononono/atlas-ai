import hashlib,hmac,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m16_executive_dashboard.routes import get_proof_event_store
from app.modules.m16_executive_dashboard.proof_event_store import ProofEventStore
C=TestClient(app);U='/api/v1/executive-dashboard/proof-gaps/events/verify-and-persist';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'};K='key'
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);sessions=sessionmaker(bind=e,expire_on_commit=False);app.dependency_overrides[get_proof_event_store]=lambda:ProofEventStore('t',sessions)
def teardown_function():app.dependency_overrides.clear()
def payload():
 e={'event_id':'e','producer':'ci','module_id':'16','requirement_id':'r','event_type':'deployment_receipt','proof_sha256':'a'*64,'deployment_version':'v1','environment':'prod','issued_at':'2026-09-22T04:00:00Z','key_id':'k'};e['signature_hmac_sha256']=hmac.new(K.encode(),json.dumps(e,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest();return {'events':[e],'trusted_producer_keys':{'k':K}}
def test_authenticates_and_persists_tenant_scoped_event():
 r=C.post(U,json=payload(),headers=H);assert r.status_code==200;b=r.json();assert b['valid'] and b['tenant_id']=='t' and b['persisted_events'][0]['event_id']=='e';assert app.dependency_overrides[get_proof_event_store]().get('e').payload['environment']=='prod'
def test_duplicate_event_cannot_replace_persisted_evidence():
 p=payload();assert C.post(U,json=p,headers=H).status_code==200;r=C.post(U,json=p,headers=H);assert r.status_code==409 and 'immutable and already persisted' in r.text
def test_invalid_signature_never_persists():
 p=payload();p['events'][0]['proof_sha256']='b'*64;r=C.post(U,json=p,headers=H);assert r.status_code==409 and 'invalid producer event signature' in r.text;assert app.dependency_overrides[get_proof_event_store]().get('e') is None
