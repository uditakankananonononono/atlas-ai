import json
from fastapi.testclient import TestClient
from app.main import app

PATH='/api/v1/api/modules/20/semantic-versioning/700/analyze'
DATA={'current_version': '1.2.3', 'baseline_snapshot': {'symbols': [{'name': 'f', 'kind': 'function', 'signature': {'params': [{'name': 'a', 'kind': 'positional', 'required': True, 'type': 'int'}], 'returns': 'int'}}]}, 'candidate_snapshot': {'symbols': [{'name': 'f', 'kind': 'function', 'signature': {'params': [{'name': 'a', 'kind': 'positional', 'required': True, 'type': 'int'}], 'returns': 'int'}}, {'name': 'g', 'kind': 'function', 'signature': {'params': [], 'returns': 'int'}}]}}

def _client(monkeypatch):
 monkeypatch.setenv('ATLAS_ENV','production');return TestClient(app,raise_server_exceptions=False)

def test_semver700_owner_bound_mounted(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch)
 assert c.post(PATH,json={'data':DATA}).status_code==401
 for tenant,actor in [('a','owner'),('b','other')]:
  r=c.post(PATH,headers=oidc_auth_headers(tenant,actor),json={'data':DATA});assert r.status_code==200,r.text
  out=r.json();assert out['tenant_id']==tenant and out['actor_id']==actor
  assert out['diff']=='additive' and out['bump']=='minor' and out['next_version']=='1.3.0'
  assert out['scope']=='declared-api-shapes-only' and out['human_review_required'] is True
 h=oidc_auth_headers('a','owner')
 for extra in [{'tenant_id':'b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'b'}]}]:
  assert c.post(PATH,headers=h,json={'data':DATA,**extra}).status_code==403

def test_semver700_64_refs_accepted_65_refused(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 refs=lambda n:[{'tenant_id':'a','actor_id':'owner','id':str(i)}for i in range(n)]
 assert c.post(PATH,headers=h,json={'data':DATA,'resource_refs':refs(64)}).status_code==200
 assert c.post(PATH,headers=h,json={'data':DATA,'resource_refs':refs(65)}).status_code==422

def test_semver700_refusals_are_422_and_surrogates_refused(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 assert c.post(PATH,headers=h,json={'data':{}}).status_code==422
 r=c.post(PATH,headers=h,json={});assert r.status_code==422 and isinstance(r.json()['detail'],list)
 r=c.post(PATH,headers=h,json={'data':{**DATA,'current_version':'01.2.3'}});assert r.status_code==422 and r.json()['detail'].startswith('E_'),r.text
 d=dict(DATA);d.pop('candidate_snapshot')
 r=c.post(PATH,headers=h,json={'data':d});assert r.status_code==422 and r.json()['detail']=='E_SCHEMA: missing field candidate_snapshot',r.text
 for packet in [{'data':['\ud800']},{'data':{'x':'\ud800'}},['\ud800'],{'data':DATA,'\ud800':'x'}]:
  r=c.post(PATH,headers={**h,'Content-Type':'application/json'},content=json.dumps(packet));assert r.status_code==422,r.text
