import unittest,tempfile,pathlib,json,asyncio
from unittest.mock import patch
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m14_project_builder import routes,sql_repository as R,artifacts
from app.modules.m14_project_builder.errors import *
from app.modules.m14_project_builder.service import Service
from app.modules.m14_project_builder.schemas import CreateProjectRequest,ProjectPlan
class IndependentM14(unittest.TestCase):
 def test_actual_duplicate_design_repo_maps409(self):
  with tempfile.TemporaryDirectory()as td:
   e=create_engine('sqlite:///'+str(pathlib.Path(td)/'db'));R.Base.metadata.create_all(e)
   repo=R.SqlProjectRepository.__new__(R.SqlProjectRepository);repo.tenant_id='t';repo.sessions=sessionmaker(e,expire_on_commit=False)
   s=Service(None,repository=repo);p=s.create('t',CreateProjectRequest(goal='build useful system'))
   a=FastAPI();a.include_router(routes.router);a.dependency_overrides[routes.get_service]=lambda:s;a.dependency_overrides[routes.tenant]=lambda:'t'
   c=TestClient(a,raise_server_exceptions=False)
   with patch.object(artifacts,'uuid4',return_value='fixed-artifact'):
    x=c.post(f'/project-builder/projects/{p.id}/designs',json={'kind':'system_architecture','context':{}})
    y=c.post(f'/project-builder/projects/{p.id}/designs',json={'kind':'system_architecture','context':{}})
   self.assertEqual(x.status_code,201,x.text);self.assertEqual((y.status_code,y.json()['detail']),(409,{'state':'artifact_conflict'}));self.assertEqual(len(repo.list_artifacts(p.id)),1);e.dispose()
 def test_invalid_dag_plan_before_mutation(self):
  async def g(*args):return 'fixture',json.dumps({'tasks':[{'id':'a','title':'hello','objective':'do work','agent_kind':'coder','dependencies':['missing']}]})
  s=Service(None,generate_fn=g);p=s.create('t',CreateProjectRequest(goal='build something'));before=p.model_dump()
  with self.assertRaises(PlannerOutputInvalid):asyncio.run(s.plan(p))
  self.assertEqual(p.model_dump(),before)
 def test_malformed_decoder_boundaries_required502(self):
  for text in ('['*1100+'0'+']'*1100,'{"tasks":'+'9'*5000+'}'):
   async def g(*args):return 'fixture',text
   s=Service(None,generate_fn=g);p=s.create('t',CreateProjectRequest(goal='test goal'))
   a=FastAPI();a.include_router(routes.router);a.dependency_overrides[routes.get_service]=lambda:s;a.dependency_overrides[routes.tenant]=lambda:'t'
   out=TestClient(a,raise_server_exceptions=False).post(f'/project-builder/projects/{p.id}/plan')
   with self.subTest(length=len(text)):self.assertEqual(out.status_code,502,out.text)
   self.assertEqual(p.revision,0);self.assertIsNone(p.plan)
