"""Slice1 local write-ahead storage; no provider transport or epoch activation."""
from datetime import datetime,timezone
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service,ApprovalEffectRow,ApprovalConflictError
from app.modules.m24_billing.write_ahead import OperationRepository,OperationRow,DispatchRefused

@pytest.fixture(params=['sqlite','postgres'])
def env(tmp_path,request):
    if request.param=='postgres':
        import pgserver
        server=pgserver.get_server(tmp_path/'postgres',cleanup_mode='stop')
        engine=create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    else:
        engine=create_engine(f'sqlite:///{tmp_path}/billing.db',connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    service=Service(session_factory=sessions)
    view=service.submit(module_id=24,action_type='create_subscription_checkout',payload={'tenant_id':'t1','plan':{'id':'pro'}},user_id='t1')
    service.decide(view['id'],ApprovalStatus.APPROVED,'owner')
    yield service,service.get(view['id']),sessions,OperationRepository(service)
    engine.dispose()
    if request.param=='postgres':server.cleanup()


def prepare(env,**changes):
    service,view,sessions,repo=env
    return repo.prepare(view['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker',**changes)


def test_prepare_durable_intent_and_permit_reopen_exact_replay(env):
    service,view,sessions,repo=env
    result=prepare(env);assert result['state']=='prepared'
    reopened=OperationRepository(Service(session_factory=sessions))
    assert reopened.get(result['id'],'t1')['request']==view['payload']
    assert prepare(env)['id']==result['id']
    with sessions() as db:assert len(db.scalars(select(ApprovalEffectRow)).all())==1


def test_epoch_activation_no_boolean_or_environment_flag_authority(env,monkeypatch):
    result=prepare(env);repo=env[3]
    monkeypatch.setenv('ATLAS_M24_CUTOVER_ENABLED','1')
    with pytest.raises(DispatchRefused):repo.claim(result['id'],'t1',protocol_epoch=2)
    with pytest.raises(DispatchRefused):repo.claim(result['id'],'t1',protocol_epoch=1)
    assert repo.get(result['id'],'t1')['state']=='prepared'


def test_foreign_and_changed_binding_refuse_without_new_permit(env):
    result=prepare(env);repo=env[3]
    with pytest.raises(KeyError):repo.get(result['id'],'foreign')
    with pytest.raises(ApprovalConflictError):prepare(env,provider_key='changed')
    with pytest.raises(ApprovalConflictError):env[3].prepare(env[1]['id'],'foreign',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')


def test_intent_failure_rolls_back_permit_and_audit(env,monkeypatch):
    from sqlalchemy.orm import Session
    original=Session.add
    def fail(self,value,*a,**kw):
        if isinstance(value,OperationRow):raise RuntimeError('intent insert fixture failure')
        return original(self,value,*a,**kw)
    monkeypatch.setattr(Session,'add',fail)
    with pytest.raises(RuntimeError):prepare(env)
    with env[2]() as db:
        assert db.scalar(select(ApprovalEffectRow)) is None
        assert db.scalar(select(OperationRow)) is None
    assert [e['event'] for e in env[0].audit(env[1]['id'])]==['created','approved']


def test_two_concurrent_sql_handles_reserve_one_exact_operation(env):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    barrier=threading.Barrier(2)
    def worker():
        local=OperationRepository(Service(session_factory=env[2]));barrier.wait(5)
        return local.prepare(env[1]['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')['id']
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:worker(),range(2)))
    assert len(set(results))==1
    with env[2]() as db:
        assert len(db.scalars(select(OperationRow)).all())==1
        assert len(db.scalars(select(ApprovalEffectRow)).all())==1


@pytest.mark.parametrize('point',['before-transaction','after-insert','after-commit'])
def test_real_external_sigkill_reservation_boundaries(env,tmp_path,point):
    import subprocess,sys,os,time,signal
    from pathlib import Path
    ready=tmp_path/'ready';dburl=str(env[2].kw['bind'].url)
    script=r'''
import os,time
from pathlib import Path
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from app.modules.m00_approval_center.service import Service
from app.modules.m24_billing.write_ahead import OperationRepository
engine=create_engine(os.environ['DATABASE'])
svc=Service(session_factory=sessionmaker(bind=engine,expire_on_commit=False));repo=OperationRepository(svc)
def barrier():
    with open(os.environ['READY'],'w') as f:f.write('ready');f.flush();os.fsync(f.fileno())
    while True:time.sleep(.05)
point=os.environ['POINT']
if point=='before-transaction':barrier()
if point=='after-insert':
    def hook(conn,cursor,statement,params,context,many):
        if statement.lstrip().startswith('INSERT INTO m24_provider_operations'):barrier()
    event.listen(engine,'after_cursor_execute',hook)
repo.prepare(os.environ['APPROVAL'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')
if point=='after-commit':barrier()
'''
    process=subprocess.Popen([sys.executable,'-c',script],env={**os.environ,'DATABASE':dburl,'READY':str(ready),'POINT':point,'APPROVAL':env[1]['id']})
    try:
        until=time.monotonic()+10
        while not ready.exists() and time.monotonic()<until:
            assert process.poll() is None;time.sleep(.02)
        assert ready.exists()
        os.kill(process.pid,signal.SIGKILL);assert process.wait(5)==-signal.SIGKILL
        with env[2]() as db:
            operations=db.scalars(select(OperationRow)).all();permits=db.scalars(select(ApprovalEffectRow)).all()
            assert len(operations)==len(permits)==(1 if point=='after-commit' else 0)
        result=prepare(env);assert result['state']=='prepared'
        with pytest.raises(DispatchRefused):env[3].claim(result['id'],'t1',protocol_epoch=2)
    finally:
        if process.poll() is None:process.kill();process.wait(5)


def test_populated_migration_quarantines_legacy_and_locks_epoch(tmp_path):
    import subprocess,sys,os
    from pathlib import Path
    from sqlalchemy import text
    database=tmp_path/'migration.db';root=Path(__file__).resolve().parents[2]
    runenv={**os.environ,'ATLAS_DATABASE_URL':f'sqlite:///{database}','PYTHONPATH':'backend'}
    result=subprocess.run([sys.executable,'-m','alembic','upgrade','20261008_m20_chroma_jobs'],cwd=root,env=runenv,capture_output=True,text=True,timeout=25)
    assert result.returncode==0,result.stderr
    engine=create_engine(f'sqlite:///{database}');svc=Service(session_factory=sessionmaker(bind=engine,expire_on_commit=False))
    view=svc.submit(module_id=24,action_type='issue_invoice',payload={'tenant_id':'t1'},user_id='t1');svc.decide(view['id'],ApprovalStatus.APPROVED,'owner')
    result=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=runenv,capture_output=True,text=True,timeout=25)
    assert result.returncode==0,result.stderr
    with engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM m24_provider_operations')).scalar()==0
        assert db.execute(text('SELECT protocol_epoch FROM m24_dispatch_cutover')).scalar()==0
        assert db.execute(text('SELECT classification FROM m24_legacy_quarantine')).scalar()=='legacy-unknown-under24h'
    result=subprocess.run([sys.executable,'-m','alembic','downgrade','20261008_m20_chroma_jobs'],cwd=root,env=runenv,capture_output=True,text=True,timeout=25)
    assert result.returncode!=0 and 'destructive downgrade refused' in result.stderr
    engine.dispose()


def test_legacy_execute_entrypoints_fail_closed_before_provider_even_with_env_flag(monkeypatch):
    import asyncio
    from app.modules.m24_billing.service import Service as BillingService
    calls=[]
    class Provider:
        async def create_checkout(self,*a):calls.append(1);return {}
        async def create_invoice(self,*a):calls.append(1);return {}
    monkeypatch.setenv('ATLAS_M24_CUTOVER_ENABLED','1')
    class Repo:
        def approval(self,aid):return {'status':'approved','payload':{'tenant_id':'tenant','plan':{'id':'pro'},'success_url':'https://example.test/s','cancel_url':'https://example.test/c','effect':'create_draft_invoice'}}
    service=BillingService(None,Repo(),Provider())
    for name in ('execute_checkout','execute_approved'):
        with pytest.raises(DispatchRefused):asyncio.run(getattr(service,name)('approval','tenant'))
    assert calls==[]


def test_quarantined_legacy_approval_cannot_become_ready(env):
    from app.modules.m24_billing.write_ahead import LegacyQuarantineRow
    with env[2].begin() as db:
        db.add(LegacyQuarantineRow(approval_id=env[1]['id'],tenant_id='t1',classification='legacy-unknown-under24h',inventoried_at=datetime.now(timezone.utc)))
    with pytest.raises(DispatchRefused,match='legacy'):prepare(env)
    with env[2]() as db:assert db.scalar(select(ApprovalEffectRow)) is None


def test_changed_authoritative_approval_payload_conflicts_with_existing_intent(env):
    from sqlalchemy import update
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    prepare(env)
    with env[2].begin() as db:db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==env[1]['id']).values(payload={'changed':True}))
    with pytest.raises(ApprovalConflictError):prepare(env)


