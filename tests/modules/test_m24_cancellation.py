"""Cancellation mechanics with fixture-only readiness. No provider activation."""
import asyncio,copy
from datetime import datetime,timezone
from urllib.parse import parse_qs
import pytest,httpx
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service,ApprovalEffectRow
from app.modules.m24_billing import write_ahead as wa
from app.modules.m24_billing.repository import TenantBillingRow
from app.modules.m24_billing.cancellation import CancellationRepository,CancellationDispatcher,CancellationAdapter,TERMS
from app.modules.m24_billing.invoice_dispatcher import InvoiceRepository,InvoiceStepRow

@pytest.fixture(params=['sqlite','postgres'])
def env(tmp_path,request,m24_postgres_schema):
    if request.param=='postgres':
        import pgserver
        pg=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');uri=pg.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri=f'sqlite:///{tmp_path}/cancel.db'
    engine=create_engine(uri);m24_postgres_schema(engine);Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False);svc=Service(session_factory=sessions)
    with sessions.begin() as db:db.add(TenantBillingRow(tenant_id='t1',customer_id='cus_fixture',subscription_id='sub_fixture',status='active',cancel_at_period_end=False))
    payload={'tenant_id':'t1','provider':'stripe','effect':'cancel_subscription','customer_id':'cus_fixture','subscription_id':'sub_fixture',
        'before_state':{'customer_id':'cus_fixture','subscription_id':'sub_fixture','status':'active','cancel_at_period_end':False},'cancellation_terms':copy.deepcopy(TERMS)}
    a=svc.submit(module_id=24,action_type='cancel_subscription',user_id='t1',payload=payload);svc.decide(a['id'],ApprovalStatus.APPROVED,'owner')
    yield svc,sessions,CancellationRepository(svc),a
    engine.dispose()
    if request.param=='postgres':pg.cleanup()

def prepare(env):return env[2].prepare(env[3]['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')

def ready(env,monkeypatch):
    monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    with env[1].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='fixture-only',verified_at=datetime.now(timezone.utc)))

class Mock:
    def __init__(self,timeout=False):self.calls=[];self.effects=0;self.timeout=timeout
    def __call__(self,request):
        self.calls.append(request.method)
        body={'id':'sub_fixture','object':'subscription','customer':'cus_fixture','status':'active','cancel_at_period_end':False,'livemode':False,'metadata':{'atlas_tenant_id':'t1'}}
        if request.method=='DELETE':
            assert 'Idempotency-Key' not in request.headers
            assert parse_qs(request.content.decode())=={'invoice_now':['false'],'prorate':['false']}
            self.effects+=1;body.update(status='canceled',canceled_at=1234)
            if self.timeout:raise httpx.ReadTimeout('accepted before timeout',request=request)
        return httpx.Response(200,json=body)

def dispatch(env,op,mock):return asyncio.run(CancellationDispatcher(env[2],CancellationAdapter('sk_test_fixture','test-account',httpx.MockTransport(mock))).dispatch(op['id'],'t1'))


