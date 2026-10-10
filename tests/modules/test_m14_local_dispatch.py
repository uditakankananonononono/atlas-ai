"""Actual bounded local OS workers, not1000 deployment evidence."""
import os,json,tempfile,shutil,uuid,subprocess,sys,importlib.util
from pathlib import Path
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select,create_engine,inspect,func
from sqlalchemy.orm import sessionmaker
from app.auth.context import TenantContext
from app.core.models import ApprovalStatus
from app.modules.m14_project_builder.local_dispatch import *
from app.modules.m14_project_builder.builder_admission import *
from app.modules.m14_project_builder.sandbox_wave import *
from app.modules.m14_project_builder.reviewed_continuation import ReviewRow,ContinuationRow,ContinuationKeyRow
from app.modules.m14_project_builder.wave_supersede import WaveKeyVersionRow,WaveSupersedeRow
from app.modules.m14_project_builder.schemas import ProjectPlan,ProjectTask,Budget
from app.modules.m00_approval_center.impact import ApprovalReviewStateRow
OWNER=TenantContext('t','owner')
TABLES=(ProjectRow,SandboxWaveRow,SandboxWaveTaskRow,SandboxWaveArtifactRow,ReviewRow,ContinuationRow,ContinuationKeyRow,WaveKeyVersionRow,WaveSupersedeRow,ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow,ApprovalReviewStateRow,*MODELS,LocalDispatchPoolRow,LocalDispatchJobRow)
@pytest.fixture(params=['sqlite','pg'])
def env(request,tmp_path,monkeypatch):
    if request.param=='pg':
        import pgserver
        server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');uri=server.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri='sqlite:///'+str(tmp_path/'dispatch.db')
    e=create_engine(uri);s=sessionmaker(e,expire_on_commit=False)
    for model in TABLES:model.__table__.create(e)
    with s.begin() as db:
        db.add(BuilderPoolRow(id=1,epoch=0,limits=dict(GLOBAL_LIMITS),used=zeros()));db.add(LocalDispatchPoolRow(id=1,policy=dict(POLICY)))
    root=Path(tempfile.mkdtemp(prefix='atlas-local-worker-',dir=Path.home()));root.chmod(0o700)
    monkeypatch.setenv('ATLAS_M14_SANDBOX_BACKEND','bubblewrap')
    monkeypatch.setenv('ATLAS_M14_LOCAL_DISPATCH','1')
    svc=LocalDispatchService(s,str(root));svc.waves._probe()
    yield svc,s,uri,root
    e.dispose();shutil.rmtree(root)

def prepared(svc,sessions,ctx=OWNER,code="open('/output/result.txt','w').write('local product executed')",n=2,execute_approved=True):
    pid=str(uuid.uuid4());plan=ProjectPlan(goal='local worker',tasks=[ProjectTask(id=str(i),title='write',objective='write output',agent_kind='coder') for i in range(n)])
    with sessions.begin() as db:db.add(ProjectRow(tenant_id=ctx.tenant_id,id=pid,goal='local',brief={},budget=Budget().model_dump(mode='json'),status='planned',revision=1,plan=plan.model_dump(mode='json')))
    wave=svc.waves.draft(ctx.tenant_id,ctx.actor_id,pid,WaveDraft(tasks={str(i):TaskCode(code=code) for i in range(n)},max_parallel=n,timeout_seconds=10,memory_mb=256))
    batch=svc.admission.propose(ctx,AdmissionRequest(wave_ids=[wave['id']],runtime_seconds=20))
    svc.admission.decide(ctx,batch['id'],'approved');svc.admission.reserve(ctx,batch['id'])
    approval=svc.waves.submit(ctx.tenant_id,ctx.actor_id,wave['id'])
    if execute_approved:svc.waves.gate.decide(approval['approval_id'],ApprovalStatus.APPROVED,decided_by=ctx.actor_id)
    return batch['id'],wave['id']
def queued(svc,sessions,**kw):
    b,w=prepared(svc,sessions,**kw);return svc.enqueue(OWNER,b,w)['id']

