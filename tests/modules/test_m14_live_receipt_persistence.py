import hashlib,hmac,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m14_project_builder.routes import get_live_receipt_store
from app.modules.m14_project_builder.live_receipt_store import LiveReceiptStore
C=TestClient(app);U='/api/v1/project-builder/proof-status/live-receipts/verify-and-persist';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'};K='secret'
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);sessions=sessionmaker(bind=e,expire_on_commit=False);app.dependency_overrides[get_live_receipt_store]=lambda:LiveReceiptStore('t',sessions)
def teardown_function():app.dependency_overrides.clear()
def payload():
 r={'receipt_id':'r','requirement_id':'req','deployed_version':'v1','environment':'prod','acceptance_inputs_sha256':'a'*64,'result_sha256':'b'*64,'status':'passed','issued_at':'2026-09-22T04:00:00Z','key_id':'k'};r['signature_hmac_sha256']=hmac.new(K.encode(),json.dumps(r,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest();return {'expected_version':'v1','expected_environment':'prod','expected_inputs_sha256':'a'*64,'receipts':[r],'trusted_keys':{'k':K}}
def test_verifies_and_persists_tenant_scoped_receipt():
 r=C.post(U,json=payload(),headers=H);assert r.status_code==200;b=r.json();assert b['valid'] and b['tenant_id']=='t' and b['persisted_receipts'][0]['receipt_id']=='r';assert app.dependency_overrides[get_live_receipt_store]().get('r').environment=='prod'
def test_duplicate_receipt_cannot_replace_persisted_evidence():
 p=payload();assert C.post(U,json=p,headers=H).status_code==200;r=C.post(U,json=p,headers=H);assert r.status_code==409 and 'immutable and already persisted' in r.text
def test_invalid_signature_never_persists():
 p=payload();p['receipts'][0]['status']='failed';r=C.post(U,json=p,headers=H);assert r.status_code==409 and 'invalid receipt signature' in r.text;assert app.dependency_overrides[get_live_receipt_store]().get('r') is None
