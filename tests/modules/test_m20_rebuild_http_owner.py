from fastapi.testclient import TestClient
from app.main import app

BASE='/api/v1/api/modules/20'
OPT=BASE+'/optimization-story-235-280'
LEARN=BASE+'/learning-reasoning-810-859'


def test_production_unauthenticated_cannot_run_rebuilt_computation(monkeypatch):
 monkeypatch.setenv('ATLAS_ENV','production')
 c=TestClient(app)
 assert c.post(OPT+'/admm',json={'payload':{}}).status_code==401
 assert c.post(LEARN+'/metacognition',json={'payload':{}}).status_code==401


def test_signed_owner_identity_binds_numerical_result_and_ignores_forged_headers(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production')
 c=TestClient(app);headers={**oidc_auth_headers('owner-a','actor-a'),'X-Atlas-Tenant':'owner-b','X-Atlas-Actor':'actor-b'}
 r=c.post(OPT+'/admm',headers=headers,json={'payload':{'source':{'title':'input','url':'https://example.org'},'quadratic':[[1]],'linear':[2],'l1_penalty':.2}})
 assert r.status_code==200
 assert r.json()['tenant_id']=='owner-a' and r.json()['actor_id']=='actor-a'
 assert abs(r.json()['result']['solution'][0]-1.8)<1e-5


def test_cross_owner_and_cross_actor_payloads_block_before_solver(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);headers=oidc_auth_headers('owner-a','actor-a')
 for payload in [{'tenant_id':'owner-b'},{'actor_id':'actor-b'},{'resource_refs':[{'tenant_id':'owner-b','id':'private'}]},
                 {'resource_refs':[{'tenant_id':'owner-a','actor_id':'actor-b','id':'private'}]}]:
  assert c.post(OPT+'/admm',headers=headers,json={'payload':payload}).status_code==403
  assert c.post(LEARN+'/metacognition',headers=headers,json={'payload':payload}).status_code==403


def test_real_signed_deduction_route_returns_countermodel_not_claimed_validity(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app)
 r=c.post(LEARN+'/deductive_reasoning',headers=oidc_auth_headers('owner-a'),json={'payload':{'source':{'title':'input','url':'https://example.org'},'formulas':['Q',{'implies':['P','Q']}],'conclusion':'P','validity':True}})
 assert r.status_code==200 and r.json()['tenant_id']=='owner-a'
 assert r.json()['result']['deduction']['countermodel']=={'P':False,'Q':True}


def test_malformed_numeric_and_unknown_resource_shapes_return_client_errors(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);headers=oidc_auth_headers('owner-a')
 for payload in [{'quadratic':'bad','linear':[1],'l1_penalty':1},{'resource_refs':['not-object']},{'resource_refs':{}}]:
  assert c.post(OPT+'/admm',headers=headers,json={'payload':payload}).status_code==422


def test_two_signed_owners_get_no_cross_owner_state(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app)
 for owner,linear in [('owner-a',1.),('owner-b',4.),('owner-a',1.)]:
  r=c.post(OPT+'/admm',headers=oidc_auth_headers(owner),json={'payload':{'source':{'title':'input','url':'https://example.org'},'quadratic':[[1]],'linear':[linear],'l1_penalty':.2}})
  assert r.status_code==200 and r.json()['tenant_id']==owner
  assert abs(r.json()['result']['solution'][0]-(linear-.2))<1e-5
