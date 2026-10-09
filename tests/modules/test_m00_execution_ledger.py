"""Memo3 actual SQL intent/claim/outcome tests, fixture effects only."""
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service,ApprovalEffectRow,ApprovalConflictError
from app.modules.m00_approval_center import execution
from app.workers import action_registry
from app.workers.tasks import execute_approved_action

@pytest.fixture
def env(tmp_path,monkeypatch):
    engine=create_engine(f'sqlite:///{tmp_path}/execution.db',connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    class Clock:
        now=datetime(2026,10,9,tzinfo=timezone.utc)
        def __call__(self):return self.now
    clock=Clock();svc=Service(session_factory=sessions,clock=clock)
    monkeypatch.setattr('app.modules.m00_approval_center.service.default_service',lambda:svc)
    monkeypatch.setattr(action_registry,'_EXECUTORS',{})
    view=svc.submit(module_id=5,action_type='fixture',payload={'value':1},user_id='owner')
    svc.decide(view['id'],ApprovalStatus.APPROVED,'owner')
    return svc,svc.get(view['id']),sessions,clock


def row(env):
    with env[2]() as db:return db.get(execution.ExecutionRow,env[1]['id'])


def test_execution_success_replay_returns_persisted_result_without_adapter_or_preflight(env,monkeypatch):
    calls=[];svc,view,_,_=env
    action_registry.register_executor(5,'fixture',lambda payload:calls.append(payload) or {'value':1})
    assert execute_approved_action.run(view['id'],'effect')['result']=={'value':1}
    monkeypatch.setattr(action_registry,'_EXECUTORS',{})
    monkeypatch.setattr('app.modules.m00_approval_center.impact.impact_preview',lambda *a,**k:(_ for _ in ()).throw(AssertionError('replay must precede drift/provider')))
    assert execute_approved_action.run(view['id'],'effect')['result']=={'value':1}
    assert len(calls)==1 and row(env).state=='succeeded'


def test_execution_missing_executor_makes_zero_permits_or_intents(env):
    svc,view,sessions,_=env
    with pytest.raises(LookupError):execute_approved_action.run(view['id'],'effect')
    with sessions() as db:
        assert db.get(execution.ExecutionRow,view['id']) is None
        assert db.scalar(select(ApprovalEffectRow)) is None


@pytest.mark.parametrize('kind',['exception','malformed','non-json','nonfinite'])
def test_execution_uncertain_effect_never_auto_retries(env,kind):
    svc,view,_,_=env;calls=[]
    def adapter(payload):
        calls.append(1)
        if kind=='exception':raise TimeoutError('fixture unknown')
        return None if kind=='malformed' else {'object':object()} if kind=='non-json' else {'value':float('nan')}
    action_registry.register_executor(5,'fixture',adapter)
    with pytest.raises((TypeError,ValueError,TimeoutError)):execute_approved_action.run(view['id'],'effect')
    assert row(env).state=='outcome-unknown'
    with pytest.raises(execution.ExecutionUnknown):execute_approved_action.run(view['id'],'effect')
    assert calls==[1]


def test_execution_expired_live_worker_cannot_complete_or_be_reclaimed(env):
    svc,view,_,clock=env
    execution.prepare(svc,view,'effect','v1');token=execution.claim(svc,view,'effect',lease_seconds=1)
    clock.now+=timedelta(seconds=2)
    with pytest.raises(execution.ExecutionUnknown):execution.prior_result(svc,view,'effect')
    assert row(env).state=='outcome-unknown'
    with pytest.raises(execution.ExecutionUnknown):execution.complete(svc,view['id'],token,{'success':True})
    with pytest.raises(execution.ExecutionUnknown):execution.claim(svc,view,'effect')
    assert row(env).result is None


def test_execution_stale_token_cannot_overwrite_current_claim(env):
    svc,view,_,_=env;execution.prepare(svc,view,'effect','v1');token=execution.claim(svc,view,'effect')
    with pytest.raises(execution.ExecutionUnknown):execution.complete(svc,view['id'],'stale',{'bad':True})
    assert execution.complete(svc,view['id'],token,{'ok':True})=={'ok':True}


def test_execution_immutable_effect_payload_owner_binding(env):
    svc,view,_,_=env;execution.prepare(svc,view,'effect','v1')
    for changed,effect in [({**view,'user_id':'foreign'},'effect'),({**view,'payload':{'value':2}},'effect'),(view,'other')]:
        with pytest.raises(ApprovalConflictError):execution.prior_result(svc,changed,effect)
    with pytest.raises(execution.ExecutionUnknown):execution.prepare(svc,view,'effect','v2')


def test_execution_concurrent_claim_has_one_winner_and_no_barrier_at_effect(env):
    svc,view,_,_=env;execution.prepare(svc,view,'effect','v1');barrier=threading.Barrier(2)
    def worker():
        barrier.wait()
        try:return execution.claim(svc,view,'effect')
        except execution.ExecutionUnknown:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:worker(),range(2)))
    assert sum(r is not None for r in results)==1