def test_actual_two_os_workers_four_sandbox_outputs(env):
    svc,sessions,uri,root=env;ids=[queued(svc,sessions,code="import time;time.sleep(1);open('/output/result.txt','w').write('overlap')") for _ in range(2)]
    # Keep a third admitted wave untouched, proving dispatch is a real selection.
    b,w=prepared(svc,sessions)
    results=run_local_pool(uri,str(root),OWNER,ids)
    assert len(results)==2 and all(r['state']=='completed' and r['result']['review_required'] for r in results)
    assert len({r['worker_id'] for r in results})==2
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(SandboxWaveTaskRow))==4
        receipts=list(db.scalars(select(SandboxWaveTaskRow)))
        events=[]
        for r in receipts:
            events.extend([(datetime.fromisoformat(r.receipt['started_at']),1),(datetime.fromisoformat(r.receipt['finished_at']),-1)])
        active=0;peak=0
        for at,delta in sorted(events):active+=delta;peak=max(peak,active)
        assert 2<=peak<=4
        assert db.scalar(select(func.count()).select_from(SandboxWaveArtifactRow))==4
        assert db.get(BuilderPoolRow,1).used['slots']==2
        for id in ids:
            job=db.get(LocalDispatchJobRow,id);wave=db.get(SandboxWaveRow,job.wave_id)
            assert wave.state=='awaiting_review' and evidence(db,wave)['classification']=='verified S6'
            assert all(r['execution_state']=='sandbox_executed' and r['exit_code']==0 and r['timed_out'] is False for r in wave.result['tasks'])
        assert db.get(SandboxWaveRow,w).state=='awaiting_approval'
    for id in ids:
        with pytest.raises(WaveConflict):svc.run(OWNER,id,'again')

def test_admission_without_separate_execution_approval_never_enqueues(env):
    svc,sessions,_,_=env;b,w=prepared(svc,sessions,execute_approved=False)
    with pytest.raises(WaveConflict,match='separate'):svc.enqueue(OWNER,b,w)
    with sessions() as db:assert not db.scalar(select(LocalDispatchJobRow.id)) and db.get(SandboxWaveRow,w).state=='awaiting_approval'

def test_atomic_claim_rollback_every_slot_and_wave_permit(env,monkeypatch):
    svc,sessions,_,_=env;id=queued(svc,sessions);original=svc.waves.gate.consume_effect
    def fail(*a,**kw):original(*a,**kw);kw['_session'].flush();raise RuntimeError('transaction fault')
    monkeypatch.setattr(svc.waves.gate,'consume_effect',fail)
    with pytest.raises(RuntimeError):svc.claim(OWNER,id,'w')
    with sessions() as db:
        job=db.get(LocalDispatchJobRow,id);assert job.state=='queued' and job.fence==0
        assert db.get(SandboxWaveRow,job.wave_id).state=='awaiting_approval'
        slots=list(db.scalars(select(BuilderSlotRow)));assert all(s.state=='reserved' and s.fence==0 for s in slots)
        assert db.scalar(select(func.count()).select_from(ApprovalEffectRow))==1

def test_actual_crash_after_job_claim_unknown_no_replay(env):
    svc,sessions,uri,root=env;id=queued(svc,sessions)
    code="""import sys,os,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.auth.context import TenantContext
from app.modules.m14_project_builder.local_dispatch import LocalDispatchService
s=LocalDispatchService(sessionmaker(create_engine(sys.argv[1]),expire_on_commit=False),sys.argv[2]);c=s.claim(TenantContext('t','owner'),sys.argv[3],'crashed');print(json.dumps(c),flush=True);os._exit(27)
"""
    r=subprocess.run([sys.executable,'-c',code,uri,str(root),id],capture_output=True,text=True,timeout=30);assert r.returncode==27,r.stderr
    fresh=LocalDispatchService(sessions,str(root));assert fresh.get(OWNER,id)['outcome_unknown']
    with pytest.raises(WaveConflict):fresh.claim(OWNER,id,'replacement')
    with sessions() as db:
        job=db.get(LocalDispatchJobRow,id);assert db.get(SandboxWaveRow,job.wave_id).state=='claimed'
        assert all(s.state=='claimed' for s in db.scalars(select(BuilderSlotRow))) and db.get(BuilderPoolRow,1).used['slots']==2

def test_pool_cap_two_jobs_and_four_tasks(env):
    svc,sessions,_,_=env;ids=[queued(svc,sessions) for _ in range(3)]
    svc.claim(OWNER,ids[0],'w1');svc.claim(OWNER,ids[1],'w2')
    with pytest.raises(WaveConflict,match='pool exhausted'):svc.claim(OWNER,ids[2],'w3')
    with sessions() as db:assert db.get(LocalDispatchJobRow,ids[2]).state=='queued'

