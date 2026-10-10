"""Approval + durable claim + real namespace execution, never mock substitution."""
import asyncio,base64,os,shutil,tempfile
from datetime import timedelta
from pathlib import Path
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalEffectRow,ApprovalRequestRow
from app.modules.m14_project_builder.sql_repository import ProjectRow
from app.modules.m14_project_builder.schemas import ProjectPlan,ProjectTask,Budget
from app.modules.m14_project_builder.sandbox_wave import *

@pytest.fixture
def env(tmp_path):
    root=Path(tempfile.mkdtemp(prefix='atlas-wave-test-',dir=Path.home()))
    root.chmod(0o700)
    engine=create_engine('sqlite:///'+str(tmp_path/'wave.db'),connect_args={'check_same_thread':False})
    sessions=sessionmaker(engine,expire_on_commit=False)
    Base.metadata.create_all(engine)
    svc=SandboxWaveService(sessions,str(root))
    try:svc._probe()
    except WaveUnavailable:pytest.skip('real Bubblewrap namespace capability unavailable')
    plan=ProjectPlan(goal='demo',tasks=[ProjectTask(id='a',title='write',objective='write result',agent_kind='coder'),ProjectTask(id='b',title='then write',objective='dependent task',agent_kind='coder',dependencies=['a'])])
    with sessions.begin() as db:db.add(ProjectRow(tenant_id='t',id='p',goal='demo',brief={},budget=Budget().model_dump(mode='json'),status='planned',revision=1,plan=plan.model_dump(mode='json')))
    yield svc,sessions,root
    engine.dispose();shutil.rmtree(root)

def request(code="open('/output/result.txt','w').write('hello')",**kw):
    return WaveDraft(tasks={'a':TaskCode(code=code),'b':TaskCode(code="raise Exception('dependent must not run')")},**kw)

def approved(svc):
    d=svc.draft('t','owner','p',request());s=svc.submit('t','owner',d['id'])
    svc.gate.decide(s['approval_id'],ApprovalStatus.APPROVED,decided_by='owner')
    return d['id'],s['approval_id']

def test_real_execution_restart_artifact_and_no_replay(env):
    svc,sessions,root=env;wid,aid=approved(svc)
    before=svc.get('t','owner',wid)['payload']['plan']
    result=asyncio.run(svc.execute('t','owner',wid))
    assert result['state']=='awaiting_review'
    assert len(result['result']['tasks'])==1
    assert result['result']['tasks'][0]['execution_state']=='sandbox_executed'
    assert result['result']['all_dag_completed'] is False
    fresh=SandboxWaveService(sessions,str(root));arts=fresh.artifacts('t','owner',wid)
    assert len(arts)==1
    data,name,sha=fresh.artifact('t','owner',wid,arts[0]['id']);assert data==b'hello'
    assert sha==hashlib.sha256(data).hexdigest()
    with sessions() as db:assert db.scalar(select(ProjectRow)).plan==before
    with pytest.raises(WaveConflict):asyncio.run(fresh.execute('t','owner',wid))
    with pytest.raises(WaveForbidden):fresh.artifact('t','other',wid,arts[0]['id'])
    with sessions() as db:assert len(list(db.scalars(select(ApprovalEffectRow))))==1

@pytest.mark.parametrize('state',['pending','denied','expired','legacy','foreign','changed_code','drift','tamper','policy'])
def test_reject_before_claim(env,state):
    svc,sessions,root=env
    d=svc.draft('t','owner','p',request());wid=d['id'];s=svc.submit('t','owner',wid);aid=s['approval_id']
    if state!='pending':svc.gate.decide(aid,ApprovalStatus.APPROVED,decided_by='owner')
    with sessions.begin() as db:
        approval=db.get(ApprovalRequestRow,aid)
        row=db.get(SandboxWaveRow,wid)
        if state=='denied':approval.status='denied'
        if state=='expired':approval.expires_at=svc.gate._clock()-timedelta(seconds=1)
        if state=='legacy':approval.action_type='execute_project_plan'
        if state=='foreign':approval.user_id='other'
        if state=='changed_code':approval.payload={**approval.payload,'profile':'different'}
        if state=='drift':db.scalar(select(ProjectRow)).revision+=1
        if state=='tamper':row.digest='0'*64
        if state=='policy':
            from app.modules.m00_approval_center.service import ApprovalEventRow
            from sqlalchemy import delete
            db.execute(delete(ApprovalEventRow).where(ApprovalEventRow.approval_id==aid,ApprovalEventRow.event=='approved'))
    with pytest.raises((WaveConflict,ApprovalConflictError)):svc.claim('t','owner',wid)
    with sessions() as db:
        assert db.get(SandboxWaveRow,wid).state=='awaiting_approval'
        assert not db.scalar(select(ApprovalEffectRow))


