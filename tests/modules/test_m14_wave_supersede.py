from app.modules.m14_project_builder.reviewed_continuation import ReviewRow,ContinuationRow,ContinuationKeyRow
"""Human admin unblock, two approvals, durable evidence, never automatic resume."""
import asyncio
import pytest
from sqlalchemy import select
from app.auth.context import TenantContext
from app.core.models import ApprovalStatus
from app.modules.m14_project_builder.wave_supersede import *
from test_m14_sandbox_wave import env,approved,request
ADMIN=TenantContext('t','admin',frozenset({'atlas-admin'}))
OWNER=TenantContext('t','owner',frozenset())

def pair(svc,completed=False):
    prior,aid=approved(svc)
    if completed:asyncio.run(svc.execute('t','owner',prior))
    else:svc.claim('t','owner',prior)
    new,aid2=approved(svc)
    return prior,new,aid2

def test_unknown_admin_supersede_new_execution_and_history(env):
    svc,sessions,_=env;prior,new,aid=pair(svc);service=WaveSupersedeService(svc)
    proposed=service.propose(ADMIN,prior,new);sid=proposed['id']
    assert proposed['payload']['evidence']=={'classification':'unknown / no S6 evidence','sha256':None}
    with pytest.raises(WaveConflict):svc.claim('t','owner',new)
    with pytest.raises(WaveForbidden):service.decide(OWNER,sid,'approved')
    service.decide(ADMIN,sid,'approved');service.apply(ADMIN,sid)
    result=asyncio.run(svc.execute('t','owner',new))
    assert result['state']=='awaiting_review' and not result['result']['all_dag_completed']
    assert service.history(ADMIN,'p')[0]['version']==1
    assert service.history(ADMIN,'p')[0]['admin_actor']=='admin'
    with sessions() as db:
        assert db.get(SandboxWaveRow,prior).claim_key is not None
        assert db.get(SandboxWaveRow,prior).state=='superseded'
        assert len(list(db.scalars(select(ApprovalEffectRow))))==3 # prior/new/supersede separately charged
    with pytest.raises(WaveConflict):service.apply(ADMIN,sid)
    with pytest.raises(WaveConflict):svc.claim('t','owner',new)


def test_verified_s6_and_artifact_tamper_refused(env):
    svc,sessions,_=env;prior,new,_=pair(svc,True);service=WaveSupersedeService(svc)
    sid=service.propose(ADMIN,prior,new)['id'];service.decide(ADMIN,sid,'approved')
    with sessions.begin() as db:
        artifact=db.scalar(select(SandboxWaveArtifactRow).where(SandboxWaveArtifactRow.wave_id==prior));artifact.content_base64='Yg=='
    with pytest.raises(WaveConflict,match='artifact digest'):service.apply(ADMIN,sid)
    with sessions() as db:assert db.get(WaveSupersedeRow,sid).state=='approved'


def test_raw_approval_never_admin_receipt(env):
    svc,_,_=env;prior,new,_=pair(svc);service=WaveSupersedeService(svc)
    proposed=service.propose(ADMIN,prior,new)
    svc.gate.decide(proposed['approval_id'],ApprovalStatus.APPROVED,decided_by='admin')
    with pytest.raises(WaveConflict,match='role-bound'):service.apply(ADMIN,proposed['id'])


def test_supersede_does_not_replace_execution_approval(env):
    svc,_,_=env;prior,_=approved(svc);svc.claim('t','owner',prior)
    new=svc.draft('t','owner','p',request())['id'];svc.submit('t','owner',new)
    service=WaveSupersedeService(svc);sid=service.propose(ADMIN,prior,new)['id']
    service.decide(ADMIN,sid,'approved');service.apply(ADMIN,sid)
    with pytest.raises(WaveConflict,match='live approved'):svc.claim('t','owner',new)