def test_exact_whole_slot_selection_and_owner_drift(env):
    svc,sessions,_,_=env;id=queued(svc,sessions)
    with pytest.raises(WaveForbidden):svc.claim(TenantContext('t','other'),id,'worker')
    with pytest.raises(WaveForbidden):svc.get(TenantContext('u','owner'),id)
    with sessions.begin() as db:
        job=db.get(LocalDispatchJobRow,id);s=db.scalar(select(BuilderSlotRow).where(BuilderSlotRow.batch_id==job.batch_id));s.state='cancelled'
    with pytest.raises(WaveConflict):svc.claim(OWNER,id,'worker')
    with sessions() as db:assert db.get(LocalDispatchJobRow,id).state=='queued'

def test_finish_fence_rejects_before_publication_and_quota_release(env):
    svc,sessions,_,_=env;id=queued(svc,sessions);c=svc.claim(OWNER,id,'worker')
    config=c['payload']['config'];out=[svc.waves._task(t,config['tasks'][t],config) for t in c['payload']['ready_task_ids']]
    for mutation in ['job_token','job_fence','slot_fence','partial','receipt']:
        changed=json.loads(json.dumps(c));outcomes=out
        if mutation=='job_token':changed['token']=str(uuid.uuid4())
        if mutation=='job_fence':changed['fence']+=1
        if mutation=='slot_fence':changed['slots'][0]['fence']+=1
        if mutation=='partial':outcomes=out[:1]
        if mutation=='receipt':outcomes=[({**r,'execution_state':'not_executed'},a) for r,a in out]
        with pytest.raises(WaveConflict):svc.finish(OWNER,id,changed,outcomes)
    with sessions() as db:assert not db.scalar(select(SandboxWaveTaskRow.id)) and db.get(BuilderPoolRow,1).used['slots']==2
    assert svc.finish(OWNER,id,c,out)['state']=='completed'

def test_actual_failure_honest_not_success(env):
    svc,sessions,_,_=env;id=queued(svc,sessions,code="raise RuntimeError('fixture failure')")
    assert svc.run(OWNER,id,'worker')['state']=='failed'
    with sessions() as db:
        assert db.get(BuilderPoolRow,1).used==zeros()
        assert all(s.state=='failed' for s in db.scalars(select(BuilderSlotRow)))

def test_migration_populated_sqlite_pg(env):
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    svc,sessions,_,_=env;e=sessions.kw['bind'];LocalDispatchJobRow.__table__.drop(e);LocalDispatchPoolRow.__table__.drop(e)
    spec=importlib.util.spec_from_file_location('local_mig',Path(__file__).resolve().parents[2]/'migrations/versions/20261010_m14_local_dispatch.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    with e.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):m.upgrade()
    id=queued(svc,sessions)
    with pytest.raises(RuntimeError,match='unsettled'):
        with e.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):m.downgrade()
    svc.run(OWNER,id,'worker')
    with e.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):m.downgrade();m.upgrade()
    with sessions() as db:assert db.scalar(select(func.count()).select_from(ProjectRow))==1

