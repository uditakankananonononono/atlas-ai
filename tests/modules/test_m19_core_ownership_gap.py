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
 assert items[0][0].payload['tenant_id']=='tenant-a'
 assert items[0][1]=='tenant-a'
 # No deployment occurs; fake approval sink only. Fixture identity isn't production auth proof.
