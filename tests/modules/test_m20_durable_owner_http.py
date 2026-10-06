from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from app.main import app
from app.modules.m20_general_cognitive_worker import runtime_routes as routes
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.schemas import SemanticFact
BASE='/api/v1/api/modules/20/api/modules/20/runtime'


def test_signed_runtime_owner_cannot_read_other_tenant_repo(monkeypatch,tmp_path,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production')
 repo=GCWRepository(create_engine('sqlite:///'+str(tmp_path/'canary.db')),tenant_id='a');repo.create_schema()
 repo.save_fact(SemanticFact(content='durable-private-canary'))
 monkeypatch.setattr(routes,'_runtimes',{})
 routes.bind_runtime(GCWRuntime(repo),tenant_id='a')
 r=TestClient(app).get(BASE+'/memory/facts',headers=oidc_auth_headers('b'))
 assert r.status_code in (404,503) or not any(f['content']=='durable-private-canary' for f in r.json())


def test_shared_db_signed_owners_are_isolated_and_wrong_binding_rejected(monkeypatch,tmp_path,oidc_auth_headers):
 import pytest
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_runtimes',{})
 engine=create_engine('sqlite:///'+str(tmp_path/'shared.db'))
 ra=GCWRepository(engine,tenant_id='a');ra.create_schema();rb=GCWRepository(engine,tenant_id='b')
 ra.save_fact(SemanticFact(content='a-only'));rb.save_fact(SemanticFact(content='b-only'))
 a=GCWRuntime(ra);b=GCWRuntime(rb)
 with pytest.raises(ValueError,match='repository tenant'):routes.bind_runtime(a,tenant_id='b')
 routes.bind_runtime(a);routes.bind_runtime(b)
 c=TestClient(app);ha=oidc_auth_headers('a');hb=oidc_auth_headers('b')
 assert [r['content'] for r in c.get(BASE+'/memory/facts',headers=ha).json()]==['a-only']
 assert [r['content'] for r in c.get(BASE+'/memory/facts',headers=hb).json()]==['b-only']
 r=c.post(BASE+'/tasks',headers=ha,json={'goal':'a-only-goal','run_immediately':False})
 assert r.status_code==201;task=r.json()['task_id']
 assert c.get(BASE+'/tasks/'+task,headers=hb).status_code==404
 assert c.post(BASE+'/tasks/'+task+'/step',headers=hb,json={}).status_code==404
 assert c.post(BASE+'/tasks/'+task+'/close',headers=hb).status_code==404
 assert c.get(BASE+'/tasks',headers=hb).json()==[]
 assert c.get(BASE+'/tasks/'+task,headers=ha).status_code==200
 assert rb.load_task(task) is None