def test_oidc_enqueue_status_and_no_http_worker_run(env,oidc_auth_headers,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m14_project_builder import routes
    svc,sessions,_,_=env;b,w=prepared(svc,sessions);app=FastAPI();app.include_router(routes.router);app.dependency_overrides[routes.get_local_dispatch_service]=lambda:svc
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    with TestClient(app) as client:
        url='/project-builder/local-dispatch/jobs';body=dict(batch_id=b,wave_id=w)
        assert client.post(url,json=body).status_code==401
        assert client.post(url,json=body,headers=oidc_auth_headers('t','other')).status_code==403
        r=client.post(url,json=body,headers=oidc_auth_headers('t','owner'));assert r.status_code==201
        id=r.json()['id'];assert client.get(url+'/'+id,headers=oidc_auth_headers('u','owner')).status_code==403
        assert client.get(url+'/'+id,headers=oidc_auth_headers('t','owner')).json()['state']=='queued'
        assert client.post(url+'/'+id+'/run',headers=oidc_auth_headers('t','owner')).status_code==404

@pytest.mark.parametrize('stage',['enqueue','claim'])
def test_execution_approval_live_owner_payload_guard(env,stage):
    svc,sessions,_,_=env;b,w=prepared(svc,sessions);id=svc.enqueue(OWNER,b,w)['id'] if stage=='claim' else None
    with sessions.begin() as db:
        wave=db.get(SandboxWaveRow,w);a=db.get(ApprovalRequestRow,wave.approval_id);a.approved_by='different-owner'
    with pytest.raises(WaveConflict,match='separate'):
        if id:svc.claim(OWNER,id,'worker')
        else:svc.enqueue(OWNER,b,w)
    with sessions() as db:assert db.get(SandboxWaveRow,w).state=='awaiting_approval'

@pytest.mark.parametrize('mutation',['wave_digest','batch_digest','policy','resources','expiry'])
def test_enqueue_claim_drift_refuses_before_permit(env,mutation):
    svc,sessions,_,_=env;id=queued(svc,sessions)
    with sessions.begin() as db:
        job=db.get(LocalDispatchJobRow,id)
        if mutation=='wave_digest':
            w=db.get(SandboxWaveRow,job.wave_id);w.payload={**w.payload,'change':True};w.digest=digest(w.payload)
        if mutation=='batch_digest':
            b=db.get(BuilderBatchRow,job.batch_id);b.payload={**b.payload,'change':True};b.digest=digest(b.payload)
        if mutation=='policy':db.get(LocalDispatchPoolRow,1).policy={**POLICY,'workers':3}
        if mutation=='resources':
            s=db.scalar(select(BuilderSlotRow).where(BuilderSlotRow.batch_id==job.batch_id));s.resources={**s.resources,'memory_mb':1}
        if mutation=='expiry':
            s=db.scalar(select(BuilderSlotRow).where(BuilderSlotRow.batch_id==job.batch_id));s.expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    with pytest.raises(WaveConflict):svc.claim(OWNER,id,'worker')
    with sessions() as db:
        job=db.get(LocalDispatchJobRow,id);assert job.state=='queued' and db.get(SandboxWaveRow,job.wave_id).state=='awaiting_approval'
        assert db.scalar(select(func.count()).select_from(ApprovalEffectRow))==1

CLAIM_WORKER="""import sys,json,time
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.auth.context import TenantContext
from app.modules.m14_project_builder.local_dispatch import LocalDispatchService,WaveConflict
svc=LocalDispatchService(sessionmaker(create_engine(sys.argv[1]),expire_on_commit=False),sys.argv[2])
Path(sys.argv[4]).touch()
while not Path(sys.argv[5]).exists():time.sleep(.01)
try:r=svc.claim(TenantContext('t','owner'),sys.argv[3],sys.argv[6]);print(json.dumps({'state':'claimed','fence':r['fence']}))
except WaveConflict:print(json.dumps({'state':'refused'}))
"""
def test_real_os_pg_sqlite_same_job_contention_one_claim(env,tmp_path):
    import time
    svc,sessions,uri,root=env;id=queued(svc,sessions);go=tmp_path/'go'
    ps=[]
    for i in range(2):ps.append(subprocess.Popen([sys.executable,'-c',CLAIM_WORKER,uri,str(root),id,str(tmp_path/('ready'+str(i))),str(go),'worker'+str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
    deadline=time.monotonic()+20
    while not all((tmp_path/('ready'+str(i))).exists() for i in range(2)):
        assert time.monotonic()<deadline;time.sleep(.01)
    go.touch();results=[]
    for p in ps:
        out,err=p.communicate(timeout=30);assert p.returncode==0,err;results.append(json.loads(out)['state'])
    assert sorted(results)==['claimed','refused']
    with sessions() as db:
        job=db.get(LocalDispatchJobRow,id);assert job.fence==1 and job.state=='claimed'
        assert db.scalar(select(func.count()).select_from(ApprovalEffectRow))==2
        assert all(s.fence==1 and s.state=='claimed' for s in db.scalars(select(BuilderSlotRow)))

def test_finish_fault_rolls_back_wave_artifacts_job_and_release(env,monkeypatch):
    svc,sessions,_,_=env;id=queued(svc,sessions);c=svc.claim(OWNER,id,'worker');config=c['payload']['config']
    out=[svc.waves._task(t,config['tasks'][t],config) for t in c['payload']['ready_task_ids']]
    original=svc.admission._release
    def fault(*a):original(*a);a[0].flush();raise RuntimeError('release fault')
    monkeypatch.setattr(svc.admission,'_release',fault)
    with pytest.raises(RuntimeError):svc.finish(OWNER,id,c,out)
    with sessions() as db:
        job=db.get(LocalDispatchJobRow,id);assert job.state=='claimed' and db.get(SandboxWaveRow,job.wave_id).state=='claimed'
        assert not db.scalar(select(SandboxWaveTaskRow.id)) and not db.scalar(select(SandboxWaveArtifactRow.id))
        assert db.get(BuilderPoolRow,1).used['slots']==2
    monkeypatch.setattr(svc.admission,'_release',original);assert svc.finish(OWNER,id,c,out)['state']=='completed'

def test_slot_cancel_and_job_expiry_fences_publication_unknown(env):
    svc,sessions,_,_=env;id=queued(svc,sessions);c=svc.claim(OWNER,id,'worker');config=c['payload']['config']
    out=[svc.waves._task(t,config['tasks'][t],config) for t in c['payload']['ready_task_ids']]
    svc.admission.cancel(OWNER,c['slots'][0]['id'])
    with pytest.raises(WaveConflict,match='fence'):svc.finish(OWNER,id,c,out)
    with sessions() as db:
        job=db.get(LocalDispatchJobRow,id);assert job.state=='claimed' and db.get(SandboxWaveRow,job.wave_id).state=='claimed'
        assert db.get(BuilderPoolRow,1).used['slots']==2 and not db.scalar(select(SandboxWaveTaskRow.id))

def test_explicit_operator_opt_in_no_worker_side_effect(env,monkeypatch):
    svc,sessions,uri,root=env;id=queued(svc,sessions);monkeypatch.delenv('ATLAS_M14_LOCAL_DISPATCH',raising=False)
    with pytest.raises(WaveConflict,match='opt-in'):run_local_pool(uri,str(root),OWNER,[id])
    assert svc.get(OWNER,id)['state']=='queued'

def test_job_actor_guard_status_without_batch_fallback(env):
    svc,sessions,_,_=env;id=queued(svc,sessions)
    with pytest.raises(WaveForbidden):svc.get(TenantContext('t','another-owner'),id)

def test_job_token_corruption_cannot_publish_with_valid_slot_token(env):
    svc,sessions,_,_=env;id=queued(svc,sessions);c=svc.claim(OWNER,id,'worker');config=c['payload']['config']
    out=[svc.waves._task(t,config['tasks'][t],config) for t in c['payload']['ready_task_ids']]
    with sessions.begin() as db:db.get(LocalDispatchJobRow,id).token=str(uuid.uuid4())
    with pytest.raises(WaveConflict,match='job fence'):svc.finish(OWNER,id,c,out)
    with sessions() as db:assert not db.scalar(select(SandboxWaveTaskRow.id)) and db.get(BuilderPoolRow,1).used['slots']==2

def test_one_batch_two_waves_can_both_dispatch(env):
    svc,sessions,_,_=env
    b1,w1=prepared(svc,sessions);b2,w2=prepared(svc,sessions)
    # Independently build the real normal combined-batch workflow on two fresh waves.
    ids=[]
    for _ in range(2):
        pid=str(uuid.uuid4());plan=ProjectPlan(goal='combined',tasks=[ProjectTask(id='a',title='write',objective='inert local',agent_kind='coder')])
        with sessions.begin() as db:db.add(ProjectRow(tenant_id='t',id=pid,goal='combined',brief={},budget=Budget().model_dump(mode='json'),status='planned',revision=1,plan=plan.model_dump(mode='json')))
        w=svc.waves.draft('t','owner',pid,WaveDraft(tasks={'a':TaskCode(code="open('/output/result.txt','w').write('combined')")},max_parallel=1,timeout_seconds=10));ids.append(w['id'])
    b=svc.admission.propose(OWNER,AdmissionRequest(wave_ids=ids));svc.admission.decide(OWNER,b['id'],'approved');svc.admission.reserve(OWNER,b['id'])
    jobs=[]
    for w in ids:
        a=svc.waves.submit('t','owner',w);svc.waves.gate.decide(a['approval_id'],ApprovalStatus.APPROVED,decided_by='owner');jobs.append(svc.enqueue(OWNER,b['id'],w)['id'])
    assert svc.run(OWNER,jobs[0],'worker0')['state']=='completed'
    assert svc.run(OWNER,jobs[1],'worker1')['state']=='completed'

# Named audit guard isolation: real SQL/artifacts; explicitly stub downstream
# evidence only where two independent defences otherwise mask the removed guard.
def claimed_outputs(svc,sessions):
    id=queued(svc,sessions);c=svc.claim(OWNER,id,'worker');cfg=c['payload']['config']
    return id,c,[svc.waves._task(t,cfg['tasks'][t],cfg) for t in c['payload']['ready_task_ids']]

def test_r1_job_worker_label_corrupt_valid_slot_label_refuses(env):
    svc,sessions,_,_=env;id,c,out=claimed_outputs(svc,sessions)
    with sessions.begin() as db:db.get(LocalDispatchJobRow,id).worker_id='another-worker'
    with pytest.raises(WaveConflict,match='job fence'):svc.finish(OWNER,id,c,out)
    assert svc.get(OWNER,id)['state']=='claimed'

@pytest.mark.parametrize('field',['payload','digest','current'])
def test_r2_finish_source_guard_isolated(env,monkeypatch,field):
    import app.modules.m14_project_builder.local_dispatch as module
    svc,sessions,_,_=env;id,c,out=claimed_outputs(svc,sessions)
    if field=='payload':c['payload']={**c['payload'],'unreviewed_marker':True}
    elif field=='digest':
        with sessions.begin() as db:
            job=db.get(LocalDispatchJobRow,id);job.payload={**job.payload,'wave_digest':'0'*64};job.digest=digest(job.payload)
    else:monkeypatch.setattr(module,'current',lambda db,w:(1,'other-wave'))
    with pytest.raises(WaveConflict,match='publication source'):svc.finish(OWNER,id,c,out)
    assert svc.get(OWNER,id)['state']=='claimed'

def test_r3_receipt_selection_with_downstream_evidence_isolated(env,monkeypatch):
    import app.modules.m14_project_builder.local_dispatch as module
    svc,sessions,_,_=env;id,c,out=claimed_outputs(svc,sessions)
    # This is a guard pin, NOT a claim that partial durable evidence is valid.
    monkeypatch.setattr(module,'evidence',lambda db,w:{'classification':'verified S6','sha256':'isolated-control'})
    with pytest.raises(WaveConflict,match='complete task receipt'):svc.finish(OWNER,id,c,out[:1])
    with sessions() as db:assert not db.scalar(select(SandboxWaveTaskRow.id)) and db.get(BuilderPoolRow,1).used['slots']==2

def test_r4_nonverified_evidence_classification_refuses(env,monkeypatch):
    import app.modules.m14_project_builder.local_dispatch as module
    svc,sessions,_,_=env;id,c,out=claimed_outputs(svc,sessions)
    # evidence normally raises on invalid records. Isolate its classification
    # boundary without pretending the stub validates any real S6 record.
    monkeypatch.setattr(module,'evidence',lambda db,w:{'classification':'unknown / no S6 evidence','sha256':None})
    with pytest.raises(WaveConflict,match='durable S6'):svc.finish(OWNER,id,c,out)
    with sessions() as db:assert not db.scalar(select(SandboxWaveTaskRow.id)) and db.get(BuilderPoolRow,1).used['slots']==2

def test_r5_nonqueued_job_with_unclaimed_wave_refuses(env):
    svc,sessions,_,_=env;id=queued(svc,sessions)
    with sessions.begin() as db:db.get(LocalDispatchJobRow,id).state='cancelled'
    with pytest.raises(WaveConflict,match='queued one-shot'):svc.claim(OWNER,id,'worker')
    with sessions() as db:assert db.scalar(select(func.count()).select_from(ApprovalEffectRow))==1

@pytest.mark.parametrize('resource,value',[('runtime_seconds',1),('cost_cents',1)])
def test_r6_runtime_and_cost_reservations_refuse(env,resource,value):
    svc,sessions,_,_=env;id=queued(svc,sessions)
    with sessions.begin() as db:
        job=db.get(LocalDispatchJobRow,id);slot=db.scalar(select(BuilderSlotRow).where(BuilderSlotRow.batch_id==job.batch_id));slot.resources={**slot.resources,resource:value}
    with pytest.raises(WaveConflict,match='resources insufficient'):svc.claim(OWNER,id,'worker')
    assert svc.get(OWNER,id)['state']=='queued'

@pytest.mark.parametrize('guard',['batch_state','source','slot_count'])
def test_r7_enqueue_guards_isolated(env,guard):
    svc,sessions,_,_=env;b,w=prepared(svc,sessions,n=1)
    with sessions.begin() as db:
        batch=db.get(BuilderBatchRow,b)
        if guard=='batch_state':batch.state='approved'
        elif guard=='source':
            wave=db.get(SandboxWaveRow,w);wave.payload={**wave.payload,'changed_config_marker':True};wave.digest=digest(wave.payload)
            # Matching new execution approval is not a new admission approval.
            a=db.get(ApprovalRequestRow,wave.approval_id);a.payload=wave.payload
        else:
            s=db.scalar(select(BuilderSlotRow).where(BuilderSlotRow.batch_id==b))
            fields={k:getattr(s,k) for k in ('batch_id','tenant_id','actor_id','wave_id','project_id','task_id','state','resources','expires_at','fence')}
            db.add(BuilderSlotRow(id=str(uuid.uuid4()),work_key=str(uuid.uuid4()),**fields))
    with pytest.raises(WaveConflict):svc.enqueue(OWNER,b,w)
    with sessions() as db:assert not db.scalar(select(LocalDispatchJobRow.id))

# Follow-up named survivors: product bytes unchanged from7f650e04.
def test_pin_resource_cpu_before_local_claim(env):
    svc,sessions,_,_=env;id=queued(svc,sessions)
    with sessions.begin() as db:
        job=db.get(LocalDispatchJobRow,id);slot=db.scalar(select(BuilderSlotRow).where(BuilderSlotRow.batch_id==job.batch_id));slot.resources={**slot.resources,'cpu_units':0}
    with pytest.raises(WaveConflict,match='resources insufficient'):svc.claim(OWNER,id,'worker')
    assert svc.get(OWNER,id)['state']=='queued'

def test_pin_claim_source_after_self_consistent_wave_job_edit(env):
    svc,sessions,_,_=env;id=queued(svc,sessions)
    with sessions.begin() as db:
        job=db.get(LocalDispatchJobRow,id);w=db.get(SandboxWaveRow,job.wave_id)
        w.payload={**w.payload,'post_admission_marker':'changed'};w.digest=digest(w.payload)
        job.payload={**job.payload,'wave_digest':w.digest};job.digest=digest(job.payload)
        db.get(ApprovalRequestRow,w.approval_id).payload=w.payload
    # Earlier enqueue snapshot survives in admission sources. Other exact
    # payload checks are deliberately self-consistent to isolate this boundary.
    with pytest.raises(WaveConflict,match='admission source drift'):svc.claim(OWNER,id,'worker')
    assert svc.get(OWNER,id)['state']=='queued'

def test_pin_pool_job_count_three_one_task_jobs(env):
    svc,sessions,_,_=env;ids=[queued(svc,sessions,n=1) for _ in range(3)]
    svc.claim(OWNER,ids[0],'one');svc.claim(OWNER,ids[1],'two')
    # Three tasks fit the four-task cap, but three workers violate job count.
    with pytest.raises(WaveConflict,match='pool exhausted'):svc.claim(OWNER,ids[2],'three')
    assert svc.get(OWNER,ids[2])['state']=='queued'

def test_pin_local_two_task_wave_limit(env):
    svc,sessions,_,_=env;b,w=prepared(svc,sessions,n=3)
    with pytest.raises(WaveConflict,match='local wave limit2'):svc.enqueue(OWNER,b,w)
    with sessions() as db:assert not db.scalar(select(LocalDispatchJobRow.id))

def test_pin_enqueue_slot_expiry_before_any_job_creation(env):
    svc,sessions,_,_=env;b,w=prepared(svc,sessions,n=1)
    with sessions.begin() as db:
        slot=db.scalar(select(BuilderSlotRow).where(BuilderSlotRow.batch_id==b));slot.expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    with pytest.raises(WaveConflict,match='unexpired'):svc.enqueue(OWNER,b,w)
    with sessions() as db:assert not db.scalar(select(LocalDispatchJobRow.id))
