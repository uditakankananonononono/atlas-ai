"""Isolated HTTP reproduction, fake model only, no preview/deploy."""
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m19_idea_incubator.routes import router,get_service
from app.modules.m19_idea_incubator.service import Service
from app.auth.context import require_tenant


@pytest.mark.xfail(strict=True,reason='core M19 intake omits tenant authentication dependency')
def test_core_intake_requires_authenticated_tenant_before_generator():
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
