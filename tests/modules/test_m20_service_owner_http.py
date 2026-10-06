from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker import routes
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
BASE='/api/v1/api/modules/20'


def test_configured_service_must_not_share_fact_between_signed_owners(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production')
 monkeypatch.setattr(routes,'_services',{})
 monkeypatch.setattr(routes,'_service',None)
 routes.bind_service(CognitiveWorkerService(),tenant_id='owner-a')
 routes.bind_service(CognitiveWorkerService(),tenant_id='owner-b')
 c=TestClient(app)
 a=oidc_auth_headers('owner-a');b=oidc_auth_headers('owner-b')
 assert c.post(BASE+'/memory/facts',headers=a,json={'content':'ownerasecretcanary'}).status_code==201
 own=c.get(BASE+'/memory/facts',headers=a,params={'query':'ownerasecretcanary'})
 other=c.get(BASE+'/memory/facts',headers=b,params={'query':'ownerasecretcanary'})
 assert own.status_code==200 and any('ownerasecretcanary' in r['content'] for r in own.json())
 assert other.status_code in (404,503) or not any('ownerasecretcanary' in r['content'] for r in other.json())


def test_same_mutable_service_cannot_be_bound_across_owners(monkeypatch):
 import pytest
 monkeypatch.setattr(routes,'_services',{})
 s=CognitiveWorkerService();routes.bind_service(s,tenant_id='a')
 with pytest.raises(ValueError,match='another tenant'):routes.bind_service(s,tenant_id='b')


def test_unconfigured_owner_fails_closed_not_local_fallback(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_services',{})
 monkeypatch.setattr(routes,'_service',CognitiveWorkerService())
 c=TestClient(app)
 assert c.get(BASE+'/tasks',headers=oidc_auth_headers('other')).status_code==503


def test_separate_owner_tasks_ingestion_traces_standup(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_services',{})
 for owner in ('a','b'):routes.bind_service(CognitiveWorkerService(),tenant_id=owner)
 c=TestClient(app);a=oidc_auth_headers('a');b=oidc_auth_headers('b')
 r=c.post(BASE+'/goals',headers=a,json={'goal':'ownerasecretgoal','run_immediately':False})
 assert r.status_code==201;task=r.json()['task_id']
 assert any(t['id']==task for t in c.get(BASE+'/tasks',headers=a).json())
 assert not c.get(BASE+'/tasks',headers=b).json()
 assert c.get(BASE+'/tasks/'+task,headers=b).status_code==404
 assert c.post(BASE+'/ingest/text',headers=b,json={'text':'cross-context','context_id':task}).status_code==404
 assert c.post(BASE+'/ingest/email',headers=b,json={'subject':'x','body':'y','sender':'z','context_id':task}).status_code==404
 assert c.post(BASE+'/tasks/'+task+'/retrospective',headers=b,json={}).status_code==404
 assert c.post(BASE+'/tasks/'+task+'/resume',headers=b,json={'node_id':'x','approved':True}).status_code==404
 assert c.post(BASE+'/ingest/text',headers=a,json={'text':'a-private-input','external_id':'shared-id'}).json()['ingested']
 assert c.post(BASE+'/ingest/text',headers=b,json={'text':'b-private-input','external_id':'shared-id'}).json()['ingested']
 assert 'ownerasecretgoal' not in c.get(BASE+'/standup',headers=b).text
 assert c.get(BASE+'/traces',headers=b,params={'task_id':task}).json()==[]


def test_real_oidc_local_tenant_cannot_access_default_service(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production')
 assert TestClient(app).get(BASE+'/tasks',headers=oidc_auth_headers('local')).status_code==403
