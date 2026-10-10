"""Durable logical admission controls, not deployed capacity."""
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from sqlalchemy import create_engine,select,func,inspect,update
from sqlalchemy.orm import sessionmaker
from app.auth.context import TenantContext
from app.modules.m14_project_builder.builder_admission import *
from app.modules.m14_project_builder.schemas import ProjectTask,ProjectPlan,Budget
from app.modules.m14_project_builder.sandbox_wave import SandboxWaveTaskRow,SandboxWaveArtifactRow
from app.modules.m14_project_builder.reviewed_continuation import ReviewRow
from app.modules.m00_approval_center.impact import ApprovalReviewStateRow
OWNER=TenantContext('t','owner')
TABLES=(ProjectRow,SandboxWaveRow,SandboxWaveTaskRow,SandboxWaveArtifactRow,ReviewRow,ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow,ApprovalReviewStateRow)

@pytest.fixture(params=['sqlite','pg'])
def env(request,tmp_path):
    if request.param=='pg':
        import pgserver
        server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
        uri=server.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri='sqlite:///'+str(tmp_path/'admit.db')
    engine=create_engine(uri);sessions=sessionmaker(engine,expire_on_commit=False)
    for model in (*TABLES,*MODELS):model.__table__.create(engine)
    with sessions.begin() as db:db.add(BuilderPoolRow(id=1,epoch=0,limits=dict(GLOBAL_LIMITS),used=zeros()))
    svc=BuilderAdmissionService(sessions)
    yield svc,sessions,uri
    engine.dispose()

def wave(sessions,ctx=OWNER,n=8):
    id=str(uuid.uuid4());pid=str(uuid.uuid4())
    plan=ProjectPlan(goal='logical builders',tasks=[ProjectTask(id=str(i),title='build',objective='inert fixture',agent_kind='coder') for i in range(n)])
    p=plan.model_dump(mode='json');budget=Budget().model_dump(mode='json')
    payload=dict(project_revision=1,plan=p,budget=budget,ready_task_ids=[str(i) for i in range(n)])
    with sessions.begin() as db:
        db.add(ProjectRow(tenant_id=ctx.tenant_id,id=pid,goal='fixture',brief={},budget=budget,status='planned',revision=1,plan=p))
        db.add(SandboxWaveRow(id=id,tenant_id=ctx.tenant_id,actor_id=ctx.actor_id,project_id=pid,payload=payload,digest=digest(payload),state='draft',created_at=_time()))
    return id

def _time():return datetime.now(timezone.utc).isoformat()
def approved(svc,sessions,ctx=OWNER,n=8,**kw):
    b=svc.propose(ctx,AdmissionRequest(wave_ids=[wave(sessions,ctx,n)],**kw))
    svc.decide(ctx,b['id'],'approved');return b['id']
def populated(svc,sessions,ctx,total):
    ids=[wave(sessions,ctx,min(8,total-i)) for i in range(0,total,8)]
    b=svc.propose(ctx,AdmissionRequest(wave_ids=ids));svc.decide(ctx,b['id'],'approved');return b['id']

def test_capacity_1000_then_1001_refused_exact_inventory(env):
    svc,sessions,_=env;b1=populated(svc,sessions,OWNER,600);other=TenantContext('u','owner');b2=populated(svc,sessions,other,400)
    svc.reserve(OWNER,b1);svc.reserve(other,b2)
    extra=approved(svc,sessions,other,1)
    with pytest.raises(WaveConflict,match='quota'):svc.reserve(other,extra)
    with sessions() as db:
        slots=list(db.scalars(select(BuilderSlotRow)));assert len(slots)==1000 and len({s.work_key for s in slots})==1000
        assert len({s.project_id for s in slots})==125
        assert db.get(BuilderPoolRow,1).used==dict(slots=1000,cpu_units=1000,memory_mb=256000,runtime_seconds=600000,cost_cents=0)
        assert db.get(BuilderBatchRow,extra).state=='approved'
        assert db.scalar(select(func.count()).select_from(ApprovalEffectRow))==2