def test_atomic_failure_rolls_back_claim_and_consume(env,monkeypatch):
    svc,sessions,root=env;wid,aid=approved(svc)
    original=svc.gate.consume_effect
    def fault(*a,**kw):original(*a,**kw);kw['_session'].flush();raise RuntimeError('fault after permit')
    monkeypatch.setattr(svc.gate,'consume_effect',fault)
    with pytest.raises(RuntimeError):svc.claim('t','owner',wid)
    with sessions() as db:
        assert db.get(SandboxWaveRow,wid).state=='awaiting_approval'
        assert not db.scalar(select(ApprovalEffectRow))


def test_claimed_restart_unknown_and_second_draft_blocked(env):
    svc,sessions,root=env;wid,aid=approved(svc);svc.claim('t','owner',wid)
    fresh=SandboxWaveService(sessions,str(root))
    assert fresh.get('t','owner',wid)['unknown_after_claim']
    with pytest.raises(WaveConflict):fresh.claim('t','owner',wid)
    wid2,aid2=approved(fresh)
    with pytest.raises(WaveConflict):fresh.claim('t','owner',wid2)


def test_live_probe_before_consumption(env,monkeypatch):
    svc,sessions,root=env;wid,aid=approved(svc)
    def unavailable():raise WaveUnavailable('namespace denied')
    monkeypatch.setattr(svc,'_probe',unavailable)
    with pytest.raises(WaveUnavailable):svc.claim('t','owner',wid)
    with sessions() as db:assert not db.scalar(select(ApprovalEffectRow))


def test_real_network_denied_readonly_and_timeout_group(env):
    svc,sessions,root=env
    code="""import socket
try:
 socket.create_connection(('1.1.1.1',443),timeout=1)
 raise Exception('network enabled')
except OSError:pass
try:
 open('/input/analysis.py','w').write('x')
 raise Exception('input writable')
except OSError:pass
open('/output/isolation.txt','w').write('verified')
"""
    receipt,arts=svc._task('a',{'code':code,'inputs':{},'outputs':['isolation.txt']},{'timeout_seconds':3,'memory_mb':256})
    assert receipt['exit_code']==0 and arts[0][1]==b'verified'
    marker=root/'escape-marker'
    # Child writes only after timeout. Bound namespace mount disappears with pid namespace.
    code="import os,time;\ntry: os.fork();raise Exception('fork enabled')\nexcept PermissionError: pass\ntime.sleep(30)"
    receipt,arts=svc._task('a',{'code':code,'inputs':{},'outputs':['result.txt']},{'timeout_seconds':1,'memory_mb':256})
    assert receipt['timed_out'] and receipt['execution_state']=='failed'
    assert all(data==b'' for _,data in arts)

@pytest.mark.parametrize('field,value',[('max_parallel',9),('max_parallel',True),('timeout_seconds',61),('memory_mb',513)])
def test_bounds(field,value):
    with pytest.raises(ValueError):request(**{field:value})

@pytest.mark.parametrize('value',['/tmp','/tmp/../tmp','/dev/shm','/missing-root','relative'])
def test_root_refusal(value):
    with pytest.raises(WaveUnavailable):private_root(value)


def test_bounded_inputs(env):
    svc,_,_=env
    for name,data in [('../escape','YQ=='),('analysis.py','YQ=='),('valid','invalid!'),('valid',base64.b64encode(b'x'*100001).decode())]:
        req=request();req.tasks['a'].inputs={name:data}
        with pytest.raises(WaveError):svc.draft('t','owner','p',req)


def test_fixed_outputs_fork_and_byte_bounds_real(env):
    svc,_,_=env
    code="""import os
try:
 os.fork()
 raise Exception('fork allowed')
except PermissionError:pass
try:
 open('/output/not-declared','w').write('bad')
 raise Exception('directory writable')
except OSError:pass
try:
 open('/unbounded-root-file','w').write('bad')
 raise Exception('root writable')
except OSError:pass
try:
 open('/dev/shm/unbounded-file','w').write('bad')
 raise Exception('dev shm writable')
except OSError:pass
try:
 open('/tmp/bad','w').write('bad')
 raise Exception('tmp writable')
except OSError:pass
with open('/output/result.txt','wb') as f:
 try: f.write(b'x'*100000);f.flush()
 except OSError: pass
"""
    receipt,arts=svc._task('a',{'code':code,'inputs':{},'outputs':['result.txt']},{'timeout_seconds':3,'memory_mb':256})
    assert receipt['execution_state']=='sandbox_executed'
    assert len(arts)==1 and len(arts[0][1])<=50000


