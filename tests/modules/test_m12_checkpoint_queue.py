from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m12_ai_research_lab.routes import get_checkpoint_queue
from app.modules.m12_ai_research_lab.checkpoint_queue import CheckpointQueue
C=TestClient(app);U='/api/v1/ai-research-lab/reproducible-run/checkpoint/enqueue';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'}
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);sessions=sessionmaker(bind=e,expire_on_commit=False);app.dependency_overrides[get_checkpoint_queue]=lambda:CheckpointQueue('t',sessions)
def teardown_function():app.dependency_overrides.clear()
def p(code='v1'):return {'run_id':'r','workflow_sha256':'a'*64,'code_version':code,'created_at':'2026-09-22T04:00:00Z','nodes':[{'node_id':'n','status':'queued','provider':'p','model':'m','budget_cents':1,'spent_cents':0,'input_sha256':'b'*64}],'resume_from_node_id':'n'}
def test_transactionally_queues_valid_checkpoint_and_is_idempotent():
 first=C.post(U,json=p(),headers=H);assert first.status_code==200 and first.json()['queue_state']=='queued';second=C.post(U,json=p(),headers=H);assert second.status_code==200 and second.json()['checkpoint_sha256']==first.json()['checkpoint_sha256']
def test_rejects_different_queued_head_for_same_run():
 assert C.post(U,json=p(),headers=H).status_code==200;r=C.post(U,json=p('v2'),headers=H);assert r.status_code==409 and 'different queued checkpoint' in r.text
def test_invalid_checkpoint_never_queues():
 x=p();x['nodes'][0]['spent_cents']=2;r=C.post(U,json=x,headers=H);assert r.status_code==422 and 'exceeds budget' in r.text
