from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from sqlalchemy import create_engine
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.schemas import TaskContext,PlanNode,TaskState

def test_overlapping_runtime_run_rejected_before_loop_state_or_second_call(tmp_path):
 entered=Event();release=Event();calls=[]
 class Model:
  def complete(self,*args):calls.append(args);entered.set();assert release.wait(5);return {'result':'fixture'}
 engine=create_engine(f'sqlite:///{tmp_path / "reentry.db"}');repo=GCWRepository(engine);repo.create_schema();runtime=GCWRuntime(repo,executive_model=Model())
 ctx=TaskContext(goal='fixture',plan=[PlanNode(title='reason')]);repo.save_task(ctx)
 with ThreadPoolExecutor(max_workers=2) as pool:
  first=pool.submit(runtime.run_task,ctx.id);assert entered.wait(5)
  try:
   with pytest.raises(RuntimeError,match='runtime execution already active'):runtime.run_task(ctx.id)
   for operation in [lambda:runtime.submit_goal('overlap'),lambda:runtime.step(),lambda:runtime.resume(ctx.id,ctx.plan[0].id,approved=True)]:
    with pytest.raises(RuntimeError,match='runtime execution already active'):operation()
   assert len(calls)==1 and len(repo.list_tasks())==1
  finally:release.set()
  assert first.result().state==TaskState.SUCCEEDED
 assert repo.load_task(ctx.id).state==TaskState.SUCCEEDED
 engine.dispose()

def test_mounted_busy_is_conflict_not_server_error():
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.modules.m20_general_cognitive_worker.runtime import RuntimeBusy
 from app.modules.m20_general_cognitive_worker.runtime_routes import router,get_runtime
 class Busy:
  def get_task(self,*args):return object()
  def run_task(self,*args,**kwargs):raise RuntimeBusy('runtime execution already active')
 app=FastAPI();app.include_router(router);app.dependency_overrides[get_runtime]=lambda:Busy()
 response=TestClient(app).post('/api/modules/20/runtime/tasks/fixture/step',json={})
 assert response.status_code==409 and response.json()['detail']=='runtime execution already active'

def test_held_execution_lock_rejects_before_any_model_or_task_write(tmp_path):
 calls=[]
 class Model:
  def complete(self,*args):calls.append(args);return {'result':'fixture'}
 engine=create_engine(f'sqlite:///{tmp_path / "held-lock.db"}');repo=GCWRepository(engine);repo.create_schema();runtime=GCWRuntime(repo,executive_model=Model())
 ctx=TaskContext(goal='fixture',plan=[PlanNode(title='reason')]);repo.save_task(ctx)
 runtime._execution_lock.acquire()
 try:
  with pytest.raises(RuntimeError,match='runtime execution already active'):runtime.run_task(ctx.id)
  assert calls==[] and repo.load_task(ctx.id).state==TaskState.PENDING
 finally:runtime._execution_lock.release();engine.dispose()