def test_postgres_claim_rollback_and_cas_actual(tmp_path):
    import pgserver
    server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
    engine=create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    sessions=sessionmaker(engine,expire_on_commit=False)
    # Only relevant tables: whole shared metadata includes pgvector unrelated to this unit.
    from app.modules.m00_approval_center.service import ApprovalEventRow
    from app.modules.m00_approval_center.impact import ApprovalReviewStateRow
    from app.modules.m14_project_builder.wave_supersede import WaveKeyVersionRow,WaveSupersedeRow
    for model in (WaveKeyVersionRow,WaveSupersedeRow,ProjectRow,ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow,ApprovalReviewStateRow,SandboxWaveRow,SandboxWaveTaskRow,SandboxWaveArtifactRow):model.__table__.create(engine,checkfirst=True)
    root=Path(tempfile.mkdtemp(prefix='wave-pg-',dir=Path.home()));root.chmod(0o700)
    try:
        svc=SandboxWaveService(sessions,str(root))
        plan=ProjectPlan(goal='demo',tasks=[ProjectTask(id='a',title='write',objective='write result',agent_kind='coder'),ProjectTask(id='b',title='next',objective='dependent task',agent_kind='coder',dependencies=['a'])])
        with sessions.begin() as db:db.add(ProjectRow(tenant_id='t',id='p',goal='demo',brief={},budget=Budget().model_dump(mode='json'),status='planned',revision=1,plan=plan.model_dump(mode='json')))
        wid,aid=approved(svc)
        original=svc.gate.consume_effect
        def fault(*a,**kw):original(*a,**kw);kw['_session'].flush();raise RuntimeError('post consume fault')
        svc.gate.consume_effect=fault
        with pytest.raises(RuntimeError):svc.claim('t','owner',wid)
        with sessions() as db:
            assert db.get(SandboxWaveRow,wid).state=='awaiting_approval'
            assert not db.scalar(select(ApprovalEffectRow))
        svc.gate.consume_effect=original
        from concurrent.futures import ThreadPoolExecutor
        def claim():
            try:svc.claim('t','owner',wid);return 'claimed'
            except WaveConflict:return 'refused'
        with ThreadPoolExecutor(2) as ex:assert sorted(ex.map(lambda _:claim(),range(2)))==['claimed','refused']
        with sessions() as db:assert len(list(db.scalars(select(ApprovalEffectRow))))==1
        with engine.connect() as db:print('actual PG',db.exec_driver_sql('select version()').scalar())
    finally:engine.dispose();shutil.rmtree(root)


