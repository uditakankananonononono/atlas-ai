import json
from fastapi.testclient import TestClient
from app.main import app

PATH='/api/v1/api/modules/20/api-documentation/openapi'
DATA={'info':{'title':'Example','version':'1'},'schemas':{},'operations':[]}

def test_api704_owner_bound_mounted(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app,raise_server_exceptions=False)
 assert c.post(PATH,json={'data':DATA}).status_code==401
 for tenant,actor in [('a','owner'),('b','other')]:
  h=oidc_auth_headers(tenant,actor)
  r=c.post(PATH,headers=h,json={'data':DATA});assert r.status_code==200,r.text
  assert r.json()['tenant_id']==tenant and r.json()['actor_id']==actor
  assert r.json()['implementation_verified']is False
 h=oidc_auth_headers('a','owner')
 for extra in [{'tenant_id':'b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'b'}]}]:
  assert c.post(PATH,headers=h,json={'data':DATA,**extra}).status_code==403
 assert c.post(PATH,headers=h,json={'data':{}}).status_code==422
 for packet in [{'data':['\ud800']},{'data':{'x':'\ud800'}},['\ud800'],{'data':DATA,'\ud800':'x'}]:
  r=c.post(PATH,headers={**h,'Content-Type':'application/json'},content=json.dumps(packet));assert r.status_code==422,r.text
