from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m13_browser_agent.routes import get_service
C=TestClient(app);U='/api/v1/browser-agent/submit/pre-submit-capture';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'}
class Page:url='https://shop.example/confirm'
class Adapter:
 calls=[]
 async def page(self,t,s,p):self.calls.append('page');return Page()
 async def read_values(self,t,s,x):self.calls.append('values');return {'qty':'2'}
 async def extract(self,t,s):self.calls.append('dom');return '<html>confirm</html>'
 async def screenshot(self,t,s,mask_selectors):self.calls.append('screenshot');p='/tmp/m13-shot.png';Path(p).write_bytes(b'PNG');return p
class Service:sessions=Adapter()
def setup_function():Service.sessions.calls=[];app.dependency_overrides[get_service]=lambda:Service()
def teardown_function():app.dependency_overrides.clear()
def test_captures_adapter_evidence_in_one_pre_submit_readback():
 r=C.post(U,json={'session_id':'s1','selectors':['qty']},headers=H);assert r.status_code==200;b=r.json();assert b['destination'].endswith('/confirm') and b['fields']=={'qty':'2'};assert len(b['dom_sha256'])==len(b['screenshot_sha256'])==len(b['capture_sha256'])==64;assert Service.sessions.calls==['page','values','dom','screenshot'];assert 'does not establish' in b['boundary']
def test_fails_closed_when_screenshot_bytes_are_missing():
 async def missing(*a,**k):return '/tmp/not-there-atlas.png'
 Service.sessions.screenshot=missing;r=C.post(U,json={'session_id':'s1'},headers=H);assert r.status_code==422 and 'screenshot is missing' in r.text