def test_owner_module_decision_and_unused_approval(env):
    svc,sessions,_=env;b=svc.propose(OWNER,AdmissionRequest(wave_ids=[wave(sessions)]))
    with pytest.raises(WaveConflict):svc.reserve(OWNER,b['id'])
    for bad in (TenantContext('t','other',frozenset({'atlas-admin'})),TenantContext('u','owner')):
        with pytest.raises(WaveForbidden):svc.decide(bad,b['id'],'approved')
        with pytest.raises(WaveForbidden):svc.get(bad,b['id'])
    svc.gate.decide(b['approval_id'],__import__('app.core.models',fromlist=['ApprovalStatus']).ApprovalStatus.APPROVED,decided_by='owner')
    with pytest.raises(WaveConflict,match='module owner'):svc.reserve(OWNER,b['id'])

def test_fences_cancel_unknown_and_reconcile_no_retry(env):
    svc,sessions,_=env;b=approved(svc,sessions,n=2);result=svc.reserve(OWNER,b);a,c=result['slots']
    claim=svc.claim(OWNER,a['id'],'worker')
    with pytest.raises(WaveConflict):svc.claim(OWNER,a['id'],'worker')
    with pytest.raises(WaveConflict):svc.complete(OWNER,a['id'],claim['token'],claim['fence']+1,'worker','completed')
    with pytest.raises(WaveConflict):svc.complete(OWNER,a['id'],claim['token'],claim['fence'],'other','completed')
    svc.cancel(OWNER,a['id']);assert svc.status(OWNER)['tenant_used']['slots']==2
    with pytest.raises(WaveConflict):svc.complete(OWNER,a['id'],claim['token'],claim['fence'],'worker','completed')
    svc.reconcile(OWNER,a['id'],'worker stopped, outcome unverified');svc.cancel(OWNER,c['id'])
    assert svc.status(OWNER)['tenant_used']==zeros()
    with pytest.raises(WaveConflict):svc.reconcile(OWNER,a['id'],'again')
    with pytest.raises(WaveConflict):svc.claim(OWNER,a['id'],'worker')

def test_actual_complete_release_and_stale_fence(env):
    svc,sessions,_=env;b=approved(svc,sessions,n=1);s=svc.reserve(OWNER,b)['slots'][0];c=svc.claim(OWNER,s['id'],'w')
    svc.complete(OWNER,s['id'],c['token'],c['fence'],'w','completed');assert svc.status(OWNER)['tenant_used']==zeros()
    with pytest.raises(WaveConflict):svc.complete(OWNER,s['id'],c['token'],c['fence'],'w','completed')

def test_expired_claim_retained_restart_unknown(env):
    svc,sessions,_=env;b=approved(svc,sessions,n=1,ttl_seconds=10);s=svc.reserve(OWNER,b)['slots'][0];c=svc.claim(OWNER,s['id'],'w')
    svc.clock=lambda:datetime.now(timezone.utc)+timedelta(seconds=20)
    assert svc.get(OWNER,b)['outcome_unknown_ids']==[s['id']]
    assert svc.status(OWNER)['tenant_used']['slots']==1
    with pytest.raises(WaveConflict):svc.complete(OWNER,s['id'],c['token'],c['fence'],'w','completed')
    svc.reconcile(OWNER,s['id'],'expired worker externally stopped');assert svc.status(OWNER)['tenant_used']['slots']==0

def test_rollback_permit_quota_and_slots_atomic(env,monkeypatch):
    svc,sessions,_=env;b=approved(svc,sessions);original=svc.gate.consume_effect
    def fault(*a,**kw):original(*a,**kw);kw['_session'].flush();raise RuntimeError('fault')
    monkeypatch.setattr(svc.gate,'consume_effect',fault)
    with pytest.raises(RuntimeError):svc.reserve(OWNER,b)
    with sessions() as db:
        assert db.get(BuilderPoolRow,1).used==zeros() and not db.scalar(select(BuilderSlotRow.id)) and not db.scalar(select(ApprovalEffectRow.id))
        assert db.get(BuilderBatchRow,b).state=='approved'
    monkeypatch.setattr(svc.gate,'consume_effect',original);svc.reserve(OWNER,b)

