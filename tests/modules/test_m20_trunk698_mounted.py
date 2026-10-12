import json
from fastapi.testclient import TestClient
from app.main import app

PATH='/api/v1/api/modules/20/trunk-based-development/698/analyze'
DATA={'source_ref': 'audit/repo-snapshot-1', 'trunk': 'main', 'reference_time': '2026-10-11T12:00:00+05:30', 'max_branch_age_hours': 24, 'required_checks': ['ci', 'lint'], 'commits': [{'sha': '0000000000000000000000000000000000000001', 'parents': [], 'committed_at': '2026-10-07T02:30:00Z'}, {'sha': '0000000000000000000000000000000000000002', 'parents': ['0000000000000000000000000000000000000001'], 'committed_at': '2026-10-07T12:30:00Z'}, {'sha': '0000000000000000000000000000000000000003', 'parents': ['0000000000000000000000000000000000000002'], 'committed_at': '2026-10-10T00:30:00Z'}, {'sha': '0000000000000000000000000000000000000004', 'parents': ['0000000000000000000000000000000000000002'], 'committed_at': '2026-10-10T10:30:00Z'}, {'sha': '0000000000000000000000000000000000000005', 'parents': ['0000000000000000000000000000000000000004'], 'committed_at': '2026-10-10T20:30:00Z'}], 'branches': [{'name': 'main', 'tip': '0000000000000000000000000000000000000003'}, {'name': 'feat', 'tip': '0000000000000000000000000000000000000005'}], 'checks': [{'name': 'ci', 'sha': '0000000000000000000000000000000000000005', 'conclusion': 'success'}, {'name': 'lint', 'sha': '0000000000000000000000000000000000000005', 'conclusion': 'success'}, {'name': 'ci', 'sha': '0000000000000000000000000000000000000003', 'conclusion': 'success'}]}

def _client(monkeypatch):
 monkeypatch.setenv('ATLAS_ENV','production');return TestClient(app,raise_server_exceptions=False)

def test_trunk698_owner_bound_mounted(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch)
 assert c.post(PATH,json={'data':DATA}).status_code==401
 for tenant,actor in [('a','owner'),('b','other')]:
  r=c.post(PATH,headers=oidc_auth_headers(tenant,actor),json={'data':DATA});assert r.status_code==200,r.text
  out=r.json();assert out['tenant_id']==tenant and out['actor_id']==actor
  assert out['branch_protection_verified'] is False and out['main_mutated'] is False
  assert out['trunk']['tip']=='0000000000000000000000000000000000000003' and out['trunk']['commit_count']==3
  assert out['trunk']['required_checks']['lint']['status']=='missing' and out['trunk']['required_checks_covered'] is False
 h=oidc_auth_headers('a','owner')
 for extra in [{'tenant_id':'b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'b'}]}]:
  assert c.post(PATH,headers=h,json={'data':DATA,**extra}).status_code==403

def test_trunk698_64_refs_accepted_65_refused(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 refs=lambda n:[{'tenant_id':'a','actor_id':'owner','id':str(i)}for i in range(n)]
 assert c.post(PATH,headers=h,json={'data':DATA,'resource_refs':refs(64)}).status_code==200
 assert c.post(PATH,headers=h,json={'data':DATA,'resource_refs':refs(65)}).status_code==422

def test_trunk698_refusals_are_422_and_surrogates_refused(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 assert c.post(PATH,headers=h,json={'data':{}}).status_code==422
 r=c.post(PATH,headers=h,json={});assert r.status_code==422 and isinstance(r.json()['detail'],list)
 r=c.post(PATH,headers=h,json={'data':{**DATA,'trunk':'bad name!'}});assert r.status_code==422 and 'invalid trunk name' in r.json()['detail'],r.text
 r=c.post(PATH,headers=h,json={'data':{**DATA,'extra':1}});assert r.status_code==422,r.text
 for packet in [{'data':['\ud800']},{'data':{'x':'\ud800'}},['\ud800'],{'data':DATA,'\ud800':'x'}]:
  r=c.post(PATH,headers={**h,'Content-Type':'application/json'},content=json.dumps(packet));assert r.status_code==422,r.text