def test_execution_permit_and_intent_roll_back_together(env,monkeypatch):
    from sqlalchemy.orm import Session
    svc,view,sessions,_=env;original=Session.add
    def fail(self,entity,*a,**kw):
        if isinstance(entity,execution.ExecutionRow):raise RuntimeError('fixture intent write failed')
        return original(self,entity,*a,**kw)
    monkeypatch.setattr(Session,'add',fail)
    with pytest.raises(RuntimeError):execution.prepare(svc,view,'effect','v1')
    with sessions() as db:
        assert db.get(execution.ExecutionRow,view['id']) is None
        assert db.scalar(select(ApprovalEffectRow)) is None
    assert [e['event'] for e in svc.audit(view['id'])]==['created','approved']


def test_execution_ready_intent_recovers_after_reopen_without_new_permit(env):
    svc,view,sessions,_=env;execution.prepare(svc,view,'effect','v1')
    recovered=Service(session_factory=sessions,clock=svc._clock)
    assert execution.prior_result(recovered,view,'effect') is None
    execution.prepare(recovered,view,'effect','v1');token=execution.claim(recovered,view,'effect')
    execution.complete(recovered,view['id'],token,{'ok':True})
    assert [e['event'] for e in svc.audit(view['id'])].count('effect_consumed')==1


def test_execution_legacy_permit_without_ledger_is_unknown(env):
    svc,view,_,_=env
    svc.consume_effect(view['id'],module_id=5,action_type='fixture',payload=view['payload'],user_id='owner',effect_id='effect',actor='worker')
    with pytest.raises(execution.ExecutionUnknown):execution.prior_result(svc,view,'effect')
    with pytest.raises(execution.ExecutionUnknown):execution.prepare(svc,view,'effect','v1')

@pytest.mark.parametrize('boundary',['before-claim','before-dispatch','after-effect','after-result'])
def test_execution_real_process_crash_boundaries_preserve_unknown_or_stored_result(env,tmp_path,boundary):
    import os,subprocess,sys
    from pathlib import Path
    svc,view,sessions,clock=env;database=str(sessions.kw['bind'].url);effect_file=tmp_path/'effect.txt'
    script='''
import os
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m00_approval_center.service import Service
from app.modules.m00_approval_center import execution
svc=Service(session_factory=sessionmaker(bind=create_engine(os.environ['TEST_DATABASE']),expire_on_commit=False),clock=lambda:datetime(2026,10,9,tzinfo=timezone.utc))
view=svc.get(os.environ['TEST_APPROVAL'])
execution.prepare(svc,view,'effect','v1')
boundary=os.environ['TEST_BOUNDARY']
if boundary=='before-claim':os._exit(17)
token=execution.claim(svc,view,'effect',lease_seconds=1)
if boundary=='before-dispatch':os._exit(17)
Path(os.environ['TEST_EFFECT']).write_text('one fixture effect')
if boundary=='after-effect':os._exit(17)
execution.complete(svc,view['id'],token,{'saved':True})
os._exit(17)
'''
    process=subprocess.run([sys.executable,'-c',script],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2]/'backend'),'TEST_DATABASE':database,'TEST_APPROVAL':view['id'],'TEST_BOUNDARY':boundary,'TEST_EFFECT':str(effect_file)},timeout=20)
    assert process.returncode==17
    clock.now+=timedelta(seconds=2)
    if boundary=='before-claim':
        assert execution.prior_result(svc,view,'effect') is None
        assert row(env).state=='ready' and not effect_file.exists()
    elif boundary=='after-result':
        assert execution.prior_result(svc,view,'effect')=={'saved':True}
        assert effect_file.read_text()=='one fixture effect'
    else:
        with pytest.raises(execution.ExecutionUnknown):execution.prior_result(svc,view,'effect')
        assert row(env).state=='outcome-unknown'
        assert effect_file.exists()==(boundary=='after-effect')


