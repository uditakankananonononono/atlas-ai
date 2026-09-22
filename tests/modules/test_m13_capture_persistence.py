import base64,hashlib,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m13_browser_agent.routes import get_service
from app.modules.m13_browser_agent.store import SQLStore
C=TestClient(app);U='/api/v1/browser-agent/submit/pre-submit-capture/persist';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'}
class S:pass
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);S.store=SQLStore(sessionmaker(bind=e,expire_on_commit=False));app.dependency_overrides[get_service]=lambda:S()
def teardown_function():app.dependency_overrides.clear()
def payload():
 dom=b'<html>x</html>';shot=b'PNG';a={'session_id':'s','destination':'https://x','fields':{'q':'1'},'captured_at':'2026-09-22T04:00:00+00:00','dom_sha256':hashlib.sha256(dom).hexdigest(),'screenshot_sha256':hashlib.sha256(shot).hexdigest()};return {**a,'capture_sha256':hashlib.sha256(json.dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'dom_base64':base64.b64encode(dom).decode(),'screenshot_base64':base64.b64encode(shot).decode()}
def test_persists_verified_capture_bytes_immutably():
 p=payload();r=C.post(U,json=p,headers=H);assert r.status_code==200 and r.json()['persisted'];row=__import__('asyncio').run(S.store.get_capture('t',p['capture_sha256']));assert row.dom_bytes==b'<html>x</html>' and row.screenshot_bytes==b'PNG'
def test_rejects_tampered_bytes_and_duplicate_capture():
 p=payload();p['dom_base64']=base64.b64encode(b'bad').decode();r=C.post(U,json=p,headers=H);assert r.status_code==409 and 'DOM byte hash mismatch' in r.text
 p=payload();assert C.post(U,json=p,headers=H).status_code==200;r=C.post(U,json=p,headers=H);assert r.status_code==409 and 'immutable capture cannot be replaced' in r.text