def test_claim_api_cannot_receive_boolean_check_attestation(env):
    result=prepare(env)
    with pytest.raises(TypeError):env[3].claim(result['id'],'t1',protocol_epoch=2,credentials_revoked=True)
    with pytest.raises(DispatchRefused):env[3].claim(result['id'],'t1',protocol_epoch=True)


def test_full_postgres_migration_stays_locked_and_empty_downgrade(tmp_path):
    import pgserver,subprocess,sys,os
    from pathlib import Path
    from sqlalchemy import text,inspect
    server=pgserver.get_server(tmp_path/'migrated-pg',cleanup_mode='stop')
    uri=server.get_uri().replace('postgresql://','postgresql+psycopg://');root=Path(__file__).resolve().parents[2]
    runenv={**os.environ,'ATLAS_DATABASE_URL':uri,'PYTHONPATH':'backend'}
    result=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=runenv,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    engine=create_engine(uri)
    with engine.connect() as db:assert db.execute(text('SELECT protocol_epoch FROM m24_dispatch_cutover')).scalar()==0
    assert 'm24_provider_operations' in inspect(engine).get_table_names()
    result=subprocess.run([sys.executable,'-m','alembic','downgrade','20261008_m20_chroma_jobs'],cwd=root,env=runenv,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert 'm24_provider_operations' not in inspect(engine).get_table_names()
    engine.dispose()
    server.cleanup()


def test_fabricated_active_database_row_is_not_checked_credential_evidence(env):
    from app.modules.m24_billing.write_ahead import CutoverRow
    result=prepare(env)
    with env[2].begin() as db:
        db.add(CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='a'*64,verified_at=datetime.now(timezone.utc)))
    with pytest.raises(DispatchRefused,match='checked'):env[3].claim(result['id'],'t1',protocol_epoch=2)
    assert env[3].get(result['id'],'t1')['state']=='prepared'


def test_expired_approval_reservation_refuses_without_new_rows(env):
    from sqlalchemy import update
    from datetime import timedelta
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    with env[2].begin() as db:db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==env[1]['id']).values(expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)))
    with pytest.raises(ApprovalConflictError):prepare(env)
    with env[2]() as db:
        assert db.scalar(select(OperationRow)) is None
        assert db.scalar(select(ApprovalEffectRow)) is None