def test_execution_worker_concurrent_calls_dispatch_once_and_other_is_held(env):
    svc,view,_,_=env;calls=[];entered=threading.Event();release=threading.Event()
    def adapter(payload):
        calls.append(1);entered.set();assert release.wait(5);return {'ok':True}
    action_registry.register_executor(5,'fixture',adapter)
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(execute_approved_action.run,view['id'],'effect')
        assert entered.wait(5)
        with pytest.raises(execution.ExecutionUnknown):execute_approved_action.run(view['id'],'effect')
        release.set();assert first.result(5)['result']=={'ok':True}
    assert calls==[1]
    assert execute_approved_action.run(view['id'],'effect')['result']=={'ok':True}


def test_execution_populated_migration_does_not_bless_historical_permits(env,tmp_path):
    import subprocess,sys,os
    from pathlib import Path
    database=tmp_path/'migration.db';root=Path(__file__).resolve().parents[2]
    runenv={**os.environ,'ATLAS_DATABASE_URL':f'sqlite:///{database}','PYTHONPATH':str(root/'backend')}
    prior=subprocess.run([sys.executable,'-m','alembic','upgrade','20261008_m20_chroma_jobs'],cwd=root,env=runenv,capture_output=True,text=True,timeout=30)
    assert prior.returncode==0,prior.stderr
    from sqlalchemy import text,inspect
    engine=create_engine(f'sqlite:///{database}')
    with engine.begin() as db:
        db.execute(text("INSERT INTO m00_approval_effects (approval_id,effect_id,request_hash,actor,consumed_at) VALUES ('legacy','historical','hash','fixture',CURRENT_TIMESTAMP)"))
    upgraded=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=runenv,capture_output=True,text=True,timeout=30)
    assert upgraded.returncode==0,upgraded.stderr
    with engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM m00_execution_intents')).scalar()==0
        assert db.execute(text('SELECT count(*) FROM m00_approval_effects')).scalar()==1
    assert 'm00_execution_intents' in inspect(engine).get_table_names()


def test_execution_postgres_separate_claims_exactly_one_wins_and_fenced_outcome_persists(tmp_path):
    import pgserver
    server=pgserver.get_server(tmp_path/'postgres',cleanup_mode='stop')
    engine=create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    execution.ExecutionRow.__table__.create(engine)
    # Only tables this dispatcher boundary uses, actual PostgreSQL constraints.
    from app.modules.m00_approval_center.service import ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow
    from app.modules.m00_approval_center.impact import ApprovalReviewStateRow
    for table in (ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow,ApprovalReviewStateRow):table.__table__.create(engine)
    sessions=sessionmaker(bind=engine,expire_on_commit=False)
    svc=Service(session_factory=sessions)
    view=svc.submit(module_id=5,action_type='fixture',payload={},user_id='owner');svc.decide(view['id'],ApprovalStatus.APPROVED,'fixture');view=svc.get(view['id'])
    execution.prepare(svc,view,'pg-effect','v1');barrier=threading.Barrier(2)
    def worker():
        local=Service(session_factory=sessions);barrier.wait(5)
        try:return execution.claim(local,view,'pg-effect')
        except execution.ExecutionUnknown:return None
    with ThreadPoolExecutor(2) as pool:tokens=list(pool.map(lambda _:worker(),range(2)))
    assert len([t for t in tokens if t])==1
    token=next(t for t in tokens if t)
    execution.complete(svc,view['id'],token,{'postgres':True})
    assert execution.prior_result(Service(session_factory=sessions),view,'pg-effect')=={'postgres':True}
    engine.dispose()


