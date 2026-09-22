import hashlib
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m11_calendar_intelligence.routes import get_risk_source_retriever
C=TestClient(app);U='/api/v1/calendar-intelligence/schedule-risk/live-evidence/retrieve';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'};RAW=b'live vendor terms'
class R:
 def fetch(self,uri):return RAW
def setup_function():app.dependency_overrides[get_risk_source_retriever]=lambda:R()
def teardown_function():app.dependency_overrides.clear()
def p():return {'source_uri':'https://vendor.example/terms','expected_sha256':hashlib.sha256(RAW).hexdigest(),'provider':'vendor','retrieval_token':'opaque-handle'}
def test_retrieves_through_adapter_and_verifies_bytes():
 r=C.post(U,json=p(),headers=H);assert r.status_code==200 and r.json()['verified'] and r.json()['byte_count']==len(RAW)
def test_rejects_hash_mismatch_and_empty_bytes():
 x=p();x['expected_sha256']='a'*64;r=C.post(U,json=x,headers=H);assert r.status_code==422 and 'hash mismatch' in r.text
 class Empty:
  def fetch(self,u):return b''
 app.dependency_overrides[get_risk_source_retriever]=lambda:Empty();r=C.post(U,json=p(),headers=H);assert r.status_code==422 and 'empty bytes' in r.text
