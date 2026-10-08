"""Mounted Atlas API validation acceptance in a fresh isolated interpreter."""
import os
import subprocess
import sys


def test_mounted_atlas_api_validates_requests_before_dispatch(tmp_path):
    code='''
import sys
from fastapi.testclient import TestClient
from app.main import app
from app.core.models import GoalRequest
import fastapi,pydantic
assert sys.version_info[:2]==(3,12)
assert fastapi.__version__.startswith('0.')
assert pydantic.__version__.startswith('2.')
assert GoalRequest.model_fields['goal']
with TestClient(app) as client:
 assert client.get('/health').json()=={'status':'ok'}
 for payload in ({}, {'goal':'x'}, {'goal':'x'*2001}):
  response=client.post('/api/v1/goals/plan',json=payload)
  assert response.status_code==422,response.text
  assert any(e['loc'][:2]==['body','goal'] for e in response.json()['detail'])
 response=client.post('/api/v1/goals/plan',json={'goal':'organize a test-only task'})
 assert response.status_code==200,response.text
 body=response.json()
 assert body['goal']=='organize a test-only task'
 assert body['approval_requests']==[]
 assert len(body['steps'])==1 and body['steps'][0]['module_id']==20
 assert body['steps'][0]['operation']=='prepare_goal_work'
 assert body['steps'][0]['requires_approval'] is False
'''
    env={**os.environ,'ATLAS_ENV':'local','ATLAS_DEV_NO_AUTH':'1',
         'ATLAS_DATABASE_URL':f'sqlite:///{tmp_path}/atlas.sqlite',
         'ATLAS_AUTO_CREATE_SCHEMA':'0','ATLAS_RUNTIME_DATA_DIR':str(tmp_path/'runtime')}
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr+'\n'+result.stdout