def test_supersede_transaction_rollback(env,monkeypatch):
    svc,sessions,_=env;prior,new,_=pair(svc);service=WaveSupersedeService(svc);sid=service.propose(ADMIN,prior,new)['id'];service.decide(ADMIN,sid,'approved')
    original=svc.gate.consume_effect
    def fault(*a,**kw):original(*a,**kw);kw['_session'].flush();raise RuntimeError('fault')
    monkeypatch.setattr(svc.gate,'consume_effect',fault)
    with pytest.raises(RuntimeError):service.apply(ADMIN,sid)
    with sessions() as db:
        assert db.get(SandboxWaveRow,prior).state=='claimed'
        assert not db.scalar(select(WaveKeyVersionRow))
        assert db.get(WaveSupersedeRow,sid).state=='approved'


def test_slow_worker_finalization_fenced(env,monkeypatch):
    svc,sessions,_=env;prior,_=approved(svc);original=svc._task
    def supersede_during_task(*a,**kw):
        new,_=approved(svc);service=WaveSupersedeService(svc)
        sid=service.propose(ADMIN,prior,new)['id'];service.decide(ADMIN,sid,'approved');service.apply(ADMIN,sid)
        return original(*a,**kw)
    monkeypatch.setattr(svc,'_task',supersede_during_task)
    with pytest.raises(WaveConflict,match='publication fenced'):asyncio.run(svc.execute('t','owner',prior))
    with sessions() as db:
        assert db.get(SandboxWaveRow,prior).state=='superseded'
        assert not list(db.scalars(select(SandboxWaveTaskRow).where(SandboxWaveTaskRow.wave_id==prior)))


