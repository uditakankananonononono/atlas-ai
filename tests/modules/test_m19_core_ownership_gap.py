"""Isolated HTTP reproduction, fake model only, no preview/deploy."""
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m19_idea_incubator.routes import router,get_service
from app.modules.m19_idea_incubator.service import Service
from app.auth.context import require_tenant


def test_core_intake_requires_authenticated_tenant_before_generator(monkeypatch):
 monkeypatch.setenv("ATLAS_DEV_NO_AUTH","0")
 calls=[]
 async def generate(*args):
  calls.append(args)
  return 'fixture',json.dumps({'problem':['fixture'],'customer_segments':['fixture'],'unique_value_proposition':'fixture','solution':['fixture'],'channels':[],'revenue_streams':[],'cost_structure':[],'key_metrics':[],'riskiest_assumptions':['unverified']})
 class Approvals:
  def put(self,*args,**kwargs):raise AssertionError('no effects allowed')
 app=FastAPI();app.include_router(router)
 app.dependency_overrides[get_service]=lambda:Service(generate=generate,approval_store=Approvals())
 with TestClient(app) as client:
  response=client.post('/idea-incubator/ideas',json={'one_liner':'fixture idea'})
 assert response.status_code in {401,403}
 assert calls==[]


def test_core_http_scopes_existing_run_get_preview_and_package_by_tenant():
 from types import SimpleNamespace
 from fastapi import Header
 from app.modules.m19_idea_incubator.schemas import IntakeIn
 import asyncio
 calls=[];items=[]
 async def generate(*args):
  calls.append(args)
  if args[0].startswith('Return viability package'):
   return 'fixture',json.dumps({'executive_summary':'fixture package','recommendation':'test only','recommendation_confidence':.2,'market_claims':[],'technical_feasibility':[],'prototype_artifacts':[],'unresolved_risks':['unverified'],'next_experiments':['review']})
  return 'fixture',json.dumps({'problem':['fixture'],'customer_segments':['fixture'],'unique_value_proposition':'fixture','solution':['fixture'],'channels':[],'revenue_streams':[],'cost_structure':[],'key_metrics':[],'riskiest_assumptions':['unverified']})
 class Approvals:
  def put(self,item,*,user_id):items.append((item,user_id));return item
 svc=Service(generate=generate,approval_store=Approvals())
 run=asyncio.run(svc.intake(IntakeIn(one_liner='fixture idea'),tenant_id='tenant-a'))
 app=FastAPI();app.include_router(router)
 app.dependency_overrides[get_service]=lambda:svc
 def fixture_tenant(x_fixture_tenant:str=Header()):return SimpleNamespace(tenant_id=x_fixture_tenant)
 app.dependency_overrides[require_tenant]=fixture_tenant
 with TestClient(app) as client:
  for path,body in [(f'/idea-incubator/ideas/{run.id}',None),(f'/idea-incubator/ideas/{run.id}/preview',{'artifacts':['fixture'],'estimated_cost':0}),('/idea-incubator/packages',{'run_id':run.id})]:
   response=client.get(path,headers={'x-fixture-tenant':'tenant-b'}) if body is None else client.post(path,headers={'x-fixture-tenant':'tenant-b'},json=body)
   assert response.status_code==404
  assert len(calls)==1 and items==[]
  assert client.get(f'/idea-incubator/ideas/{run.id}',headers={'x-fixture-tenant':'tenant-a'}).status_code==200
  response=client.post(f'/idea-incubator/ideas/{run.id}/preview',headers={'x-fixture-tenant':'tenant-a'},json={'artifacts':['fixture'],'estimated_cost':0})
  assert response.status_code==201
  response=client.post('/idea-incubator/packages',headers={'x-fixture-tenant':'tenant-a'},json={'run_id':run.id})
  assert response.status_code==200 and response.json()['executive_summary']=='fixture package'
 assert items[0][0].payload['tenant_id']=='tenant-a'
 assert items[0][1]=='tenant-a'
 # No deployment occurs; fake approval sink only. Fixture identity isn't production auth proof.


@pytest.mark.parametrize('method,path,body',[('get','/idea-incubator/ideas/missing',None),('post','/idea-incubator/ideas/missing/preview',{'artifacts':[],'estimated_cost':0}),('post','/idea-incubator/packages',{'run_id':'missing'})])
def test_other_core_routes_reject_missing_credentials_before_service(monkeypatch,method,path,body):
 monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0')
 class NoCalls:
  def get(self,*args,**kwargs):raise AssertionError('service must not run')
  def request_preview(self,*args,**kwargs):raise AssertionError('service must not run')
  async def package(self,*args,**kwargs):raise AssertionError('service must not run')
 app=FastAPI();app.include_router(router);app.dependency_overrides[get_service]=lambda:NoCalls()
 with TestClient(app) as client:
  response=client.request(method,path,json=body) if body is not None else client.request(method,path)
 assert response.status_code==401
