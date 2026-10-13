import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_social_scan import m, payload, AS_OF
from s21.routes import make_router
from app.auth.context import TenantContext, require_tenant


def client():
    app = FastAPI()
    app.include_router(make_router())
    return app, TestClient(app)


def body():
    return {'connector':'normalized_json','payload':payload().decode(),'as_of':AS_OF}


def test_route_roundtrip_and_tenant_boundary():
    app,c=client()
    app.dependency_overrides[require_tenant]=lambda:TenantContext('a','owner')
    r=c.post('/api/v1/c33/self-feed/run',json=body())
    assert r.status_code==200
    report_id=r.json()['report_id']
    assert c.get('/api/v1/c33/self-feed/report',params={'report_id':report_id}).json()==r.json()
    app.dependency_overrides[require_tenant]=lambda:TenantContext('b','owner')
    assert c.get('/api/v1/c33/self-feed/report',params={'report_id':report_id}).status_code==404


def test_unauthed_production_and_extra_fields(monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    monkeypatch.setenv('ATLAS_ENV','production')
    app,c=client()
    assert c.post('/api/v1/c33/self-feed/run',json=body()).status_code==401
    assert c.get('/api/v1/c33/self-feed/report',params={'report_id':'x'}).status_code==401
    app.dependency_overrides[require_tenant]=lambda:TenantContext('a','owner')
    for extra in [{'tenant_id':'b'},{'action':'post'},{'token':'secret'}]:
        assert c.post('/api/v1/c33/self-feed/run',json={**body(),**extra}).status_code==422
    assert c.post('/api/v1/c33/self-feed/run',json={**body(),'payload':'bad'}).json()['detail']=='SOCIAL_REFUSED_SCHEMA'


def test_real_signed_tenant_path(oidc_auth_headers,monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    monkeypatch.setenv('ATLAS_ENV','production')
    app,c=client()
    r=c.post('/api/v1/c33/self-feed/run',json=body(),headers=oidc_auth_headers(tenant='a'))
    assert r.status_code==200
    assert c.get('/api/v1/c33/self-feed/report',params={'report_id':r.json()['report_id']},headers=oidc_auth_headers(tenant='b')).status_code==404


def test_payload_surrogate_fails_as_422():
    app,c=client()
    app.dependency_overrides[require_tenant]=lambda:TenantContext('a','owner')
    assert c.post('/api/v1/c33/self-feed/run',content=json.dumps({**body(),'payload':'\ud800'}),headers={'Content-Type':'application/json'}).status_code==422
