from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.runtime_routes import router, get_runtime
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.schemas import TaskContext, PlanNode

OPERATIONS = [
    ('post','/methods/fixture/activate',{'expected_hash':'a'*64},'planner','activate_method'),
    ('post','/risk-registers',{'goal':'fixture','risks':[{'id':'r'}]},'risk_registers','create'),
    ('post','/risk-registers/fixture/revise',{'expected_revision':1,'risks':[{'id':'r'}]},'risk_registers','revise'),
    ('patch','/risk-registers/fixture/risks/r',{'expected_revision':1,'changes':{'owner':'fixture'}},'risk_registers','patch_risk'),
]

@pytest.fixture
def wired(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "nested.db"}')
    repo=GCWRepository(engine);repo.create_schema();runtime=GCWRuntime(repo)
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_runtime]=lambda:runtime
    yield runtime,repo,TestClient(app)
    engine.dispose()

@pytest.mark.parametrize('verb,path,payload,component,method',OPERATIONS)
def test_held_runtime_lock_blocks_nested_route_before_mutation(wired,monkeypatch,verb,path,payload,component,method):
    runtime,repo,client=wired;calls=[]
    def mutation(*args,**kwargs):calls.append((args,kwargs));return True if component=='planner' else {'id':'fixture'}
    monkeypatch.setattr(getattr(runtime,component),method,mutation)
    runtime._execution_lock.acquire()
    try:
        response=getattr(client,verb)('/api/modules/20/runtime'+path,json=payload)
        assert response.status_code==409
        assert response.json()['detail']=='runtime execution already active'
        assert calls==[]
    finally:runtime._execution_lock.release()

@pytest.mark.parametrize('verb,path,payload,component,method',OPERATIONS)
def test_actual_execution_blocks_nested_route_then_allows_after_release(wired,monkeypatch,verb,path,payload,component,method):
    runtime,repo,client=wired;entered=Event();release=Event();calls=[]
    class Model:
        def complete(self,*args):entered.set();assert release.wait(10);return {'result':'fixture'}
    runtime.loop.model=Model()
    ctx=TaskContext(goal='fixture',plan=[PlanNode(title='reason')]);repo.save_task(ctx)
    def mutation(*args,**kwargs):calls.append((args,kwargs));return True if component=='planner' else {'id':'fixture'}
    monkeypatch.setattr(getattr(runtime,component),method,mutation)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(runtime.run_task,ctx.id);assert entered.wait(5)
        try:
            response=getattr(client,verb)('/api/modules/20/runtime'+path,json=payload)
            assert response.status_code==409 and calls==[]
        finally:release.set()
        future.result()
    response=getattr(client,verb)('/api/modules/20/runtime'+path,json=payload)
    assert response.status_code in (200,201) and len(calls)==1

@pytest.mark.parametrize('verb,path,payload,component,method',OPERATIONS)
def test_nested_mutation_holds_execution_lock_and_releases_on_error(wired,monkeypatch,verb,path,payload,component,method):
    from app.modules.m20_general_cognitive_worker.runtime import RuntimeBusy
    runtime,repo,client=wired;entered=Event();release=Event()
    ctx=TaskContext(goal='fixture',plan=[PlanNode(title='reason')]);repo.save_task(ctx)
    def mutation(*args,**kwargs):
        entered.set();assert release.wait(10)
        raise ValueError('fixture rejected mutation')
    monkeypatch.setattr(getattr(runtime,component),method,mutation)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(getattr(client,verb),'/api/modules/20/runtime'+path,json=payload)
        assert entered.wait(5)
        try:
            with pytest.raises(RuntimeBusy,match='already active'):runtime.run_task(ctx.id)
            assert repo.load_task(ctx.id).state.value=='pending'
        finally:release.set()
        if component=='planner':
            with pytest.raises(ValueError,match='fixture rejected'):future.result()
        else:
            assert future.result().status_code==422
    # Exceptions must never leave the shared runtime permanently busy.
    assert runtime._execution_lock.acquire(blocking=False)
    runtime._execution_lock.release()


def test_real_risk_create_commits_only_when_runtime_idle(wired):
    runtime,repo,client=wired
    risk={'id':'r','cause':'fixture','severity':2,'occurrence':2,'detection':2,
          'owner':'fixture','mitigation':'fixture','test':'fixture','evidence':[]}
    runtime._execution_lock.acquire()
    try:
        response=client.post('/api/modules/20/runtime/risk-registers',json={'goal':'fixture','risks':[risk]})
        assert response.status_code==409 and runtime.risk_registers.list()==[]
    finally:runtime._execution_lock.release()
    response=client.post('/api/modules/20/runtime/risk-registers',json={'goal':'fixture','risks':[risk]})
    assert response.status_code==201
    created=response.json()
    assert runtime.risk_registers.get(created['id'])['revision']==1
    path='/api/modules/20/runtime/risk-registers/'+created['id']
    runtime._execution_lock.acquire()
    try:
        assert client.post(path+'/revise',json={'expected_revision':1,'risks':[risk]}).status_code==409
        assert client.patch(path+'/risks/r',json={'expected_revision':1,'changes':{'owner':'new'}}).status_code==409
        assert runtime.risk_registers.get(created['id'])['revision']==1
    finally:runtime._execution_lock.release()
    assert client.patch(path+'/risks/r',json={'expected_revision':1,'changes':{'owner':'new'}}).status_code==200
    assert runtime.risk_registers.get(created['id'])['revision']==2
