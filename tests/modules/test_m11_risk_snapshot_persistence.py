import base64,hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m11_calendar_intelligence.routes import get_risk_snapshot_store
from app.modules.m11_calendar_intelligence.risk_snapshot_store import RiskSnapshotStore
C=TestClient(app);U='/api/v1/calendar-intelligence/schedule-risk/live-evidence/snapshots/persist';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'};RAW=b'vendor policy bytes'
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);sessions=sessionmaker(bind=e,expire_on_commit=False);app.dependency_overrides[get_risk_snapshot_store]=lambda:RiskSnapshotStore('t',sessions)
def teardown_function():app.dependency_overrides.clear()
def p(uri='https://vendor/policy'):return {'source_uri':uri,'content_sha256':hashlib.sha256(RAW).hexdigest(),'content_base64':base64.b64encode(RAW).decode()}
def test_persists_verified_bytes_and_idempotent_repeat():
 r=C.post(U,json=p(),headers=H);assert r.status_code==200 and r.json()['byte_count']==len(RAW);r=C.post(U,json=p(),headers=H);assert r.status_code==200
def test_rejects_tampered_bytes_and_hash_collision_metadata_conflict():
 x=p();x['content_base64']=base64.b64encode(b'bad').decode();r=C.post(U,json=x,headers=H);assert r.status_code==409 and 'byte hash mismatch' in r.text
 assert C.post(U,json=p(),headers=H).status_code==200;r=C.post(U,json=p('https://other'),headers=H);assert r.status_code==409 and 'immutable source snapshot conflict' in r.text