def test_exact_delete_terms_two_get_preflight_one_effect_replay(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=Mock()
    assert dispatch(env,op,mock)['state']=='succeeded'
    assert mock.calls==['GET','GET','DELETE'] and mock.effects==1
    assert dispatch(env,op,mock)['state']=='succeeded' and mock.effects==1


def test_accepted_delete_timeout_unknown_never_repeated(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=Mock(timeout=True)
    assert dispatch(env,op,mock)['state']=='outcome_unknown'
    assert dispatch(env,op,mock)['state']=='outcome_unknown' and mock.effects==1


def test_hard_readiness_zero_network(env):
    op=prepare(env);mock=Mock()
    with pytest.raises(wa.DispatchRefused):dispatch(env,op,mock)
    assert mock.calls==[]


def test_legacy_sparse_cancel_request_refuses_no_permit(env):
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    with env[1].begin() as db:db.get(ApprovalRequestRow,env[3]['id']).payload={'tenant_id':'t1','provider':'stripe','effect':'cancel_subscription','subscription_id':'sub_fixture'}
    with pytest.raises(wa.DispatchRefused,match='terms'):prepare(env)
    with env[1]() as db:assert db.scalar(select(ApprovalEffectRow)) is None


def test_cancellation_preparation_fences_existing_draft_before_item(env):
    svc,sessions,repo,a=env
    invoice=svc.submit(module_id=24,action_type='issue_invoice',user_id='t1',payload={'tenant_id':'t1','provider':'stripe','effect':'create_draft_invoice','customer_id':'cus_fixture','description':'draft','amount_cents':1234,'currency':'usd'})
    svc.decide(invoice['id'],ApprovalStatus.APPROVED,'owner');irepo=InvoiceRepository(svc)
    op=irepo.prepare(invoice['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')
    with sessions.begin() as db:
        row=db.get(InvoiceStepRow,op['id']+':draft-invoice');row.state='succeeded';row.result={'id':'in_fixture','object':'invoice','customer':'cus_fixture','currency':'usd','livemode':False,'invoice':None,'amount':0}
    prepare(env)
    assert irepo.get(op['id'],'t1')['state']=='outcome_unknown'
    with pytest.raises(wa.DispatchRefused,match='cancellation fence|cancelled or held'):irepo.prepare_item(op['id'],'t1')


def test_new_invoice_after_cancel_refuses_and_late_draft_evidence_retained(env,monkeypatch):
    svc,sessions,repo,a=env
    invoice=svc.submit(module_id=24,action_type='issue_invoice',user_id='t1',payload={'tenant_id':'t1','provider':'stripe','effect':'create_draft_invoice','customer_id':'cus_fixture','description':'draft','amount_cents':1234,'currency':'usd'})
    svc.decide(invoice['id'],ApprovalStatus.APPROVED,'owner');irepo=InvoiceRepository(svc)
    op=irepo.prepare(invoice['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')
    ready(env,monkeypatch);fence=irepo.claim_step(op['id'],'t1','draft-invoice')
    prepare(env)
    receipt={'id':'in_fixture','object':'invoice','customer':'cus_fixture','currency':'usd','livemode':False,'invoice':None,'amount':0}
    assert irepo.step_outcome(op['id'],'t1','draft-invoice',fence,state='succeeded',result=receipt)['step']['state']=='succeeded_late'
    assert irepo.steps(op['id'],'t1')['draft-invoice']['result']==receipt
    newer=svc.submit(module_id=24,action_type='issue_invoice',user_id='t1',payload=invoice['payload']);svc.decide(newer['id'],ApprovalStatus.APPROVED,'owner')
    with pytest.raises(wa.DispatchRefused,match='cancellation fence'):irepo.prepare(newer['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')


def test_cancel_proposal_includes_explicit_side_effects_and_customer(env):
    from app.modules.m24_billing.service import Service as BillingService
    from app.modules.m24_billing.schemas import CancelIn
    class Approvals:
        def put(self,item):return item
    class Repo:
        def tenant_billing(self,tenant):
            with env[1]() as db:return db.get(TenantBillingRow,tenant)
    proposal=BillingService(Approvals(),Repo(),None).propose_cancel('t1',CancelIn(subscription_id='sub_fixture'))
    assert proposal.payload['cancellation_terms']==TERMS
    assert proposal.payload['customer_id']=='cus_fixture'
    assert 'no stale item attachment' in proposal.payload['cancellation_terms']['atlas_pending_drafts']

@pytest.mark.parametrize('point',['attempt','accepted','receipt'])
def test_real_sigkill_cancellation_resume_no_second_delete(env,tmp_path,point):
    import subprocess,sys,os,time,signal,json
    op=prepare(env);readyfile=tmp_path/'ready';effects=tmp_path/'effects';answer=tmp_path/'answer'
    with env[1].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='fixture-only',verified_at=datetime.now(timezone.utc)))
    script=r'''
import asyncio,json,os,time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m00_approval_center.service import Service
from app.modules.m24_billing import write_ahead as wa
from app.modules.m24_billing.cancellation import CancellationRepository,CancellationDispatcher,CancellationAdapter
wa.require_dispatch_ready=lambda:None
repo=CancellationRepository(Service(session_factory=sessionmaker(bind=create_engine(os.environ['DATABASE']),expire_on_commit=False)))
def barrier(point):
 if os.environ['MODE']=='kill' and point==os.environ['POINT']:
  with open(os.environ['READY'],'w') as f:f.write(str(os.getpid()));f.flush();os.fsync(f.fileno())
  while True:time.sleep(.05)
original_claim=repo.claim;original_outcome=repo.outcome
def claim(*a,**kw):
 fence=original_claim(*a,**kw);barrier('attempt');return fence
repo.claim=claim
def outcome(*a,**kw):
 result=original_outcome(*a,**kw);barrier('receipt');return result
repo.outcome=outcome
class Adapter(CancellationAdapter):
 async def retrieve(self,snap):return {'id':'sub_fixture','object':'subscription','customer':'cus_fixture','status':'active','cancel_at_period_end':False,'livemode':False,'metadata':{'atlas_tenant_id':'t1'}}
 async def invoke(self,request):
  with open(os.environ['EFFECTS'],'a') as f:f.write('DELETE\n');f.flush();os.fsync(f.fileno())
  barrier('accepted')
  return {'id':'sub_fixture','object':'subscription','customer':'cus_fixture','status':'canceled','livemode':False,'canceled_at':1234}
result=asyncio.run(CancellationDispatcher(repo,Adapter('sk_test_fixture','test-account')).dispatch(os.environ['OP'],'t1'))
with open(os.environ['ANSWER'],'w') as f:json.dump({'pid':os.getpid(),'result':result},f,default=str)
'''
    settings={**os.environ,'DATABASE':str(env[1].kw['bind'].url),'OP':op['id'],'READY':str(readyfile),'EFFECTS':str(effects),'ANSWER':str(answer),'POINT':point,'MODE':'kill'}
    child=subprocess.Popen([sys.executable,'-c',script],env=settings)
    try:
        until=time.monotonic()+12
        while not readyfile.exists() and time.monotonic()<until:
            assert child.poll() is None;time.sleep(.02)
        assert readyfile.exists() and int(readyfile.read_text())==child.pid
        os.kill(child.pid,signal.SIGKILL);assert child.wait(5)==-signal.SIGKILL
        restart=subprocess.run([sys.executable,'-c',script],env={**settings,'MODE':'restart'},capture_output=True,text=True,timeout=12)
        assert restart.returncode==0,restart.stderr
        result=json.loads(answer.read_text());assert result['pid']!=child.pid
        assert result['result']['state']==('succeeded' if point=='receipt' else 'dispatching')
        assert (len(effects.read_text().splitlines()) if effects.exists() else 0)==(0 if point=='attempt' else 1)
    finally:
        if child.poll() is None:child.kill();child.wait(5)


def test_concurrent_invoice_prepare_and_cancel_never_leave_dispatchable_new_invoice(env):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    svc,sessions,repo,a=env;barrier=threading.Barrier(2)
    invoice=svc.submit(module_id=24,action_type='issue_invoice',user_id='t1',payload={'tenant_id':'t1','provider':'stripe','effect':'create_draft_invoice','customer_id':'cus_fixture','description':'draft','amount_cents':1234,'currency':'usd'});svc.decide(invoice['id'],ApprovalStatus.APPROVED,'owner')
    def draft():
        barrier.wait(5)
        try:return InvoiceRepository(svc).prepare(invoice['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')
        except wa.DispatchRefused:return None
    def cancel():barrier.wait(5);return prepare(env)
    with ThreadPoolExecutor(2) as pool:
        pending=pool.submit(draft);cancelled=pool.submit(cancel);d=pending.result();c=cancelled.result()
    with sessions() as db:
        invoices=db.scalars(select(wa.OperationRow).where(wa.OperationRow.action_type=='issue_invoice')).all()
        assert not invoices or all(row.state=='outcome_unknown' for row in invoices)


def test_provider_ownership_mismatch_zero_delete(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=Mock()
    def bad(request):
        response=mock(request);body=response.json();body['customer']='cus_other';return httpx.Response(200,json=body)
    with pytest.raises(wa.DispatchRefused,match='before state'):dispatch(env,op,bad)
    assert mock.effects==0


def test_cancel_service_uses_durable_adapter_not_legacy(env,monkeypatch):
    from app.modules.m24_billing.service import Service as BillingService
    op=prepare(env);ready(env,monkeypatch);mock=Mock()
    class Repo:
        def approval(self,aid):return env[0].get(aid)
        def record_execution(self,*a):raise AssertionError('legacy receipt')
    class Legacy:
        async def cancel_subscription(self,*a):raise AssertionError('legacy bypass')
    dispatcher=CancellationDispatcher(env[2],CancellationAdapter('sk_test_fixture','test-account',httpx.MockTransport(mock)))
    service=BillingService(None,Repo(),Legacy(),cancellation_dispatcher=dispatcher)
    assert asyncio.run(service.execute_approved(env[3]['id'],'t1'))['state']=='succeeded' and mock.effects==1


def test_late_cancel_response_after_local_lifecycle_change_retained(env,monkeypatch):
    from datetime import timedelta
    op=prepare(env);ready(env,monkeypatch);fence=env[2].claim(op['id'],'t1',protocol_epoch=2)
    with env[1].begin() as db:
        db.get(TenantBillingRow,'t1').status='canceled'
        db.get(wa.OperationRow,op['id']).lease_until=datetime.now(timezone.utc)-timedelta(seconds=1)
    receipt={'id':'sub_fixture','customer':'cus_fixture','status':'canceled','livemode':False,'canceled_at':1234}
    result=env[2].outcome(op['id'],'t1',fence,state='succeeded',result=receipt)
    assert result['state']=='succeeded_late' and result['result']==receipt

@pytest.mark.parametrize('database',['sqlite','postgres'])
def test_populated_cancellation_snapshot_downgrade_refuses(tmp_path,database):
    import subprocess,sys,os
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    if database=='postgres':
        import pgserver
        pg=pgserver.get_server(tmp_path/'migration-pg',cleanup_mode='stop');uri=pg.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri=f'sqlite:///{tmp_path}/migration.db'
    runenv={**os.environ,'ATLAS_DATABASE_URL':uri,'PYTHONPATH':'backend'}
    def migrate(*args):return subprocess.run([sys.executable,'-m','alembic',*args],cwd=root,env=runenv,capture_output=True,text=True,timeout=30)
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    engine=create_engine(uri);sessions=sessionmaker(bind=engine,expire_on_commit=False);svc=Service(session_factory=sessions)
    with sessions.begin() as db:db.add(TenantBillingRow(tenant_id='t1',customer_id='cus_fixture',subscription_id='sub_fixture',status='active',cancel_at_period_end=False))
    payload={'tenant_id':'t1','provider':'stripe','effect':'cancel_subscription','customer_id':'cus_fixture','subscription_id':'sub_fixture',
        'before_state':{'customer_id':'cus_fixture','subscription_id':'sub_fixture','status':'active','cancel_at_period_end':False},'cancellation_terms':dict(TERMS)}
    a=svc.submit(module_id=24,action_type='cancel_subscription',user_id='t1',payload=payload);svc.decide(a['id'],ApprovalStatus.APPROVED,'owner')
    CancellationRepository(svc).prepare(a['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')
    result=migrate('downgrade','20261009_m24_reconciliation');assert result.returncode!=0 and 'destructive downgrade refused' in result.stderr
    engine.dispose()
    if database=='postgres':pg.cleanup()


@pytest.mark.parametrize('field,value',[('status','paused'),('cancel_at_period_end',True)])
def test_local_before_state_drift_alone_refuses_without_permit(env,field,value):
    with env[1].begin() as db:setattr(db.get(TenantBillingRow,'t1'),field,value)
    with pytest.raises(wa.DispatchRefused,match='before state drift'):prepare(env)
    with env[1]() as db:
        assert db.scalar(select(ApprovalEffectRow)) is None
        assert db.scalar(select(wa.OperationRow)) is None


@pytest.mark.parametrize('field,value',[
    ('object','invoice'),('id','sub_other'),('customer','cus_other'),('livemode',True),
    ('status','paused'),('cancel_at_period_end',True),('metadata',{'atlas_tenant_id':'foreign'}),
])
def test_provider_before_field_drift_alone_refuses(env,field,value):
    from app.modules.m24_billing.cancellation import validate_before
    op=prepare(env);snap=env[2].snapshot(op['id'],'t1')
    raw={'id':'sub_fixture','object':'subscription','customer':'cus_fixture','status':'active',
        'cancel_at_period_end':False,'livemode':False,'metadata':{'atlas_tenant_id':'t1'}}
    validate_before(raw,snap)
    raw[field]=value
    with pytest.raises(wa.DispatchRefused,match='provider subscription'):validate_before(raw,snap)
    assert env[2].get(op['id'],'t1')['state']=='prepared'


@pytest.mark.parametrize('field,value',[('status','paused'),('metadata',{'atlas_tenant_id':'foreign'})])
def test_second_provider_read_drift_zero_delete_safe_failure(env,monkeypatch,field,value):
    op=prepare(env);ready(env,monkeypatch);mock=Mock()
    def drift(request):
        response=mock(request);body=response.json()
        if mock.calls==['GET','GET']:body[field]=value
        return httpx.Response(200,json=body)
    assert dispatch(env,op,drift)['state']=='failed_before_dispatch'
    assert mock.calls==['GET','GET'] and mock.effects==0


@pytest.mark.parametrize('state',[
    'prepared','dispatching','outcome_unknown','succeeded','succeeded_late',
    'failed_before_dispatch','closed_unknown','cancelled_before_dispatch',
])
def test_customer_fence_all_cancel_states_except_unsent_terminal(env,state):
    op=prepare(env)
    # Isolate the invoice fence state predicate, not a claim that all transitions
    # can be produced by the cancellation dispatcher or released automatically.
    with env[1].begin() as db:db.get(wa.OperationRow,op['id']).state=state
    invoice=env[0].submit(module_id=24,action_type='issue_invoice',user_id='t1',payload={
        'tenant_id':'t1','provider':'stripe','effect':'create_draft_invoice','customer_id':'cus_fixture',
        'description':'draft','amount_cents':1234,'currency':'usd'})
    env[0].decide(invoice['id'],ApprovalStatus.APPROVED,'owner')
    repo=InvoiceRepository(env[0])
    def prepare_invoice():return repo.prepare(invoice['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')
    if state=='cancelled_before_dispatch':assert prepare_invoice()['state']=='prepared'
    else:
        with pytest.raises(wa.DispatchRefused,match='cancellation fence'):prepare_invoice()
