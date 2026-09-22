import base64,hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m10_email_assistant.routes import get_source_message_store
from app.modules.m10_email_assistant.source_message_store import SourceMessageStore
C=TestClient(app);U='/api/v1/email-assistant/promise-state-reconciliation/source-messages/persist';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'};RAW=b'I sent it'
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);sessions=sessionmaker(bind=e,expire_on_commit=False);app.dependency_overrides[get_source_message_store]=lambda:SourceMessageStore('t',sessions)
def teardown_function():app.dependency_overrides.clear()
def p(raw=RAW):return {'message_id':'m','content_sha256':hashlib.sha256(RAW).hexdigest(),'content_base64':base64.b64encode(raw).decode()}
def test_persists_verified_bytes_and_exact_repeat_is_idempotent():
 r=C.post(U,json=p(),headers=H);assert r.status_code==200 and r.json()['byte_count']==len(RAW);assert C.post(U,json=p(),headers=H).status_code==200
def test_rejects_tampered_bytes_and_message_replacement():
 r=C.post(U,json=p(b'bad'),headers=H);assert r.status_code==409 and 'byte hash mismatch' in r.text
 assert C.post(U,json=p(),headers=H).status_code==200;x={'message_id':'m','content_sha256':hashlib.sha256(b'other').hexdigest(),'content_base64':base64.b64encode(b'other').decode()};r=C.post(U,json=x,headers=H);assert r.status_code==409 and 'immutable source-message conflict' in r.text
