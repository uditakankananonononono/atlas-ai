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
