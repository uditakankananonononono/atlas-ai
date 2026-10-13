from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.mission_build.routes import router
from test_training import fixture


def test_production_auth_required_and_private_owner_scope(monkeypatch,oidc_auth_headers):
    app=FastAPI();app.include_router(router);client=TestClient(app)
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    assert client.post('/mission-build/polynomial',json={'data':{'coefficients':[1,2]}}).status_code==401
    headers=oidc_auth_headers('tenant-z','actor-z')
    r=client.post('/mission-build/polynomial',headers=headers,json={'data':{'coefficients':[1,2],'at':3}})
    assert r.status_code==200 and r.json()['result']['value']=='7'
    assert r.json()['tenant_id']=='tenant-z' and r.json()['actor_id']=='actor-z' and r.json()['external_effects']==[]
    assert client.post('/mission-build/exec',headers=headers,json={'data':{}}).status_code==404
    assert client.post('/mission-build/polynomial',headers=headers,json={'data':{'coefficients':[True]}}).status_code==422


def test_training_consent_and_rights_fail_closed(oidc_auth_headers,monkeypatch):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH",raising=False)
    app=FastAPI();app.include_router(router);client=TestClient(app);headers=oidc_auth_headers()
    corpus,sources=fixture();data={'corpus':corpus,'sources':sources}
    assert client.post('/mission-build/admissions/train',headers=headers,json=data).status_code==403
    data['owner_consented']=True
    r=client.post('/mission-build/admissions/train',headers=headers,json=data)
    assert r.status_code==200 and r.json()['model']['evaluation']['heldout_count']==2 and not r.json()['publishing']
    sources[0]['training_allowed']=False
    assert client.post('/mission-build/admissions/train',headers=headers,json=data).status_code==403


def test_actual_claire_router_mount(oidc_auth_headers,monkeypatch):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH",raising=False)
    from app.modules.m21_claire.routes import router as claire
    app=FastAPI();app.include_router(claire);client=TestClient(app)
    response=client.post('/claire/mission-build/polynomial',headers=oidc_auth_headers(),json={'data':{'coefficients':[0,1],'at':2}})
    assert response.status_code==200 and response.json()['result']['value']=='2'


def test_owner_growth_routes_enforce_actor_from_signed_identity(tmp_path,oidc_auth_headers,monkeypatch):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH",raising=False)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.modules.m21_claire.personalization import ScopedPersonalizationRepository
    from app.mission_build.routes import owner_repository
    from app.auth.context import require_tenant
    from fastapi import Depends
    engine=create_engine(f'sqlite:///{tmp_path}/routes.db',connect_args={'check_same_thread':False});Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine)
    a=ScopedPersonalizationRepository('t','a',sessions);ident=a.add_decision('pick','r','c',[1])
    app=FastAPI();app.include_router(router)
    def repository(tenant=Depends(require_tenant)):
        return ScopedPersonalizationRepository(tenant.tenant_id,tenant.actor_id,sessions)
    app.dependency_overrides[owner_repository]=repository;client=TestClient(app)
    body={'outcome':'worked','lesson':'use again','rating':'better'}
    assert client.post(f'/mission-build/owner/decisions/{ident}/outcomes',headers=oidc_auth_headers('t','b'),json=body).status_code==404
    assert client.get(f'/mission-build/owner/decisions/{ident}',headers=oidc_auth_headers('t','b')).status_code==404
    assert client.post(f'/mission-build/owner/decisions/{ident}/outcomes',headers=oidc_auth_headers('t','a'),json=body).status_code==201
    r=client.get('/mission-build/owner/growth',headers=oidc_auth_headers('t','a'))
    assert r.status_code==200 and r.json()['owner_reported_improvement_rate']==1
