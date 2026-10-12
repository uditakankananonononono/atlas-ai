import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def case_tenant(request):
 return 'api704-'+hashlib.sha256(request.node.nodeid.encode()).hexdigest()

PATH='/api/v1/api/modules/20/api-documentation/openapi'
DATA={'info':{'title':'Example','version':'1'},'schemas':{},'operations':[{'operation_id':'read','method':'get','path':'/read','summary':'Read','source_ref':'caller:1','responses':{'200':{'description':'ok'}}}]}

def test_api704_owner_bound_mounted(monkeypatch,oidc_auth_headers,case_tenant):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app,raise_server_exceptions=False)
 assert c.post(PATH,json={'data':DATA}).status_code==401
 for tenant,actor in [(case_tenant,'owner'),(case_tenant+'-other','other')]:
  h=oidc_auth_headers(tenant,actor)
  r=c.post(PATH,headers=h,json={'data':DATA});assert r.status_code==200,r.text
  assert r.json()['tenant_id']==tenant and r.json()['actor_id']==actor
  assert r.json()['implementation_verified']is False
 h=oidc_auth_headers(case_tenant,'owner')
 for extra in [{'tenant_id':case_tenant+'-other'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':case_tenant+'-other'}]}]:
  assert c.post(PATH,headers=h,json={'data':DATA,**extra}).status_code==403
 assert c.post(PATH,headers=h,json={'data':{}}).status_code==422
 for packet in [{'data':['\ud800']},{'data':{'x':'\ud800'}},['\ud800'],{'data':DATA,'\ud800':'x'}]:
  r=c.post(PATH,headers={**h,'Content-Type':'application/json'},content=json.dumps(packet));assert r.status_code==422,r.text

def test_api704_exactly_64_matching_refs_accepted(monkeypatch,oidc_auth_headers,case_tenant):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app,raise_server_exceptions=False)
 refs=[{'tenant_id':case_tenant,'actor_id':'owner','id':str(i)}for i in range(64)]
 r=c.post(PATH,headers=oidc_auth_headers(case_tenant,'owner'),json={'data':DATA,'resource_refs':refs})
 assert r.status_code==200,r.text
 assert r.json()['tenant_id']==case_tenant and r.json()['implementation_verified']is False

def test_api704_65_matching_refs_refused(monkeypatch,oidc_auth_headers,case_tenant):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app,raise_server_exceptions=False)
 refs=[{'tenant_id':case_tenant,'actor_id':'owner','id':str(i)}for i in range(65)]
 r=c.post(PATH,headers=oidc_auth_headers(case_tenant,'owner'),json={'data':DATA,'resource_refs':refs})
 assert r.status_code==422,r.text

def test_api704_explicit_null_identity_fields_treated_as_absent(monkeypatch,oidc_auth_headers,case_tenant):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app,raise_server_exceptions=False)
 r=c.post(PATH,headers=oidc_auth_headers(case_tenant,'owner'),json={'data':DATA,'tenant_id':None,'actor_id':None})
 assert r.status_code==200,r.text
 assert r.json()['tenant_id']==case_tenant and r.json()['actor_id']=='owner' and r.json()['implementation_verified']is False
