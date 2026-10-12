"""Mounted opt-in default GCW reachability; no manual binding or service override."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker import routes

BASE='/api/v1/api/modules/20'

@pytest.fixture
def fresh_gcw(monkeypatch):
    monkeypatch.setenv('ATLAS_ENV','production')
    monkeypatch.setenv('ATLAS_GCW_AUTOBIND','1')
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    monkeypatch.setattr(routes,'_services',{})
    monkeypatch.setattr(routes,'_service',None)
    return TestClient(app,raise_server_exceptions=False)

@pytest.mark.parametrize('method,path,data,status',[
    ('get','/tasks',None,200),('get','/tools',None,200),('get','/skills',None,200),
    ('get','/health',None,200),('get','/standup',None,200),('get','/traces',None,200),
    ('get','/memory/facts',None,400),('get','/memory/episodes',None,400),
    ('get','/meta/calibration/curve',None,200),('get','/meta/world-models',None,200),
    ('post','/meta/load-allocation',None,200),('get','/tasks/absent',None,404),
])
def test_autobind_meta_service_reachable(fresh_gcw,oidc_auth_headers,method,path,data,status):
    response=fresh_gcw.request(method,BASE+path,headers=oidc_auth_headers('gcw-pin-owner','owner'),json=data)
    assert response.status_code==status,response.text
    if path in ('/memory/facts','/memory/episodes'):
        assert response.json()['detail']=='query required'
    assert 'gcw-pin-owner' in routes._services


def test_autobind_signed_owners_task_isolation(fresh_gcw,oidc_auth_headers):
    a,b=oidc_auth_headers('gcw-a','owner'),oidc_auth_headers('gcw-b','other')
    created=fresh_gcw.post(BASE+'/goals',headers=a,json={'goal':'gcw-a-private-goal','run_immediately':False})
    assert created.status_code==201,created.text
    task=created.json()['task_id']
    own=fresh_gcw.get(BASE+'/tasks',headers=a)
    other=fresh_gcw.get(BASE+'/tasks',headers=b)
    assert own.status_code==other.status_code==200
    assert any(row['id']==task for row in own.json())
    assert other.json()==[]
    assert routes._services['gcw-a'] is not routes._services['gcw-b']
    assert fresh_gcw.get(BASE+'/tasks/'+task,headers=b).status_code==404


def test_autobind_missing_auth_fail_closed(fresh_gcw):
    assert fresh_gcw.get(BASE+'/meta/world-models').status_code==401
    assert routes._services=={}


def test_autobind_production_dev_flag_not_bypass(fresh_gcw,monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','1')
    assert fresh_gcw.get(BASE+'/tasks').status_code==401
    assert routes._services=={}


def test_autobind_real_local_identity_refused(fresh_gcw,oidc_auth_headers):
    response=fresh_gcw.get(BASE+'/tasks',headers=oidc_auth_headers('local','owner'))
    assert response.status_code==403
    assert response.json()['detail']=='local is reserved for insecure development, not an authenticated tenant'
    assert routes._services=={}


def test_autobind_development_no_auth_does_not_create_local(fresh_gcw,monkeypatch):
    monkeypatch.setenv('ATLAS_ENV','development')
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','1')
    response=fresh_gcw.get(BASE+'/tasks')
    assert response.status_code==503
    assert routes._services=={}


def test_autobind_flag_off_preserves_unbound_refusal(fresh_gcw,monkeypatch,oidc_auth_headers):
    monkeypatch.setenv('ATLAS_GCW_AUTOBIND','0')
    response=fresh_gcw.get(BASE+'/tasks',headers=oidc_auth_headers('gcw-pin-owner'))
    assert response.status_code==503
    assert routes._services=={}


def test_autobind_default_mode_all_probes_preserve_503(fresh_gcw,monkeypatch,oidc_auth_headers):
    monkeypatch.delenv('ATLAS_GCW_AUTOBIND')
    headers=oidc_auth_headers('default-gcw')
    for path in ['/tasks','/health','/meta/calibration/curve','/meta/world-models']:
        response=fresh_gcw.get(BASE+path,headers=headers)
        assert response.status_code==503,response.text
        assert response.json()['detail']=='GCW service not bound for authenticated tenant'
    assert routes._services=={}


def test_autobind_dev_header_tenant_and_explicit_precedence(fresh_gcw,monkeypatch):
    from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
    monkeypatch.setenv('ATLAS_ENV','development')
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','1')
    header={'X-Atlas-Tenant':'dev-gcw','X-Atlas-Actor':'dev-owner'}
    response=fresh_gcw.get(BASE+'/tasks',headers=header)
    assert response.status_code==200,response.text
    assert 'dev-gcw' in routes._services and 'local' not in routes._services
    explicit=CognitiveWorkerService()
    routes.bind_service(explicit,tenant_id='dev-gcw')
    assert fresh_gcw.get(BASE+'/meta/world-models',headers=header).status_code==200
    assert routes._services['dev-gcw'] is explicit
    assert fresh_gcw.get(BASE+'/tasks',headers={'X-Atlas-Tenant':'local'}).status_code==503
    assert 'local' not in routes._services
