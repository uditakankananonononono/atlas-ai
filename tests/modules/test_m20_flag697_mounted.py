import json
from fastapi.testclient import TestClient
from app.main import app

PATH='/api/v1/api/modules/20/feature-flags/697/evaluate'
DATA={'context_schema': {'x': 'int'}, 'evaluation_context': {'x': 1}, 'flags': [{'name': 'beta', 'source_id': 'flag-src', 'default': False, 'rules': [{'id': 'r1', 'source_id': 'rule-src', 'priority': 1, 'value': True, 'condition': {'op': 'eq', 'field': 'x', 'value': 1}}]}]}

def _client(monkeypatch):
 monkeypatch.setenv('ATLAS_ENV','production');return TestClient(app,raise_server_exceptions=False)

def test_flag697_owner_bound_mounted(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch)
 assert c.post(PATH,json={'data':DATA}).status_code==401
 for tenant,actor in [('a','owner'),('b','other')]:
  r=c.post(PATH,headers=oidc_auth_headers(tenant,actor),json={'data':DATA});assert r.status_code==200,r.text
  out=r.json();assert out['tenant_id']==tenant and out['actor_id']==actor
  assert out['status']=='supplied_flag_rules_evaluated' and out['release_authorized'] is False and out['evidence_verified'] is False
  assert out['flags'][0]['value'] is True and out['flags'][0]['matched_rule_id']=='r1'
 h=oidc_auth_headers('a','owner')
 for extra in [{'tenant_id':'b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'b'}]}]:
  assert c.post(PATH,headers=h,json={'data':DATA,**extra}).status_code==403

def test_flag697_64_refs_accepted_65_refused(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 refs=lambda n:[{'tenant_id':'a','actor_id':'owner','id':str(i)}for i in range(n)]
 assert c.post(PATH,headers=h,json={'data':DATA,'resource_refs':refs(64)}).status_code==200
 assert c.post(PATH,headers=h,json={'data':DATA,'resource_refs':refs(65)}).status_code==422

def test_flag697_refusals_are_422_and_surrogates_refused(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 assert c.post(PATH,headers=h,json={'data':{}}).status_code==422
 r=c.post(PATH,headers=h,json={});assert r.status_code==422 and isinstance(r.json()['detail'],list)
 bad={**DATA,'flags':[{**DATA['flags'][0],'default':'x'}]}
 r=c.post(PATH,headers=h,json={'data':bad});assert r.status_code==422 and r.json()['detail'].startswith('FLAG697_'),r.text
 r=c.post(PATH,headers=h,json={'data':{**DATA,'extra':1}});assert r.status_code==422 and r.json()['detail'].startswith('FLAG697_'),r.text
 for packet in [{'data':['\ud800']},{'data':{'x':'\ud800'}},['\ud800'],{'data':DATA,'\ud800':'x'}]:
  r=c.post(PATH,headers={**h,'Content-Type':'application/json'},content=json.dumps(packet));assert r.status_code==422,r.text