def test_resource_and_tenant_quotas(env):
    svc,sessions,_=env
    b=populated(svc,sessions,OWNER,601)
    with pytest.raises(WaveConflict,match='quota'):svc.reserve(OWNER,b)
    b=approved(svc,sessions,n=8,runtime_seconds=86400)
    with pytest.raises(WaveConflict,match='quota'):svc.reserve(OWNER,b)
    b=approved(svc,sessions,n=8,memory_mb=4096,cpu_units=8);svc.reserve(OWNER,b)
    assert svc.status(OWNER)['tenant_used']['cpu_units']==64
    from pydantic import ValidationError
    for field,value in [('cost_cents',1),('cpu_units',True),('ttl_seconds',0),('memory_mb',float('nan'))]:
        with pytest.raises(ValidationError):AdmissionRequest(wave_ids=['x'],**{field:value})

def test_project_snapshot_drift_and_permanent_task_dedupe(env):
    svc,sessions,_=env;b=approved(svc,sessions,n=1);first=svc.reserve(OWNER,b)
    source=first['payload']['sources'][0]
    duplicate=svc.propose(OWNER,AdmissionRequest(wave_ids=[source['wave_id']]));svc.decide(OWNER,duplicate['id'],'approved')
    with pytest.raises(WaveConflict,match='already admitted'):svc.reserve(OWNER,duplicate['id'])
    with sessions.begin() as db:
        p=db.scalar(select(ProjectRow).where(ProjectRow.id==source['project_id']));p.revision+=1
    with pytest.raises(WaveConflict):svc.claim(OWNER,first['slots'][0]['id'],'worker')

