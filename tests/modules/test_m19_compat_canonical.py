from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.modules.m19_idea_incubator.routes import router,get_ledger
from app.modules.m19_idea_incubator.lane_router import get_service
from app.modules.m19_idea_incubator.repository import SqlIdeaRepository
from app.modules.m19_idea_incubator.ledger import LedgerService
from app.auth.context import require_tenant
from fastapi import Depends


def test_compat_routes_authenticate_and_share_canonical_durable_ledger(oidc_auth_headers,monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    app=FastAPI();app.include_router(router)
    def ledger(t=Depends(require_tenant)):return LedgerService(SqlIdeaRepository(t.tenant_id,sessions),t.actor_id)
    app.dependency_overrides[get_ledger]=ledger;app.dependency_overrides[get_service]=ledger;c=TestClient(app);path='/idea-incubator/compat/ideas'
    assert c.post(path,json={}).status_code in (401,403)
    h=oidc_auth_headers('tenant-a','owner-a');data={'title':'Idea','problem':'Problem','proposed_solution':'Solution','owner_id':'forged'}
    result=c.post(path,json=data,headers=h);assert result.status_code==201,result.text
    idea=result.json();assert idea['owner_id']=='owner-a'
    canonical=c.get('/idea-incubator/portfolio/ideas/'+idea['id'],headers=h)
    assert canonical.status_code==200 and canonical.json()['idea']['title']=='Idea'
    assert c.get(path+'/'+idea['id'],headers=oidc_auth_headers('tenant-b','owner-b')).status_code==404
    payload={'to_stage':'discovery','rationale':'Investigate','actor_id':'forged','expected_version':1}
    result=c.post(path+'/'+idea['id']+'/decisions',json=payload,headers=h)
    assert result.status_code==201 and result.json()['actor_id']=='owner-a'
    assert c.post(path+'/'+idea['id']+'/decisions',json=payload,headers=h).status_code==409
    # Rebuilt service/session continues reading exactly the canonical rows.
    restart=LedgerService(SqlIdeaRepository('tenant-a',sessions),'owner-a')
    assert restart.dossier(idea['id']).idea.version==2
    assert len(restart.dossier(idea['id']).decisions)==1

def test_all_compat_effects_reject_other_tenant_and_forged_actor(oidc_auth_headers,monkeypatch):
    from app.modules.m19_idea_incubator.lane_router import get_service
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    app=FastAPI();app.include_router(router)
    def ledger(t=Depends(require_tenant)):return LedgerService(SqlIdeaRepository(t.tenant_id,sessions),t.actor_id)
    app.dependency_overrides[get_ledger]=ledger;app.dependency_overrides[get_service]=ledger;c=TestClient(app);h=oidc_auth_headers('a','owner');other=oidc_auth_headers('b','other')
    path='/idea-incubator/api/modules/19/ideas'
    made=c.post(path,json={'title':'Idea','problem':'P','proposed_solution':'S','owner_id':'spoof','metadata':{'captured_by':'spoof'}},headers=h)
    assert made.status_code==201 and made.json()['owner_id']=='owner'
    root=path+'/'+made.json()['id']
    evidence={'kind':'interview','claim':'Demand','source':'interview-1','polarity':'supports','strength':.4,'confidence':.5}
    feasibility={name:{'score':80,'confidence':.8} for name in ('desirability','technical','viability','strategic_fit','compliance')}
    experiment={'name':'Interview','hypothesis':'Demand','method':'Ask','metric':'signups','target':3}
    for suffix,payload in [('/evidence',evidence),('/feasibility-tests',feasibility),('/experiments',experiment),('/decisions',{'to_stage':'discovery','rationale':'Inspect','actor_id':'spoof'})]:
        assert c.post(root+suffix,json=payload,headers=other).status_code==404
        assert c.post(root+suffix,json=payload).status_code in (401,403)
    assert c.get(root+'/evidence/summary',headers=other).status_code==404
    assert c.get(path,headers=other).json()==[]
    assert c.post(root+'/evidence',json=evidence,headers=h).status_code==201
    assert c.post(root+'/feasibility-tests',json=feasibility,headers=h).status_code==201
    exp=c.post(root+'/experiments',json=experiment,headers=h).json()
    assert c.patch(root+'/experiments/'+exp['id'],json={'status':'running'},headers=other).status_code==404
    assert c.patch(root+'/experiments/'+exp['id'],json={'status':'running'},headers=h).status_code==200
    assert c.patch(root+'/experiments/'+exp['id'],json={'status':'succeeded','observed_value':4},headers=h).status_code==200
    assert c.patch(root+'/experiments/'+exp['id'],json={'status':'failed','observed_value':0},headers=h).status_code==409
    canonical=c.get('/idea-incubator/portfolio/ideas/'+made.json()['id'],headers=h).json()
    assert len(canonical['evidence'])==len(canonical['feasibility_tests'])==len(canonical['experiments'])==1
