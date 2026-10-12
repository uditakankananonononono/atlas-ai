import json
from fastapi.testclient import TestClient
from app.main import app

PATH='/api/v1/api/modules/20/release-notes/702/plan'
DATA={'version': '1.0', 'audience': 'users', 'changes': [{'id': 'c1', 'description': 'd', 'user_visible': True, 'breaking': False}], 'upgrade_steps': [], 'known_issues': []}

def _client(monkeypatch):
 monkeypatch.setenv('ATLAS_ENV','production');return TestClient(app,raise_server_exceptions=False)

def test_release702_owner_bound_mounted(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch)
 assert c.post(PATH,json={'data':DATA}).status_code==401
 for tenant,actor in [('a','owner'),('b','other')]:
  r=c.post(PATH,headers=oidc_auth_headers(tenant,actor),json={'data':DATA});assert r.status_code==200,r.text
  out=r.json();assert out['tenant_id']==tenant and out['actor_id']==actor
  assert out['status']=='draft_only' and out['published'] is False and out['release_authorized'] is False
  assert out['highlights']==[{'id':'c1','description':'d'}] and out['generated_from_change_ids']==['c1']
  assert out['snapshot_sha256']=='1228b033476074e9e3cb3909a18f1cf456509263b206b96743b2307f8486e450'
 h=oidc_auth_headers('a','owner')
 for extra in [{'tenant_id':'b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'b'}]}]:
  assert c.post(PATH,headers=h,json={'data':DATA,**extra}).status_code==403

def test_release702_64_refs_accepted_65_refused(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 refs=lambda n:[{'tenant_id':'a','actor_id':'owner','id':str(i)}for i in range(n)]
 assert c.post(PATH,headers=h,json={'data':DATA,'resource_refs':refs(64)}).status_code==200
 assert c.post(PATH,headers=h,json={'data':DATA,'resource_refs':refs(65)}).status_code==422

def test_release702_refusals_are_422_and_surrogates_refused(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 assert c.post(PATH,headers=h,json={'data':{}}).status_code==422
 r=c.post(PATH,headers=h,json={});assert r.status_code==422 and isinstance(r.json()['detail'],list)
 r=c.post(PATH,headers=h,json={'data':{**DATA,'extra':1}});assert r.status_code==422 and r.json()['detail']=='RELEAS702: request fields invalid',r.text
 d=dict(DATA,changes=[DATA['changes'][0],DATA['changes'][0]])
 r=c.post(PATH,headers=h,json={'data':d});assert r.status_code==422 and r.json()['detail']=='RELEAS702: duplicate change id',r.text
 for packet in [{'data':['\ud800']},{'data':{'x':'\ud800'}},['\ud800'],{'data':DATA,'\ud800':'x'}]:
  r=c.post(PATH,headers={**h,'Content-Type':'application/json'},content=json.dumps(packet));assert r.status_code==422,r.text
