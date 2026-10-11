from fastapi.testclient import TestClient
from app.main import app

def test_mounted_owner_limits_and_no_execution(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);path='/api/v1/api/modules/20/legacy-modernization/694/modernize';body={'source':'for x in xrange(2): pass'}
 assert c.post(path,json=body).status_code==401
 for tenant,actor in [('a','owner'),('b','other')]:
  r=c.post(path,headers=oidc_auth_headers(tenant,actor),json=body);assert r.status_code==200,r.text
  assert r.json()['tenant_id']==tenant and r.json()['actor_id']==actor and r.json()['source_execution_performed']is False
 h=oidc_auth_headers('a','owner')
 for extra in [{'tenant_id':'b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'b'}]}]:assert c.post(path,headers=h,json={**body,**extra}).status_code==403
 for extra in [{'source':'x'*100001},{'rules':['xrange']*8},{'rules':['unknown']},{'source':'😀'*30000}]:assert c.post(path,headers=h,json={**body,**extra}).status_code==422
 r=c.post(path,headers=h,json={'source':'raise RuntimeError("never executed")'});assert r.status_code==200 and r.json()['verified']is False

def test_known_unicode_defect_and_resource_failure_refuse(monkeypatch,oidc_auth_headers):
 from app.modules.m20_general_cognitive_worker import legacy_modernizer_routes694 as routes
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner');path='/api/v1/api/modules/20/legacy-modernization/694/modernize'
 r=c.post(path,headers=h,json={'source':'self.ａssertEquals(1, 1)'});assert r.status_code==422 and r.json()['detail']=='legacy694 Unicode source-span defect; transformation refused'
 for exc in [RecursionError,MemoryError]:
  def fail(*args,**kwargs):raise exc()
  monkeypatch.setattr(routes,'modernize',fail);r=c.post(path,headers=h,json={'source':'x=1'});assert r.status_code==422 and r.json()['detail']=='legacy694 parser resource limit; transformation refused'

def test_lone_surrogate_refuses_422(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app)
 r=c.post('/api/v1/api/modules/20/legacy-modernization/694/modernize',headers={**oidc_auth_headers('a','owner'),'Content-Type':'application/json'},content='{"source":"\\ud800"}')
 assert r.status_code==422 and r.json()['detail']=='source contains invalid Unicode surrogate'

import json
import pytest

@pytest.mark.parametrize('packet',[
 {'source':['\ud800']}, {'source':{'x':'\ud800'}},
 {'source':'x=1','rules':'\ud800'}, ['\ud800'],
 {'source':'x=1','\ud800':'x'},
 {'source':'x=1','resource_refs':[{'note':['\ud800']}]},
 {'source':'x=1','tenant_id':'\ud800'},
 {'source':'x=1','rules':['\ud800']},
 {'source':'\udfff'},
])
def test_surrogate_keys_values_and_type_error_shapes_refuse(monkeypatch,oidc_auth_headers,packet):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app,raise_server_exceptions=False)
 r=c.post('/api/v1/api/modules/20/legacy-modernization/694/modernize',headers={**oidc_auth_headers('a','owner'),'Content-Type':'application/json'},content=json.dumps(packet))
 assert r.status_code==422,r.text
 assert r.json()['detail']=='source contains invalid Unicode surrogate'

@pytest.mark.parametrize('packet',[
 {'source':['plain']}, {'source':{'x':'plain'}},
 {'source':'x=1','rules':'plain'}, ['plain'],
])
def test_nonsurrogate_type_errors_remain_422(monkeypatch,oidc_auth_headers,packet):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app,raise_server_exceptions=False)
 r=c.post('/api/v1/api/modules/20/legacy-modernization/694/modernize',headers=oidc_auth_headers('a','owner'),json=packet)
 assert r.status_code==422,r.text

@pytest.mark.parametrize('source',['x=1','name="é"','name="😀"'])
def test_valid_unicode_stays_accepted(monkeypatch,oidc_auth_headers,source):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app,raise_server_exceptions=False)
 r=c.post('/api/v1/api/modules/20/legacy-modernization/694/modernize',headers=oidc_auth_headers('a','owner'),json={'source':source})
 assert r.status_code==200,r.text
 assert r.json()['source_execution_performed']is False

def test_deep_json_refuses_before_validation(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app,raise_server_exceptions=False)
 nested='plain'
 for _ in range(66):nested=[nested]
 r=c.post('/api/v1/api/modules/20/legacy-modernization/694/modernize',headers=oidc_auth_headers('a','owner'),json={'source':'x=1','extra':nested})
 assert r.status_code==422,r.text
 assert r.json()['detail']=='legacy694 JSON nesting exceeds 64 levels'
