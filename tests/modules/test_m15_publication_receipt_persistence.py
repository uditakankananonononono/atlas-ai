import hashlib,hmac,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m15_document_generator.routes import get_publication_receipt_store
from app.modules.m15_document_generator.publication_receipt_store import PublicationReceiptStore
C=TestClient(app);U='/api/v1/document-generator/publication-receipts/provider/verify-and-persist';H={'X-Atlas-Tenant':'t'};K='key'
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);sessions=sessionmaker(bind=e,expire_on_commit=False);app.dependency_overrides[get_publication_receipt_store]=lambda:PublicationReceiptStore('t',sessions)
def teardown_function():app.dependency_overrides.clear()
def p():
 r={'approval_id':'a','version_id':'v','provider':'store','object_key':'private/v','access':'private','download_url':'https://files/v','published_sha256':'a'*64,'byte_size':42,'uploaded_at':'2026-09-22T04:00:00Z','key_id':'k'};r['signature_hmac_sha256']=hmac.new(K.encode(),json.dumps(r,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest();return {'expected_sha256':'a'*64,'approval_consumed':True,'receipt':r,'trusted_provider_keys':{'k':K}}
def test_verifies_and_persists_publication_receipt():
 r=C.post(U,json=p(),headers=H);assert r.status_code==200 and r.json()['persisted'];assert app.dependency_overrides[get_publication_receipt_store]().get('a').object_key=='private/v'
def test_duplicate_approval_or_object_cannot_replace_receipt():
 x=p();assert C.post(U,json=x,headers=H).status_code==200;r=C.post(U,json=x,headers=H);assert r.status_code==409 and 'immutable and already persisted' in r.text
def test_invalid_receipt_never_persists():
 x=p();x['receipt']['byte_size']=43;r=C.post(U,json=x,headers=H);assert r.status_code==409 and 'invalid provider receipt signature' in r.text;assert app.dependency_overrides[get_publication_receipt_store]().get('a') is None
