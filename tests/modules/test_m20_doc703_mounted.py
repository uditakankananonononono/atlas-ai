import json
from fastapi.testclient import TestClient
from app.main import app

PATH='/api/v1/api/modules/20/documentation-generation/703/generate'
DATA={'source': 'def f(a, b=1):\n    """doc"""\n'}

def _client(monkeypatch):
 monkeypatch.setenv('ATLAS_ENV','production');return TestClient(app,raise_server_exceptions=False)

def test_doc703_owner_bound_mounted(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch)
 assert c.post(PATH,json={'data':DATA}).status_code==401
 for tenant,actor in [('a','owner'),('b','other')]:
  r=c.post(PATH,headers=oidc_auth_headers(tenant,actor),json={'data':DATA});assert r.status_code==200,r.text
  out=r.json();assert out['tenant_id']==tenant and out['actor_id']==actor
  assert out['status']=='generated' and out['algorithm']=='python_ast_api_documentation_v1'
  assert out['source_sha256']=='587d0c605bcc0b691812fcd91138fed355ce789777f84611e9f1f21d6a93e34c' and out['symbols'][0]['name']=='f'
 h=oidc_auth_headers('a','owner')
 for extra in [{'tenant_id':'b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'b'}]}]:
  assert c.post(PATH,headers=h,json={'data':DATA,**extra}).status_code==403

def test_doc703_64_refs_accepted_65_refused(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 refs=lambda n:[{'tenant_id':'a','actor_id':'owner','id':str(i)}for i in range(n)]
 assert c.post(PATH,headers=h,json={'data':DATA,'resource_refs':refs(64)}).status_code==200
 assert c.post(PATH,headers=h,json={'data':DATA,'resource_refs':refs(65)}).status_code==422

def test_doc703_refusals_are_422_and_surrogates_refused(monkeypatch,oidc_auth_headers):
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 assert c.post(PATH,headers=h,json={'data':{}}).status_code==422
 r=c.post(PATH,headers=h,json={});assert r.status_code==422 and isinstance(r.json()['detail'],list)
 r=c.post(PATH,headers=h,json={'data':{'source':'x\x00'}});assert r.status_code==422 and r.json()['detail']=='source contains NUL',r.text
 r=c.post(PATH,headers=h,json={'data':{'source':'a'*65537}});assert r.status_code==422 and r.json()['detail']=='source exceeds 65536 characters',r.text
 for packet in [{'data':['\ud800']},{'data':{'x':'\ud800'}},['\ud800'],{'data':DATA,'\ud800':'x'}]:
  r=c.post(PATH,headers={**h,'Content-Type':'application/json'},content=json.dumps(packet));assert r.status_code==422,r.text

def test_doc703_resource_limit_refuses_422(monkeypatch,oidc_auth_headers):
 from app.modules.m20_general_cognitive_worker import doc703_routes as routes
 c=_client(monkeypatch);h=oidc_auth_headers('a','owner')
 for exc in [RecursionError,MemoryError]:
  def fail(*a,**k):raise exc()
  monkeypatch.setattr(routes,'generate',fail)
  r=c.post(PATH,headers=h,json={'data':DATA});assert r.status_code==422 and r.json()['detail']=='doc703 parser resource limit; generation refused',r.text