def test_oidc_admin_routes_and_generic_denial(env,oidc_auth_headers,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m14_project_builder import routes
    from app.modules.m00_approval_center import routes as m00
    svc,_,_=env;prior,new,_=pair(svc)
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    app=FastAPI();app.include_router(routes.router);app.include_router(m00.router)
    app.dependency_overrides[routes.get_wave_service]=lambda:svc
    app.dependency_overrides[m00.get_service]=lambda:svc.gate
    with TestClient(app) as client:
        owner=oidc_auth_headers('t','owner')
        assert client.post('/project-builder/wave-supersedes',headers=owner,json={'prior_wave_id':prior,'new_wave_id':new}).status_code==403
        headers=oidc_auth_headers('t','admin',roles=['atlas-admin'])
        p=client.post('/project-builder/wave-supersedes',headers=headers,json={'prior_wave_id':prior,'new_wave_id':new});assert p.status_code==202
        sid=p.json()['id'];aid=p.json()['approval_id']
        assert client.post('/approval-center/requests/'+aid+'/decision',headers=headers,json={'decision':'approved','decided_by':'admin'}).status_code==403
        assert client.post('/project-builder/wave-supersedes/'+sid+'/decision',headers=headers,json={'decision':'approved'}).status_code==200
        assert client.post('/project-builder/wave-supersedes/'+sid+'/apply',headers=headers).status_code==200

@pytest.mark.parametrize('fault',['denied','expired','new_digest','prior_digest','partial','version'])
def test_supersede_rejects_drift_denial_expiry_partial(env,fault):
    from datetime import timedelta
    svc,sessions,_=env;prior,new,_=pair(svc);service=WaveSupersedeService(svc);proposed=service.propose(ADMIN,prior,new);sid=proposed['id'];service.decide(ADMIN,sid,'denied' if fault=='denied' else 'approved')
    with sessions.begin() as db:
        if fault=='expired':db.get(ApprovalRequestRow,proposed['approval_id']).expires_at=svc.gate._clock()-timedelta(seconds=1)
        if fault=='new_digest':db.get(SandboxWaveRow,new).digest='0'*64
        if fault=='prior_digest':db.get(SandboxWaveRow,prior).digest='0'*64
        if fault=='partial':db.add(SandboxWaveTaskRow(id=str(uuid.uuid4()),wave_id=prior,task_id='a',receipt={}))
        if fault=='version':db.add(WaveKeyVersionRow(id=str(uuid.uuid4()),project_key=project_key(db.get(SandboxWaveRow,prior)),version=1,prior_wave_id=prior,new_wave_id='other',admin_actor='admin',supersede_id='other',evidence={},created_at='now'))
    with pytest.raises(WaveConflict):service.apply(ADMIN,sid)
    with sessions() as db:assert db.get(SandboxWaveRow,prior).state=='claimed'


def test_verified_s6_success_hash_and_no_dependent_progress(env):
    svc,_,_=env;prior,new,_=pair(svc,True);service=WaveSupersedeService(svc);p=service.propose(ADMIN,prior,new)
    assert p['payload']['evidence']['classification']=='verified S6' and len(p['payload']['evidence']['sha256'])==64
    service.decide(ADMIN,p['id'],'approved');service.apply(ADMIN,p['id'])
    result=asyncio.run(svc.execute('t','owner',new));assert [x['task_id'] for x in result['result']['tasks']]==['a']


def test_fresh_service_reads_version_history_no_memory(env):
    from app.modules.m14_project_builder.sandbox_wave import SandboxWaveService
    svc,sessions,root=env;prior,new,_=pair(svc);service=WaveSupersedeService(svc);p=service.propose(ADMIN,prior,new);service.decide(ADMIN,p['id'],'approved');service.apply(ADMIN,p['id'])
    fresh=SandboxWaveService(sessions,str(root));assert WaveSupersedeService(fresh).history(ADMIN,'p')[0]['new_wave_id']==new
    assert asyncio.run(fresh.execute('t','owner',new))['state']=='awaiting_review'


def test_supersede_sqlite_concurrent_apply_once(env):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.exc import OperationalError,IntegrityError
    svc,sessions,_=env;prior,new,_=pair(svc);service=WaveSupersedeService(svc);p=service.propose(ADMIN,prior,new);service.decide(ADMIN,p['id'],'approved')
    def apply():
        try:service.apply(ADMIN,p['id']);return 'applied'
        except (WaveConflict,OperationalError,IntegrityError):return 'refused'
    with ThreadPoolExecutor(2) as pool:assert sorted(pool.map(lambda _:apply(),range(2)))==['applied','refused']
    with sessions() as db:assert len(list(db.scalars(select(WaveKeyVersionRow))))==1


def test_supersede_migration_sqlite_pg_and_pg_claim_apply(tmp_path):
    import importlib.util,pgserver,tempfile,shutil
    from pathlib import Path
    from sqlalchemy import create_engine,inspect
    from sqlalchemy.orm import sessionmaker
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    from app.modules.m14_project_builder.sandbox_wave import SandboxWaveService
    from app.modules.m14_project_builder.sql_repository import ProjectRow
    from app.modules.m14_project_builder.schemas import ProjectPlan,ProjectTask,Budget
    from app.modules.m00_approval_center.impact import ApprovalReviewStateRow
    server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
    pguri=server.get_uri().replace('postgresql://','postgresql+psycopg://')
    spec=importlib.util.spec_from_file_location('migration',Path(__file__).resolve().parents[2]/'migrations/versions/20261010_m14_wave_supersede.py');migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    for uri in ['sqlite:///'+str(tmp_path/'migration.db'),pguri]:
        engine=create_engine(uri)
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade();assert 'm14_wave_key_versions' in inspect(connection).get_table_names();migration.downgrade()
        engine.dispose()
    engine=create_engine(pguri);sessions=sessionmaker(engine,expire_on_commit=False)
    for model in (ReviewRow,ContinuationRow,ContinuationKeyRow,WaveKeyVersionRow,WaveSupersedeRow,ProjectRow,ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow,ApprovalReviewStateRow,SandboxWaveRow,SandboxWaveTaskRow,SandboxWaveArtifactRow):model.__table__.create(engine,checkfirst=True)
    root=Path(tempfile.mkdtemp(prefix='m14-supersede-pg-',dir=Path.home()));root.chmod(0o700)
    try:
        plan=ProjectPlan(goal='demo',tasks=[ProjectTask(id='a',title='write',objective='write result',agent_kind='coder'),ProjectTask(id='b',title='next',objective='dependent task',agent_kind='coder',dependencies=['a'])])
        with sessions.begin() as db:db.add(ProjectRow(tenant_id='t',id='p',goal='demo',brief={},budget=Budget().model_dump(mode='json'),status='planned',revision=1,plan=plan.model_dump(mode='json')))
        svc=SandboxWaveService(sessions,str(root));prior,new,_=pair(svc);service=WaveSupersedeService(svc);p=service.propose(ADMIN,prior,new);service.decide(ADMIN,p['id'],'approved')
        original=svc.gate.consume_effect
        def fault(*a,**kw):original(*a,**kw);kw['_session'].flush();raise RuntimeError('rollback')
        svc.gate.consume_effect=fault
        with pytest.raises(RuntimeError):service.apply(ADMIN,p['id'])
        with sessions() as db:assert db.get(SandboxWaveRow,prior).state=='claimed' and not db.scalar(select(WaveKeyVersionRow))
        svc.gate.consume_effect=original
        from concurrent.futures import ThreadPoolExecutor
        from sqlalchemy.exc import IntegrityError
        def apply():
            try:service.apply(ADMIN,p['id']);return 'applied'
            except (WaveConflict,IntegrityError):return 'refused'
        with ThreadPoolExecutor(2) as pool:assert sorted(pool.map(lambda _:apply(),range(2)))==['applied','refused']
        assert asyncio.run(svc.execute('t','owner',new))['state']=='awaiting_review'
        third,_=approved(svc);p=service.propose(ADMIN,new,third);service.decide(ADMIN,p['id'],'approved');service.apply(ADMIN,p['id'])
        from threading import Event
        entered=Event();release=Event();original_task=svc._task
        def slow_task(*a,**kw):
            entered.set();assert release.wait(15);return original_task(*a,**kw)
        svc._task=slow_task
        with ThreadPoolExecutor(1) as pool:
            pending=pool.submit(lambda:asyncio.run(svc.execute('t','owner',third)))
            assert entered.wait(15)
            fourth,_=approved(svc);p=service.propose(ADMIN,third,fourth);service.decide(ADMIN,p['id'],'approved');service.apply(ADMIN,p['id'])
            release.set()
            with pytest.raises(WaveConflict,match='publication fenced'):pending.result(timeout=20)
        with sessions() as db:
            assert db.get(SandboxWaveRow,third).state=='superseded'
            assert not db.scalar(select(SandboxWaveTaskRow).where(SandboxWaveTaskRow.wave_id==third))
            assert not db.scalar(select(SandboxWaveArtifactRow).where(SandboxWaveArtifactRow.wave_id==third))
        svc._task=original_task
        assert asyncio.run(svc.execute('t','owner',fourth))['state']=='awaiting_review'
    finally:engine.dispose();shutil.rmtree(root)

@pytest.mark.parametrize('limit,value',[('max_agent_calls',1),('max_runtime_seconds',15),('max_cost_usd',0)])
def test_cumulative_reservations_never_refunded(env,limit,value):
    from app.modules.m14_project_builder.sql_repository import ProjectRow
    svc,sessions,_=env
    with sessions.begin() as db:
        project=db.scalar(select(ProjectRow));project.budget={**project.budget,limit:value}
    prior,new,_=pair(svc);service=WaveSupersedeService(svc);p=service.propose(ADMIN,prior,new)
    before=svc.get('t','owner',prior)['payload']
    service.decide(ADMIN,p['id'],'approved');service.apply(ADMIN,p['id'])
    if limit=='max_cost_usd': # genuine free sandbox cost is0, not an invented charge
        svc.claim('t','owner',new)
    else:
        with pytest.raises(WaveConflict,match='cumulative'):svc.claim('t','owner',new)
        with sessions() as db:
            assert db.get(SandboxWaveRow,new).state=='awaiting_approval'
            assert not db.scalar(select(ApprovalEffectRow).where(ApprovalEffectRow.approval_id==db.get(SandboxWaveRow,new).approval_id))
    assert svc.get('t','owner',prior)['payload']==before


def test_supersede_ready_set_and_tenant_ownership_refused(env):
    svc,sessions,_=env;prior,new,_=pair(svc);service=WaveSupersedeService(svc)
    with pytest.raises(WaveForbidden):service.propose(TenantContext('other','admin',frozenset({'atlas-admin'})),prior,new)
    with sessions.begin() as db:
        row=db.get(SandboxWaveRow,new);row.payload={**row.payload,'ready_task_ids':['b']};row.digest=digest(row.payload)
    with pytest.raises(WaveConflict,match='initially-ready'):service.propose(ADMIN,prior,new)


def test_approved_state_alone_never_role_receipt(env):
    svc,sessions,_=env;prior,new,_=pair(svc);service=WaveSupersedeService(svc);p=service.propose(ADMIN,prior,new)
    svc.gate.decide(p['approval_id'],ApprovalStatus.APPROVED,decided_by='admin')
    with sessions.begin() as db:
        row=db.get(WaveSupersedeRow,p['id']);row.state='approved';row.approver_actor='admin'
    with pytest.raises(WaveConflict,match='role-bound'):service.apply(ADMIN,p['id'])

@pytest.fixture
def pg_env(tmp_path):
    import pgserver,tempfile,shutil
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.modules.m14_project_builder.sandbox_wave import SandboxWaveService
    from app.modules.m14_project_builder.sql_repository import ProjectRow
    from app.modules.m14_project_builder.schemas import ProjectPlan,ProjectTask,Budget
    from app.modules.m00_approval_center.impact import ApprovalReviewStateRow
    server=pgserver.get_server(tmp_path/'pg-race',cleanup_mode='stop')
    engine=create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    sessions=sessionmaker(engine,expire_on_commit=False)
    for model in (ReviewRow,ContinuationRow,ContinuationKeyRow,WaveKeyVersionRow,WaveSupersedeRow,ProjectRow,ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow,ApprovalReviewStateRow,SandboxWaveRow,SandboxWaveTaskRow,SandboxWaveArtifactRow):model.__table__.create(engine,checkfirst=True)
    root=Path(tempfile.mkdtemp(prefix='m14-fence-pg-',dir=Path.home()));root.chmod(0o700)
    plan=ProjectPlan(goal='demo',tasks=[ProjectTask(id='a',title='write',objective='write result',agent_kind='coder'),ProjectTask(id='b',title='next',objective='dependent task',agent_kind='coder',dependencies=['a'])])
    with sessions.begin() as db:db.add(ProjectRow(tenant_id='t',id='p',goal='demo',brief={},budget=Budget().model_dump(mode='json'),status='planned',revision=1,plan=plan.model_dump(mode='json')))
    try:yield SandboxWaveService(sessions,str(root)),sessions,engine
    finally:engine.dispose();shutil.rmtree(root)


def test_finalize_read_publication_interleaving_pg_lock(pg_env,monkeypatch):
    """Apply reaches the lock while current() has read but publication is paused."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event,current_thread
    from sqlalchemy import event,text
    import time
    import app.modules.m14_project_builder.wave_supersede as module
    svc,sessions,engine=pg_env;prior,_=approved(svc);new,_=approved(svc)
    entered=Event();release=Event();apply_select=Event();pid=[];sid=[]
    original=module.current
    def barrier(db,row):
        result=original(db,row)
        if current_thread().name.startswith('finalize') and row.state=='claimed':
            entered.set();assert release.wait(15)
        return result
    monkeypatch.setattr(module,'current',barrier)
    def before(conn,cursor,statement,parameters,context,executemany):
        if current_thread().name.startswith('apply') and 'FOR UPDATE' in statement and 'm14_sandbox_waves' in statement:
            pid.append(conn.connection.driver_connection.info.backend_pid);apply_select.set()
    event.listen(engine,'before_cursor_execute',before)
    try:
        with ThreadPoolExecutor(1,thread_name_prefix='finalize') as final_pool,ThreadPoolExecutor(1,thread_name_prefix='apply') as apply_pool:
            pending=final_pool.submit(lambda:asyncio.run(svc.execute('t','owner',prior)))
            assert entered.wait(15)
            service=WaveSupersedeService(svc);p=service.propose(ADMIN,prior,new);sid.append(p['id']);service.decide(ADMIN,p['id'],'approved')
            applying=apply_pool.submit(service.apply,ADMIN,p['id'])
            assert apply_select.wait(15)
            blocked=False;deadline=time.monotonic()+5
            with engine.connect() as observer:
                while time.monotonic()<deadline:
                    observer.rollback()
                    blocked=bool(observer.execute(text('select cardinality(pg_blocking_pids(:pid)) > 0'),{'pid':pid[0]}).scalar())
                    if blocked or applying.done():break
                    time.sleep(.01)
            if not blocked:
                applying.result(timeout=20) # mutation allows commit between read/publication
                release.set()
                try:pending.result(timeout=20)
                except WaveConflict:pass # CAS-only defense still rejects stale publication
                with sessions() as db:
                    assert db.get(SandboxWaveRow,prior).state=='superseded','old worker overwrote superseded after current() read'
                    assert not db.scalar(select(SandboxWaveTaskRow).where(SandboxWaveTaskRow.wave_id==prior))
                pytest.fail('supersede was not blocked at old worker read/publication boundary')
            release.set();assert pending.result(timeout=20)['state']=='awaiting_review'
            with pytest.raises(WaveConflict,match='evidence or version changed'):applying.result(timeout=20)
        with sessions() as db:
            assert db.get(SandboxWaveRow,prior).state=='awaiting_review'
            assert db.get(WaveSupersedeRow,sid[0]).state=='approved'
            assert not db.scalar(select(WaveKeyVersionRow))
    finally:release.set();event.remove(engine,'before_cursor_execute',before)


def test_finalize_zero_row_cas_refused_pg(pg_env):
    """Real PG UPDATE affects zero rows; rowcount must abort all publication."""
    from sqlalchemy import event
    svc,sessions,engine=pg_env;prior,_=approved(svc);hit=[]
    def zero(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith('UPDATE m14_sandbox_waves SET state=') and parameters.get('state')=='finalizing':
            hit.append(True);statement=statement+' AND 1=0'
        return statement,parameters
    event.listen(engine,'before_cursor_execute',zero,retval=True)
    try:
        with pytest.raises(WaveConflict,match='publication fenced'):asyncio.run(svc.execute('t','owner',prior))
        assert hit
        with sessions() as db:
            assert db.get(SandboxWaveRow,prior).state=='claimed'
            assert db.get(SandboxWaveRow,prior).result is None
            assert not db.scalar(select(SandboxWaveTaskRow)) and not db.scalar(select(SandboxWaveArtifactRow))
    finally:event.remove(engine,'before_cursor_execute',zero)


def test_preapproved_sibling_cannot_claim_before_or_after_supersede(env):
    """Only the admin-selected new wave may claim the new key version.

    Mutation evidence (auditor): removing the `version.new_wave_id!=row.id`
    check in SandboxWaveService.claim lets the sibling claim after supersede.
    """
    svc,sessions,_=env;prior,new,_=pair(svc);sibling,_=approved(svc);service=WaveSupersedeService(svc)
    with pytest.raises(WaveConflict):svc.claim('t','owner',sibling)
    p=service.propose(ADMIN,prior,new);service.decide(ADMIN,p['id'],'approved');service.apply(ADMIN,p['id'])
    with pytest.raises(WaveConflict):svc.claim('t','owner',sibling)
    svc.claim('t','owner',new)