def test_oidc_routes_owner_status_artifact(env,oidc_auth_headers,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m14_project_builder import routes
    svc,_,_=env
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    app=FastAPI();app.include_router(routes.router);app.dependency_overrides[routes.get_wave_service]=lambda:svc
    with TestClient(app) as client:
        headers=oidc_auth_headers('t','owner')
        d=client.post('/project-builder/projects/p/sandbox-waves',json=request().model_dump(),headers=headers)
        assert d.status_code==201
        wid=d.json()['id'];prefix='/project-builder/sandbox-waves/'+wid
        s=client.post(prefix+'/submit',headers=headers);assert s.status_code==202
        assert client.post(prefix+'/execute',headers=headers).status_code==409
        svc.gate.decide(s.json()['approval_id'],ApprovalStatus.APPROVED,decided_by='owner')
        executed=client.post(prefix+'/execute',headers=headers);assert executed.status_code==200
        assert client.get(prefix,headers=oidc_auth_headers('t','other')).status_code==403
        assert client.get(prefix,headers=oidc_auth_headers('foreign','owner')).status_code==403
        arts=client.get(prefix+'/artifacts',headers=headers).json()
        response=client.get(prefix+'/artifacts/'+arts[0]['id'],headers=headers)
        assert response.content==b'hello' and response.headers['X-Content-SHA256']==arts[0]['sha256']
        assert client.post(prefix+'/execute',headers=headers).status_code==409
        assert client.get(prefix).status_code in (401,403)


def test_sqlite_concurrent_claim_exactly_one(env):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.exc import OperationalError
    svc,sessions,_=env;wid,aid=approved(svc)
    def claim():
        try:svc.claim('t','owner',wid);return 'claimed'
        except (WaveConflict,OperationalError):return 'refused'
    with ThreadPoolExecutor(2) as ex:assert sorted(ex.map(lambda _:claim(),range(2)))==['claimed','refused']
    with sessions() as db:assert len(list(db.scalars(select(ApprovalEffectRow))))==1


def test_project_edit_during_execution_reported_not_followed(env,monkeypatch):
    svc,sessions,_=env;wid,aid=approved(svc);original=svc._task
    def edit(*a,**kw):
        with sessions.begin() as db:db.scalar(select(ProjectRow)).revision+=1
        return original(*a,**kw)
    monkeypatch.setattr(svc,'_task',edit)
    result=asyncio.run(svc.execute('t','owner',wid))
    assert result['result']['concurrent_project_drift']


def test_environment_lock_drift(env,monkeypatch):
    svc,sessions,_=env;wid,aid=approved(svc)
    monkeypatch.setattr(svc,'_probe',lambda:{'changed':True})
    with pytest.raises(WaveConflict):svc.claim('t','owner',wid)
    with sessions() as db:assert not db.scalar(select(ApprovalEffectRow))


def test_fixed_output_names_bounds(env):
    svc,_,_=env
    for outputs in [['../escape'],['x','x'],['.']]:
        req=request();req.tasks['a'].outputs=outputs
        with pytest.raises(WaveError):svc.draft('t','owner','p',req)


def test_migration_sqlite_and_postgres_actual(tmp_path):
    import importlib.util,pgserver
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    spec=importlib.util.spec_from_file_location('wave_migration',Path(__file__).resolve().parents[2]/'migrations/versions/20261010_m14_sandbox_wave.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    server=pgserver.get_server(tmp_path/'pg-migration',cleanup_mode='stop')
    for uri in ['sqlite:///'+str(tmp_path/'migration.db'),server.get_uri().replace('postgresql://','postgresql+psycopg://')]:
        engine=create_engine(uri)
        try:
            with engine.begin() as connection:
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
                    assert set(inspect(connection).get_table_names())>={'m14_sandbox_waves','m14_sandbox_wave_tasks','m14_sandbox_wave_artifacts'}
                    migration.downgrade()
                    assert not set(inspect(connection).get_table_names()) & {'m14_sandbox_waves','m14_sandbox_wave_tasks','m14_sandbox_wave_artifacts'}
        finally:engine.dispose()


def test_timeout_process_group_gone_real(env,monkeypatch):
    import subprocess
    from app.modules.m14_project_builder import wave_backend
    svc,_,_=env;pids=[];original=subprocess.Popen
    def record(*a,**kw):
        proc=original(*a,**kw);pids.append(proc.pid);return proc
    monkeypatch.setattr(wave_backend.subprocess,'Popen',record)
    receipt,arts=svc._task('a',{'code':'import time;time.sleep(30)','inputs':{},'outputs':['result.txt']},{'timeout_seconds':1,'memory_mb':256})
    assert receipt['timed_out'] and pids
    for pid in pids:
        with pytest.raises(ProcessLookupError):os.killpg(pid,0)


def test_no_opt_in_no_sandbox_root_no_route_execution(monkeypatch,oidc_auth_headers):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m14_project_builder.routes import router
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    monkeypatch.delenv('ATLAS_M14_SANDBOX_BACKEND',raising=False)
    app=FastAPI();app.include_router(router)
    with TestClient(app) as client:
        assert client.post('/project-builder/sandbox-waves/not-existing/execute',headers=oidc_auth_headers('t','owner')).status_code==503



def test_run_volatile_root_refused_before_any_work(monkeypatch):
    # Simulate a private existing /run descendant even when this host has no
    # private writable /run fixture. Resolved path policy, not OS permissions.
    from types import SimpleNamespace
    target=Path('/run/credentials/private-service')
    monkeypatch.setattr(Path,'is_symlink',lambda self:False)
    monkeypatch.setattr(Path,'resolve',lambda self,strict=False:self)
    monkeypatch.setattr(Path,'is_dir',lambda self:True)
    monkeypatch.setattr(Path,'stat',lambda self,*a,**kw:SimpleNamespace(st_mode=0o40700))
    with pytest.raises(WaveUnavailable):private_root(str(target))


def test_backend_helper_input_refused_before_claim_or_consume(env):
    svc,sessions,_=env
    req=request();req.tasks['a'].inputs={'empty-tmp':base64.b64encode(b'user data').decode()}
    with pytest.raises(WaveError):svc.draft('t','owner','p',req)
    with sessions() as db:
        assert not db.scalar(select(SandboxWaveRow))
        assert not db.scalar(select(ApprovalRequestRow))
        assert not db.scalar(select(ApprovalEffectRow))