def test_execution_populated_ledger_downgrade_refuses_without_deleting_outcome(env):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    svc,view,sessions,_=env;execution.prepare(svc,view,'effect','v1')
    path=Path(__file__).resolve().parents[2]/'migrations/versions/20261009_m00_execution_intents.py'
    spec=importlib.util.spec_from_file_location('execution_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with sessions.kw['bind'].begin() as db:
        module.op=Operations(MigrationContext.configure(db))
        with pytest.raises(RuntimeError,match='destructive downgrade refused'):module.downgrade()
    assert row(env).state=='ready'


def test_execution_same_effect_id_for_other_approval_rolls_back_loser_permit(env):
    svc,view,sessions,_=env;execution.prepare(svc,view,'effect','v1')
    other=svc.submit(module_id=5,action_type='fixture',payload={'value':2},user_id='other')
    svc.decide(other['id'],ApprovalStatus.APPROVED,'fixture');other=svc.get(other['id'])
    with pytest.raises(ApprovalConflictError):execution.prepare(svc,other,'effect','v1')
    with sessions() as db:
        assert db.get(execution.ExecutionRow,other['id']) is None
        assert db.scalar(select(ApprovalEffectRow).where(ApprovalEffectRow.approval_id==other['id'])) is None
    assert [e['event'] for e in svc.audit(other['id'])]==['created','approved']


def test_execution_observed_drift_refuses_before_claim_or_adapter(env,monkeypatch):
    svc,view,sessions,_=env;calls=[]
    action_registry.register_executor(5,'fixture',lambda payload:calls.append(payload) or {})
    monkeypatch.setattr('app.modules.m00_approval_center.impact.impact_preview',lambda *a,**k:{'verdict':'drifted'})
    with pytest.raises(ApprovalConflictError):execute_approved_action.run(view['id'],'effect')
    assert calls==[]
    with sessions() as db:assert db.get(execution.ExecutionRow,view['id']) is None


@pytest.mark.parametrize('seconds',[0,True,3601])
def test_execution_invalid_lease_refuses_without_state_change(env,seconds):
    svc,view,_,_=env;execution.prepare(svc,view,'effect','v1')
    with pytest.raises(ValueError):execution.claim(svc,view,'effect',lease_seconds=seconds)
    assert row(env).state=='ready'


def test_execution_two_requests_concurrent_same_effect_id_only_winner_has_permit(env):
    svc,view,sessions,_=env
    other=svc.submit(module_id=5,action_type='fixture',payload={'value':2},user_id='other')
    svc.decide(other['id'],ApprovalStatus.APPROVED,'fixture');other=svc.get(other['id']);barrier=threading.Barrier(2)
    def prepare(local_view):
        barrier.wait(5)
        try:execution.prepare(svc,local_view,'shared-effect','v1');return local_view['id']
        except ApprovalConflictError:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(prepare,[view,other]))
    assert sum(r is not None for r in results)==1
    with sessions() as db:
        assert len(db.scalars(select(execution.ExecutionRow)).all())==1
        assert len(db.scalars(select(ApprovalEffectRow)).all())==1


def test_execution_expired_claim_before_dispatch_refuses_zero_adapter_calls(env,monkeypatch):
    svc,view,_,clock=env;calls=[]
    action_registry.register_executor(5,'fixture',lambda payload:calls.append(1) or {})
    original=execution.claim
    def expire(*args,**kwargs):
        token=original(*args,**kwargs);clock.now+=timedelta(seconds=61);return token
    monkeypatch.setattr(execution,'claim',expire)
    with pytest.raises(execution.ExecutionUnknown):execute_approved_action.run(view['id'],'effect')
    assert calls==[] and row(env).state=='outcome-unknown'


@pytest.mark.parametrize('delay',[0,0.001,0.01])
def test_execution_start_profiles_count_outcomes_without_executor_barrier(env,delay):
    import time
    svc,_,_,_=env
    counts={'executed':0,'held':0};calls=[];lock=threading.Lock()
    def adapter(payload):
        with lock:calls.append(payload['trial'])
        time.sleep(0.002);return {'trial':payload['trial']}
    action_registry.register_executor(5,'profile',adapter)
    for trial in range(20):
        view=svc.submit(module_id=5,action_type='profile',payload={'trial':trial},user_id='owner')
        svc.decide(view['id'],ApprovalStatus.APPROVED,'fixture');barrier=threading.Barrier(2)
        def worker(offset):
            barrier.wait(5);time.sleep(offset)
            try:return execute_approved_action.run(view['id'],f'profile-{trial}')['status']
            except execution.ExecutionUnknown:return 'held'
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(worker,[0,delay]))
        assert results.count('executed')>=1
        for outcome in results:counts[outcome]+=1
    assert sorted(calls)==list(range(20)) # Exactly one local adapter call per intent.
    assert counts['executed']+counts['held']==40
    print({'delay':delay,'outcomes':counts,'adapter_calls':len(calls)})