def test_oidc_actual_http_owner_foreign_generic_and_strict(env,oidc_auth_headers,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m14_project_builder import routes
    from app.modules.m00_approval_center import routes as m00
    svc,sessions,_=env;app=FastAPI();app.include_router(routes.router);app.include_router(m00.router)
    app.dependency_overrides[routes.get_admission_service]=lambda:svc;app.dependency_overrides[m00.get_service]=lambda:svc.gate
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    with TestClient(app) as client:
        url='/project-builder/builder-admission';owner=oidc_auth_headers('t','owner');other=oidc_auth_headers('t','other')
        assert client.post(url+'/batches',json={'wave_ids':[wave(sessions)]}).status_code==401
        b=client.post(url+'/batches',headers=owner,json={'wave_ids':[wave(sessions)]}).json();id=b['id']
        assert client.post('/approval-center/requests/'+b['approval_id']+'/decision',headers=owner,json={'decision':'approved','decided_by':'owner'}).status_code==403
        assert client.post(url+'/batches/'+id+'/decision',headers=other,json={'decision':'approved'}).status_code==403
        assert client.post(url+'/batches/'+id+'/decision',headers=owner,json={'decision':'approved'}).status_code==200
        result=client.post(url+'/batches/'+id+'/reserve',headers=owner).json();s=result['slots'][0]['id']
        assert client.post(url+'/slots/'+s+'/claim',headers=other,json={'worker_id':'w'}).status_code==403
        claim=client.post(url+'/slots/'+s+'/claim',headers=owner,json={'worker_id':'w'}).json()
        body=dict(worker_id='w',token=claim['token'],fence=claim['fence'],outcome='completed')
        assert client.post(url+'/slots/'+s+'/complete',headers=owner,json={**body,'fence':True}).status_code==422
        assert client.post(url+'/slots/'+s+'/complete',headers=owner,json=body).status_code==200

WORKER="""import json,sys,time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.auth.context import TenantContext
from app.modules.m14_project_builder.builder_admission import BuilderAdmissionService,WaveConflict
svc=BuilderAdmissionService(sessionmaker(create_engine(sys.argv[1]),expire_on_commit=False));ctx=TenantContext(sys.argv[2],'owner')
try:
 r=svc.reserve(ctx,sys.argv[3]);print(json.dumps({'outcome':'reserved','slots':len(r['slots'])}))
except WaveConflict:print(json.dumps({'outcome':'refused'}))
"""

def test_actual_pg_cross_process_contention_and_restart_inventory(env):
    svc,sessions,uri=env
    b=populated(svc,sessions,OWNER,600);other=TenantContext('u','owner');a=populated(svc,sessions,other,400);c=populated(svc,sessions,other,400)
    svc.reserve(OWNER,b)
    args=lambda id:[sys.executable,'-c',WORKER,uri,'u',id]
    p1=subprocess.Popen(args(a),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    p2=subprocess.Popen(args(c),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    results=[]
    for p in (p1,p2):
        out,err=p.communicate(timeout=60);assert p.returncode==0,err;results.append(json.loads(out)['outcome'])
    assert sorted(results)==['refused','reserved']
    with sessions() as db:assert db.scalar(select(func.count()).select_from(BuilderSlotRow))==1000 and db.get(BuilderPoolRow,1).used['slots']==1000
    code="""import json,sys
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import sessionmaker
from app.modules.m14_project_builder.builder_admission import BuilderSlotRow,BuilderPoolRow
with sessionmaker(create_engine(sys.argv[1]))() as db:print(json.dumps({'count':db.scalar(select(func.count()).select_from(BuilderSlotRow)),'used':db.get(BuilderPoolRow,1).used['slots']}))
"""
    run=subprocess.run([sys.executable,'-c',code,uri],capture_output=True,text=True,timeout=30)
    assert run.returncode==0,run.stderr;assert json.loads(run.stdout)==dict(count=1000,used=1000)

def test_migration_populated_roundtrip_and_active_refusal(env,tmp_path):
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    svc,sessions,uri=env
    engine=sessions.kw['bind']
    for model in reversed(MODELS):model.__table__.drop(engine)
    path=Path(__file__).resolve().parents[2]/'migrations/versions/20261010_m14_builder_admission.py'
    spec=importlib.util.spec_from_file_location('admission_migration',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):m.upgrade()
    b=approved(svc,sessions,n=1);s=svc.reserve(OWNER,b)['slots'][0]
    with pytest.raises(RuntimeError,match='active'):
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):m.downgrade()
    svc.cancel(OWNER,s['id'])
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            m.downgrade();assert 'm14_builder_pool' not in inspect(conn).get_table_names();m.upgrade()
    assert svc.status(OWNER)['tenant_used']==zeros()

def test_real_product_wave_draft_admitted_not_executed(env,tmp_path):
    from app.modules.m14_project_builder.sandbox_wave import SandboxWaveService,WaveDraft,TaskCode
    svc,sessions,_=env
    w=wave(sessions,n=2)
    with sessions() as db:pid=db.get(SandboxWaveRow,w).project_id
    # Real product drafting is isolated from backend execution; no probe required.
    import tempfile,shutil
    root=Path(tempfile.mkdtemp(prefix='atlas-admission-',dir=Path.home()));root.chmod(0o700)
    os.environ['ATLAS_M14_SANDBOX_BACKEND']='bubblewrap'
    waves=SandboxWaveService(sessions,str(root))
    draft=waves.draft('t','owner',pid,WaveDraft(tasks={'0':TaskCode(code='print(0)'), '1':TaskCode(code='print(1)')},max_parallel=2))
    batch=svc.propose(OWNER,AdmissionRequest(wave_ids=[draft['id']]))
    svc.decide(OWNER,batch['id'],'approved');reserved=svc.reserve(OWNER,batch['id'])
    assert len(reserved['slots'])==2 and not reserved['dispatch_authorized']
    assert waves.get('t','owner',draft['id'])['state']=='draft'
    # Admission permit is deliberately not the M14 sandbox execution approval.
    with pytest.raises(WaveConflict):waves.claim('t','owner',draft['id'])
    shutil.rmtree(root)

def test_actual_crash_after_claim_separate_restart_fence(env):
    svc,sessions,uri=env;b=approved(svc,sessions,n=1);s=svc.reserve(OWNER,b)['slots'][0]
    code="""import os,sys,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.auth.context import TenantContext
from app.modules.m14_project_builder.builder_admission import BuilderAdmissionService
svc=BuilderAdmissionService(sessionmaker(create_engine(sys.argv[1]),expire_on_commit=False));r=svc.claim(TenantContext('t','owner'),sys.argv[2],'crashed-worker');print(json.dumps(r),flush=True);os._exit(27)
"""
    run=subprocess.run([sys.executable,'-c',code,uri,s['id']],capture_output=True,text=True,timeout=30)
    assert run.returncode==27,run.stderr;c=json.loads(run.stdout)
    fresh=BuilderAdmissionService(sessions);assert fresh.get(OWNER,b)['slots'][0]['state']=='claimed'
    assert fresh.status(OWNER)['tenant_used']['slots']==1
    with pytest.raises(WaveConflict):fresh.claim(OWNER,s['id'],'replacement')
    fresh.cancel(OWNER,s['id']);assert fresh.get(OWNER,b)['outcome_unknown_ids']==[s['id']]
    with pytest.raises(WaveConflict):fresh.complete(OWNER,s['id'],c['token'],c['fence'],'crashed-worker','completed')
    fresh.reconcile(OWNER,s['id'],'process exited27, outcome remains unverified');assert fresh.status(OWNER)['tenant_used']==zeros()

def test_distinct_claim_contenders_only_one_fenced_winner(env):
    svc,sessions,uri=env;b=approved(svc,sessions,n=1);s=svc.reserve(OWNER,b)['slots'][0]
    code="""import sys,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.auth.context import TenantContext
from app.modules.m14_project_builder.builder_admission import BuilderAdmissionService,WaveConflict
svc=BuilderAdmissionService(sessionmaker(create_engine(sys.argv[1]),expire_on_commit=False))
try:r=svc.claim(TenantContext('t','owner'),sys.argv[2],sys.argv[3]);print(json.dumps({'state':'claimed','fence':r['fence']}))
except WaveConflict:print(json.dumps({'state':'refused'}))
"""
    ps=[subprocess.Popen([sys.executable,'-c',code,uri,s['id'],w],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for w in ('worker1','worker2')]
    results=[]
    for p in ps:
        out,err=p.communicate(timeout=30);assert p.returncode==0,err;results.append(json.loads(out))
    assert sorted(r['state'] for r in results)==['claimed','refused']
    assert [r['fence'] for r in results if r['state']=='claimed']==[1]

def test_cpu_memory_global_and_tenant_budget_transaction(env):
    svc,sessions,_=env
    # Under slot quota but over CPU quota: no partial reservations.
    ids=[wave(sessions) for _ in range(10)]
    b=svc.propose(OWNER,AdmissionRequest(wave_ids=ids,cpu_units=8));svc.decide(OWNER,b['id'],'approved')
    with pytest.raises(WaveConflict,match='quota'):svc.reserve(OWNER,b['id'])
    ids=[wave(sessions) for _ in range(5)]
    b=svc.propose(OWNER,AdmissionRequest(wave_ids=ids,memory_mb=4096));svc.decide(OWNER,b['id'],'approved')
    with pytest.raises(WaveConflict,match='quota'):svc.reserve(OWNER,b['id'])
    assert svc.status(OWNER)['tenant_used']==zeros()

def test_denied_expired_duplicates_boundaries(env):
    svc,sessions,_=env;wid=wave(sessions)
    with pytest.raises(WaveConflict):svc.propose(OWNER,AdmissionRequest(wave_ids=[wid,wid]))
    with pytest.raises(WaveForbidden):svc.propose(TenantContext('u','owner'),AdmissionRequest(wave_ids=[wid]))
    b=svc.propose(OWNER,AdmissionRequest(wave_ids=[wid]));svc.decide(OWNER,b['id'],'denied')
    with pytest.raises(WaveConflict):svc.reserve(OWNER,b['id'])
    b=approved(svc,sessions,n=1,ttl_seconds=1);svc.clock=lambda:datetime.now(timezone.utc)+timedelta(seconds=10)
    with pytest.raises(WaveConflict):svc.reserve(OWNER,b)
    assert svc.status(OWNER)['tenant_used']==zeros()

@pytest.mark.parametrize('mutation',['digest','approval_payload','approval_owner','approval_expiry','approval_action','project_plan','claimed_wave','source_tenant'])
def test_immutable_binding_mutations_refuse_before_effect(env,mutation):
    svc,sessions,_=env;b=approved(svc,sessions,n=1)
    with sessions.begin() as db:
        batch=db.get(BuilderBatchRow,b);a=db.get(ApprovalRequestRow,batch.approval_id);source=batch.payload['sources'][0];w=db.get(SandboxWaveRow,source['wave_id'])
        if mutation=='digest':batch.digest='0'*64
        if mutation=='approval_payload':a.payload={**a.payload,'logical_only':False}
        if mutation=='approval_owner':a.approved_by='other'
        if mutation=='approval_expiry':a.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        if mutation=='approval_action':a.action_type='execute_project_sandbox_wave'
        if mutation=='project_plan':
            p=db.scalar(select(ProjectRow).where(ProjectRow.id==w.project_id));p.plan={**p.plan,'goal':'changed'}
        if mutation=='claimed_wave':w.state='claimed';w.claim_key='already-claimed'
        if mutation=='source_tenant':w.tenant_id='other'
    with pytest.raises((WaveConflict,WaveForbidden,__import__('app.modules.m00_approval_center.service',fromlist=['ApprovalConflictError']).ApprovalConflictError)):svc.reserve(OWNER,b)
    with sessions() as db:
        assert db.get(BuilderPoolRow,1).used==zeros() and not db.scalar(select(BuilderSlotRow.id)) and not db.scalar(select(ApprovalEffectRow.id))

# Independent audit named survivors, paired actual SQL backends.
def test_p1_live_claim_cannot_be_reconciled_and_free_capacity(env):
    svc,sessions,_=env;b=approved(svc,sessions,n=1);s=svc.reserve(OWNER,b)['slots'][0];c=svc.claim(OWNER,s['id'],'live')
    with pytest.raises(WaveConflict,match='outcome-unknown'):svc.reconcile(OWNER,s['id'],'premature release')
    with sessions() as db:
        slot=db.get(BuilderSlotRow,s['id']);assert slot.state=='claimed' and slot.token==c['token'] and slot.fence==c['fence']
        assert slot.reconciliation is None and db.get(BuilderPoolRow,1).used['slots']==1
        assert db.get(BuilderTenantRow,'t').used['slots']==1

def test_p2_expired_reserved_slot_cannot_claim(env):
    svc,sessions,_=env;b=approved(svc,sessions,n=1);s=svc.reserve(OWNER,b)['slots'][0]
    with sessions.begin() as db:db.get(BuilderSlotRow,s['id']).expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    with pytest.raises(WaveConflict,match='unexpired'):svc.claim(OWNER,s['id'],'worker')
    with sessions() as db:
        slot=db.get(BuilderSlotRow,s['id']);assert slot.state=='reserved' and slot.token is None and slot.fence==0
        assert db.get(BuilderPoolRow,1).used['slots']==1

def test_p3_wrong_token_with_correct_fence_worker_cannot_complete(env):
    svc,sessions,_=env;b=approved(svc,sessions,n=1);s=svc.reserve(OWNER,b)['slots'][0];c=svc.claim(OWNER,s['id'],'worker')
    with pytest.raises(WaveConflict,match='fenced'):svc.complete(OWNER,s['id'],str(uuid.uuid4()),c['fence'],'worker','completed')
    assert svc.get(OWNER,b)['slots'][0]['state']=='claimed' and svc.status(OWNER)['tenant_used']['slots']==1

@pytest.mark.parametrize('stage',['reserve','claim'])
def test_p4_self_consistent_wave_digest_drift_after_approval(env,stage):
    svc,sessions,_=env;b=approved(svc,sessions,n=1);s=svc.reserve(OWNER,b)['slots'][0] if stage=='claim' else None
    with sessions.begin() as db:
        batch=db.get(BuilderBatchRow,b);w=db.get(SandboxWaveRow,batch.payload['sources'][0]['wave_id'])
        w.payload={**w.payload,'changed_config_marker':'post-approval'};w.digest=digest(w.payload)
    with pytest.raises(WaveConflict,match='source'):
        if stage=='claim':svc.claim(OWNER,s['id'],'worker')
        else:svc.reserve(OWNER,b)
    with sessions() as db:
        assert db.get(BuilderPoolRow,1).used['slots']==(1 if stage=='claim' else 0)
        if s:assert db.get(BuilderSlotRow,s['id']).state=='reserved'
        else:assert not db.scalar(select(BuilderSlotRow.id)) and not db.scalar(select(ApprovalEffectRow.id))

def test_p5_same_tenant_foreign_wave_owner_refused(env):
    svc,sessions,_=env;wid=wave(sessions,TenantContext('t','different-owner'),1)
    with pytest.raises(WaveForbidden,match='owner wave'):svc.propose(OWNER,AdmissionRequest(wave_ids=[wid]))
    with sessions() as db:assert not db.scalar(select(BuilderBatchRow.id)) and not db.scalar(select(ApprovalRequestRow.id))

def test_p6_rejected_ready_task_cannot_be_admitted(env):
    svc,sessions,_=env;wid=wave(sessions,n=1)
    with sessions.begin() as db:
        db.add(ReviewRow(id=str(uuid.uuid4()),tenant_id='t',actor_id='owner',payload={'prior_wave_id':wid,'selection':{'0':{'accept':False,'reason':'rejected'}}},digest='unused-fixture',approval_id=str(uuid.uuid4()),state='applied'))
    with pytest.raises(WaveConflict,match='rejected'):svc.propose(OWNER,AdmissionRequest(wave_ids=[wid]))
    with sessions() as db:assert not db.scalar(select(BuilderBatchRow.id))

def test_p6_completed_nonready_task_cannot_be_admitted(env):
    svc,sessions,_=env;wid=wave(sessions,n=1)
    with sessions.begin() as db:
        w=db.get(SandboxWaveRow,wid);p=db.scalar(select(ProjectRow).where(ProjectRow.id==w.project_id))
        plan=json.loads(json.dumps(p.plan));plan['tasks'][0]['status']='completed';p.plan=plan
        w.payload={**w.payload,'plan':plan};w.digest=digest(w.payload)
    with pytest.raises(WaveConflict,match='ready wave'):svc.propose(OWNER,AdmissionRequest(wave_ids=[wid]))
    with sessions() as db:assert not db.scalar(select(BuilderBatchRow.id))

@pytest.mark.parametrize('mutation',['expiry','payload'])
def test_p7_decide_requires_live_exact_approval(env,mutation):
    svc,sessions,_=env;b=svc.propose(OWNER,AdmissionRequest(wave_ids=[wave(sessions,n=1)]))
    with sessions.begin() as db:
        a=db.get(ApprovalRequestRow,b['approval_id'])
        if mutation=='expiry':a.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        else:a.payload={**a.payload,'different_reviewed_value':True}
    with pytest.raises(WaveConflict,match='matching live'):svc.decide(OWNER,b['id'],'approved')
    with sessions() as db:
        assert db.get(BuilderBatchRow,b['id']).state=='awaiting_approval' and db.get(ApprovalRequestRow,b['approval_id']).status=='pending'
        assert not db.scalar(select(ApprovalEventRow.id).where(ApprovalEventRow.approval_id==b['approval_id'],ApprovalEventRow.event=='approved'))

@pytest.mark.parametrize('policy',['pool','tenant'])
def test_p8_fixed_policy_drift_cannot_reserve(env,policy):
    svc,sessions,_=env;b=approved(svc,sessions,n=1)
    with sessions.begin() as db:
        if policy=='pool':db.get(BuilderPoolRow,1).limits={**GLOBAL_LIMITS,'slots':1001}
        else:db.add(BuilderTenantRow(tenant_id='t',limits={**TENANT_LIMITS,'slots':601},used=zeros()))
    with pytest.raises(WaveConflict,match='policy drift'):svc.reserve(OWNER,b)
    with sessions() as db:
        assert db.get(BuilderPoolRow,1).used==zeros() and not db.scalar(select(BuilderSlotRow.id)) and not db.scalar(select(ApprovalEffectRow.id))

@pytest.mark.parametrize('quota',['pool','tenant'])
def test_p9_release_quota_integrity_refuses_and_rolls_back(env,quota):
    svc,sessions,_=env;b=approved(svc,sessions,n=1);s=svc.reserve(OWNER,b)['slots'][0];c=svc.claim(OWNER,s['id'],'worker')
    with sessions.begin() as db:
        row=db.get(BuilderPoolRow,1) if quota=='pool' else db.get(BuilderTenantRow,'t')
        row.used={**row.used,'memory_mb':0}
    with pytest.raises(WaveConflict,match='quota integrity'):svc.complete(OWNER,s['id'],c['token'],c['fence'],'worker','completed')
    with sessions() as db:
        slot=db.get(BuilderSlotRow,s['id']);assert slot.state=='claimed' and slot.token==c['token'] and slot.fence==c['fence']
        # In the tenant case, earlier pool decrement must roll back as well.
        assert db.get(BuilderPoolRow,1).used['slots']==1 and db.get(BuilderTenantRow,'t').used['slots']==1
