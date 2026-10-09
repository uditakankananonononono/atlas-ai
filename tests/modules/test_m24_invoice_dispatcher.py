"""Invoice substep controls, production remains inactive."""
from app.modules.m24_billing.invoice_dispatcher import InvoiceRepository,InvoiceDispatcher

def test_invoice_dispatcher_import():
    assert InvoiceRepository and InvoiceDispatcher

import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service,ApprovalEffectRow
from app.modules.m24_billing import write_ahead as wa
from app.modules.m24_billing.invoice_dispatcher import InvoiceStepRow
from app.modules.m24_billing.repository import TenantBillingRow

@pytest.fixture(params=['sqlite','postgres'])
def env(tmp_path,request):
    if request.param=='postgres':
        import pgserver
        pg=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');uri=pg.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri=f'sqlite:///{tmp_path}/invoice.db'
    engine=create_engine(uri);Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False);svc=Service(session_factory=sessions)
    with sessions.begin() as db:db.add(TenantBillingRow(tenant_id='t1',customer_id='cus_fixture'))
    a=svc.submit(module_id=24,action_type='issue_invoice',user_id='t1',payload={'tenant_id':'t1','provider':'stripe','effect':'create_draft_invoice','customer_id':'cus_fixture','description':'Reviewed draft','amount_cents':1234,'currency':'usd'})
    svc.decide(a['id'],ApprovalStatus.APPROVED,'owner')
    yield InvoiceRepository(svc),sessions,a
    engine.dispose()
    if request.param=='postgres':pg.cleanup()

def prepare(env):return env[0].prepare(env[2]['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')

def test_draft_first_exact_snapshot_and_one_atomic_permit(env):
    op=prepare(env);steps=env[0].steps(op['id'],'t1')
    assert set(steps)=={'draft-invoice'}
    assert steps['draft-invoice']['form']['pending_invoice_items_behavior']=='exclude'
    assert steps['draft-invoice']['provider_key']==op['id']+':draft-invoice'
    with env[1]() as db:assert len(db.scalars(select(ApprovalEffectRow)).all())==1
    assert prepare(env)['id']==op['id']

def test_uncommitted_or_unknown_draft_never_prepares_item(env):
    op=prepare(env)
    with pytest.raises(wa.DispatchRefused,match='not committed'):env[0].prepare_item(op['id'],'t1')
    with env[1].begin() as db:db.get(InvoiceStepRow,op['id']+':draft-invoice').state='outcome_unknown'
    with pytest.raises(wa.DispatchRefused):env[0].prepare_item(op['id'],'t1')
    with env[1]() as db:assert len(db.scalars(select(InvoiceStepRow)).all())==1

def test_item_snapshot_binds_committed_draft_id_not_pending_customer_item(env):
    op=prepare(env)
    with env[1].begin() as db:
        row=db.get(InvoiceStepRow,op['id']+':draft-invoice');row.state='succeeded';row.result={'id':'in_fixture','object':'invoice','customer':'cus_fixture','currency':'usd','livemode':False,'invoice':None,'amount':0}
    item=env[0].prepare_item(op['id'],'t1')
    assert item['form']['invoice']=='in_fixture' and item['form']['amount']=='1234'
    assert item['form']['discountable']=='false'
    assert item['provider_key']==op['id']+':invoice-item'
    assert env[0].prepare_item(op['id'],'t1')['id']==item['id']

def test_snapshot_failure_rolls_back_all_intent_permit(env,monkeypatch):
    from sqlalchemy.orm import Session
    original=Session.add
    def fail(self,row,*a,**kw):
        if isinstance(row,InvoiceStepRow):raise RuntimeError('snapshot insert failure')
        return original(self,row,*a,**kw)
    monkeypatch.setattr(Session,'add',fail)
    with pytest.raises(RuntimeError):prepare(env)
    with env[1]() as db:
        assert db.scalar(select(wa.OperationRow)) is None
        assert db.scalar(select(ApprovalEffectRow)) is None

def test_customer_tenant_mapping_required(env):
    with env[1].begin() as db:db.get(TenantBillingRow,'t1').customer_id='cus_other'
    with pytest.raises(wa.DispatchRefused,match='mapping'):prepare(env)
    with env[1]() as db:assert db.scalar(select(ApprovalEffectRow)) is None

import asyncio,httpx
from urllib.parse import parse_qs
from datetime import datetime,timezone
from app.modules.m24_billing.invoice_dispatcher import InvoiceAdapter,InvoiceStepAttemptRow

def ready(env,monkeypatch):
    monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    with env[1].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='fixture-only',verified_at=datetime.now(timezone.utc)))

class MockStripe:
    def __init__(self,*,fail=None,mismatch=None):self.calls=[];self.effects={};self.keys={};self.fail=fail;self.mismatch=mismatch;self.invoice=None;self.item=None
    def __call__(self,request):
        assert request.headers['Stripe-Version']=='2026-09-30.endive'
        self.calls.append((request.method,request.url.path))
        if request.method=='GET':
            invoice={**self.invoice,'total':1234,'lines':{'has_more':False,'data':[{'amount':1234,'currency':'usd','description':'Reviewed draft','parent':{'invoice_item_details':{'invoice_item':self.item['id']}}}]}}
            if self.mismatch=='total':invoice['total']=9999
            if self.mismatch=='lines':invoice['lines']['has_more']=True
            if self.mismatch=='item':invoice['lines']['data'][0]['parent']['invoice_item_details']['invoice_item']='ii_wrong'
            return httpx.Response(200,json=invoice)
        form={k:v[0] for k,v in parse_qs(request.content.decode()).items()};role=form['metadata[atlas_operation_step]'];key=request.headers['Idempotency-Key']
        if key in self.keys:
            before,body=self.keys[key]
            assert before==form
            return httpx.Response(200,json=body)
        md={k[9:-1]:v for k,v in form.items() if k.startswith('metadata[')}
        if role=='draft-invoice':
            assert form['pending_invoice_items_behavior']=='exclude' and form['auto_advance']=='false'
            body={'id':'in_fixture','object':'invoice','customer':form['customer'],'currency':form['currency'],'livemode':False,'status':'draft','auto_advance':False,'total':0,'metadata':md};self.invoice=body
        else:
            assert self.invoice is not None and form['invoice']==self.invoice['id'] and form['discountable']=='false'
            body={'id':'ii_fixture','object':'invoiceitem','customer':form['customer'],'currency':form['currency'],'livemode':False,'invoice':form['invoice'],'amount':int(form['amount']),'description':form['description'],'metadata':md};self.item=body
        self.keys[key]=(form,body);self.effects[role]=body
        if self.fail==role:raise httpx.ReadTimeout('after fixture acceptance',request=request)
        return httpx.Response(200,json=body)

def dispatch(env,op,mock):return asyncio.run(InvoiceDispatcher(env[0],InvoiceAdapter('sk_test_fixture','test-account',httpx.MockTransport(mock))).dispatch(op['id'],'t1'))


def test_draft_first_item_attachment_final_total_and_replay(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe()
    result=dispatch(env,op,mock)
    assert result['state']=='succeeded' and result['result']['invoice_id']=='in_fixture'
    assert mock.calls==[('POST','/v1/invoices'),('POST','/v1/invoiceitems'),('GET','/v1/invoices/in_fixture')]
    assert dispatch(env,op,mock)['result']==result['result'] and len(mock.calls)==3
    assert len(mock.effects)==2
    with env[1]() as db:assert len(db.scalars(select(InvoiceStepAttemptRow)).all())==2

@pytest.mark.parametrize('role',['draft-invoice','invoice-item'])
def test_step_accepted_timeout_stays_unknown_no_repeat(env,monkeypatch,role):
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe(fail=role)
    result=dispatch(env,op,mock);assert result['state']=='outcome_unknown' and result['step']==role and result['step_state']=='outcome_unknown'
    calls=list(mock.calls);again=dispatch(env,op,mock)
    assert again['state']=='outcome_unknown' and mock.calls==calls
    assert len(mock.effects)==(1 if role=='draft-invoice' else 2)
    if role=='draft-invoice':assert set(env[0].steps(op['id'],'t1'))=={'draft-invoice'}

@pytest.mark.parametrize('mismatch',['total','lines','item'])
def test_final_total_or_incomplete_binding_holds_without_compensation(env,monkeypatch,mismatch):
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe(mismatch=mismatch)
    result=dispatch(env,op,mock);assert result['state']=='outcome_unknown'
    calls=list(mock.calls);assert dispatch(env,op,mock)['state']=='outcome_unknown' and mock.calls==calls
    assert len(mock.effects)==2 and all(c[0] in {'GET','POST'} for c in mock.calls)


def test_hard_readiness_with_forged_active_row_zero_calls(env):
    op=prepare(env);mock=MockStripe()
    with env[1].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='forged',verified_at=datetime.now(timezone.utc)))
    with pytest.raises(wa.DispatchRefused):dispatch(env,op,mock)
    assert mock.calls==[]


def test_invoice_item_must_not_claim_late_draft(env,monkeypatch):
    from datetime import timedelta
    op=prepare(env);ready(env,monkeypatch);fence=env[0].claim_step(op['id'],'t1','draft-invoice')
    with env[1].begin() as db:db.get(InvoiceStepRow,op['id']+':draft-invoice').lease_until=datetime.now(timezone.utc)-timedelta(seconds=2)
    receipt={'id':'in_fixture','object':'invoice','customer':'cus_fixture','currency':'usd','livemode':False,'invoice':None,'amount':0}
    assert env[0].step_outcome(op['id'],'t1','draft-invoice',fence,state='succeeded',result=receipt)['step']['state']=='succeeded_late'
    with pytest.raises(wa.DispatchRefused):env[0].prepare_item(op['id'],'t1')


def test_step_claim_commit_ack_loss_no_call(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe();original=env[0].claim_step
    def fail(*a,**kw):original(*a,**kw);raise RuntimeError('ack loss')
    monkeypatch.setattr(env[0],'claim_step',fail)
    result=dispatch(env,op,mock);assert result['state']=='outcome_unknown' and mock.calls==[]
    assert env[0].step(op['id'],'t1','draft-invoice')['step']['state']=='dispatching'

@pytest.mark.parametrize('role',['draft-invoice','invoice-item'])
@pytest.mark.parametrize('point',['attempt','accepted','receipt'])
def test_real_sigkill_substep_pid_distinct_resume_no_repeated_mutation(env,tmp_path,role,point):
    import subprocess,sys,os,time,signal,json
    op=prepare(env);readyfile=tmp_path/'ready';effectfile=tmp_path/'effects';answer=tmp_path/'answer'
    with env[1].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='fixture-only',verified_at=datetime.now(timezone.utc)))
    script=r'''
import asyncio,json,os,time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m00_approval_center.service import Service
from app.modules.m24_billing.repository import TenantBillingRow
from app.modules.m24_billing import write_ahead as wa
from app.modules.m24_billing.invoice_dispatcher import InvoiceRepository,InvoiceDispatcher,InvoiceAdapter
wa.require_dispatch_ready=lambda:None
repo=InvoiceRepository(Service(session_factory=sessionmaker(bind=create_engine(os.environ['DATABASE']),expire_on_commit=False)))
def barrier(role,point):
 if os.environ['MODE']=='kill' and role==os.environ['ROLE'] and point==os.environ['POINT']:
  with open(os.environ['READY'],'w') as f:f.write(str(os.getpid()));f.flush();os.fsync(f.fileno())
  while True:time.sleep(.05)
original_claim=repo.claim_step;original_outcome=repo.step_outcome
def claim(op,tenant,role):
 fence=original_claim(op,tenant,role);barrier(role,'attempt');return fence
repo.claim_step=claim
def outcome(op,tenant,role,*a,**kw):
 result=original_outcome(op,tenant,role,*a,**kw);barrier(role,'receipt');return result
repo.step_outcome=outcome
class Adapter(InvoiceAdapter):
 async def invoke(self,request):
  from urllib.parse import parse_qs
  form={k:v[0] for k,v in parse_qs(request.content.decode()).items()};role=form['metadata[atlas_operation_step]']
  with open(os.environ['EFFECTS'],'a') as f:f.write(role+'\n');f.flush();os.fsync(f.fileno())
  barrier(role,'accepted')
  md={k[9:-1]:v for k,v in form.items() if k.startswith('metadata[')}
  if role=='draft-invoice':return {'id':'in_fixture','object':'invoice','customer':'cus_fixture','currency':'usd','livemode':False,'status':'draft','auto_advance':False,'total':0,'metadata':md}
  return {'id':'ii_fixture','object':'invoiceitem','customer':'cus_fixture','currency':'usd','livemode':False,'invoice':'in_fixture','amount':1234,'description':'Reviewed draft','metadata':md}
 async def read_invoice(self,ident):
  parent=repo.get(os.environ['OP'],'t1')
  return {'id':'in_fixture','object':'invoice','customer':'cus_fixture','currency':'usd','livemode':False,'status':'draft','auto_advance':False,'total':1234,
   'metadata':{'atlas_operation_id':parent['id'],'atlas_operation_step':'draft-invoice','atlas_approval_id':parent['approval_id']},
   'lines':{'has_more':False,'data':[{'amount':1234,'currency':'usd','description':'Reviewed draft','parent':{'invoice_item_details':{'invoice_item':'ii_fixture'}}}]}}
result=asyncio.run(InvoiceDispatcher(repo,Adapter('sk_test_fixture','test-account')).dispatch(os.environ['OP'],'t1'))
with open(os.environ['ANSWER'],'w') as f:json.dump({'pid':os.getpid(),'result':result},f,default=str)
'''
    settings={**os.environ,'DATABASE':str(env[1].kw['bind'].url),'OP':op['id'],'READY':str(readyfile),'EFFECTS':str(effectfile),'ANSWER':str(answer),'ROLE':role,'POINT':point,'MODE':'kill'}
    child=subprocess.Popen([sys.executable,'-c',script],env=settings)
    try:
        until=time.monotonic()+12
        while not readyfile.exists() and time.monotonic()<until:
            assert child.poll() is None;time.sleep(.02)
        assert readyfile.exists() and int(readyfile.read_text())==child.pid
        os.kill(child.pid,signal.SIGKILL);assert child.wait(5)==-signal.SIGKILL
        previous=effectfile.read_text().splitlines() if effectfile.exists() else []
        restart=subprocess.run([sys.executable,'-c',script],env={**settings,'MODE':'restart'},capture_output=True,text=True,timeout=12)
        assert restart.returncode==0,restart.stderr
        result=json.loads(answer.read_text());assert result['pid']!=child.pid
        effects=effectfile.read_text().splitlines() if effectfile.exists() else []
        assert effects.count('draft-invoice')<=1 and effects.count('invoice-item')<=1
        if point=='receipt':assert result['result']['state']=='succeeded' and effects==['draft-invoice','invoice-item']
        else:assert result['result']['state']=='outcome_unknown' and effects==previous
        if role=='draft-invoice' and point!='receipt':assert set(env[0].steps(op['id'],'t1'))=={'draft-invoice'}
    finally:
        if child.poll() is None:child.kill();child.wait(5)

@pytest.mark.parametrize('database',['sqlite','postgres'])
def test_populated_invoice_migration_no_backfill_downgrade_refuses(tmp_path,database):
    import subprocess,sys,os
    from pathlib import Path
    from sqlalchemy import text
    root=Path(__file__).resolve().parents[2]
    if database=='postgres':
        import pgserver
        server=pgserver.get_server(tmp_path/'migration-pg',cleanup_mode='stop');uri=server.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri=f'sqlite:///{tmp_path}/migration.db'
    runenv={**os.environ,'ATLAS_DATABASE_URL':uri,'PYTHONPATH':'backend'}
    def migrate(*args):return subprocess.run([sys.executable,'-m','alembic',*args],cwd=root,env=runenv,capture_output=True,text=True,timeout=30)
    result=migrate('upgrade','20261009_m24_checkout_snapshot');assert result.returncode==0,result.stderr
    engine=create_engine(uri);sessions=sessionmaker(bind=engine,expire_on_commit=False);svc=Service(session_factory=sessions)
    with sessions.begin() as db:db.add(TenantBillingRow(tenant_id='t1',customer_id='cus_fixture'))
    payload={'tenant_id':'t1','provider':'stripe','effect':'create_draft_invoice','customer_id':'cus_fixture','description':'Reviewed draft','amount_cents':1234,'currency':'usd'}
    a=svc.submit(module_id=24,action_type='issue_invoice',user_id='t1',payload=payload);svc.decide(a['id'],ApprovalStatus.APPROVED,'owner')
    old=wa.OperationRepository(svc).prepare(a['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    with engine.connect() as db:assert db.execute(text('SELECT count(*) FROM m24_invoice_steps')).scalar()==0
    with pytest.raises(wa.DispatchRefused):InvoiceRepository(svc).steps(old['id'],'t1')
    result=migrate('downgrade','20261009_m24_checkout_snapshot');assert result.returncode==0,result.stderr
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    b=svc.submit(module_id=24,action_type='issue_invoice',user_id='t1',payload=payload);svc.decide(b['id'],ApprovalStatus.APPROVED,'owner')
    InvoiceRepository(svc).prepare(b['id'],'t1',provider_account='test-account',environment='test',api_version='2026-09-30.endive',actor='worker')
    result=migrate('downgrade','20261009_m24_checkout_snapshot');assert result.returncode!=0 and 'destructive downgrade refused' in result.stderr
    engine.dispose()
    if database=='postgres':server.cleanup()


def test_concurrent_step_claim_one_attempt(env,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    op=prepare(env);ready(env,monkeypatch);barrier=threading.Barrier(2)
    def claim():
        barrier.wait(5)
        try:return env[0].claim_step(op['id'],'t1','draft-invoice')
        except wa.DispatchRefused:return 'refused'
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:claim(),range(2)))
    assert results.count('refused')==1
    with env[1]() as db:assert len(db.scalars(select(InvoiceStepAttemptRow)).all())==1


def test_wrong_account_cannot_retrieve_after_committed_steps(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe()
    adapter=InvoiceAdapter('sk_test_fixture','foreign-account',httpx.MockTransport(mock))
    with pytest.raises(wa.DispatchRefused):asyncio.run(InvoiceDispatcher(env[0],adapter).dispatch(op['id'],'t1'))
    assert mock.calls==[]

@pytest.mark.parametrize('change',['key','form','account','version','authority','deadline'])
def test_invoice_changed_bindings_refuse_zero_provider(env,monkeypatch,change):
    from datetime import timedelta
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe()
    with env[1].begin() as db:
        parent=db.get(wa.OperationRow,op['id']);step=db.get(InvoiceStepRow,op['id']+':draft-invoice')
        if change=='key':step.provider_key='changed'
        elif change=='form':step.form={**step.form,'currency':'eur'}
        elif change=='account':parent.provider_account='foreign'
        elif change=='version':parent.api_version='changed'
        elif change=='authority':db.get(ApprovalRequestRow,env[2]['id']).status='denied'
        else:db.get(ApprovalRequestRow,env[2]['id']).expires_at=datetime.now(timezone.utc)-timedelta(seconds=3)
    try:result=dispatch(env,op,mock)
    except (wa.DispatchRefused,ValueError):pass
    assert mock.calls==[]


def test_invoice_claim_readback_mismatch_no_adapter(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe();original=env[0].step
    def mismatch(*a,**kw):
        value=original(*a,**kw)
        if value['step']['state']=='dispatching':value['step']['fence']='bad-readback'
        return value
    monkeypatch.setattr(env[0],'step',mismatch)
    result=dispatch(env,op,mock);assert result['state']=='outcome_unknown' and mock.calls==[]


def test_invoice_lease_expired_before_entry_is_zero_provider(env,monkeypatch):
    from datetime import timedelta
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe();original=env[0].claim_step
    def expire(*a,**kw):
        fence=original(*a,**kw)
        with env[1].begin() as db:db.get(InvoiceStepRow,op['id']+':draft-invoice').lease_until=datetime.now(timezone.utc)-timedelta(seconds=2)
        return fence
    monkeypatch.setattr(env[0],'claim_step',expire)
    result=dispatch(env,op,mock);assert result['step_state']=='failed_before_dispatch' and mock.calls==[]


def test_invoice_accepted_receipt_storage_loss_no_item_and_no_retry(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe()
    monkeypatch.setattr(env[0],'step_outcome',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('lost receipt DB')))
    result=dispatch(env,op,mock);assert result['state']=='outcome_unknown'
    assert len(mock.calls)==len(mock.effects)==1
    assert dispatch(env,op,mock)['state']=='outcome_unknown' and len(mock.calls)==1


def test_invoice_strict_draft_evidence_refuses_id_only_dependency(env):
    op=prepare(env)
    with env[1].begin() as db:
        draft=db.get(InvoiceStepRow,op['id']+':draft-invoice');draft.state='succeeded';draft.result={'id':'in_fabricated'}
    with pytest.raises(ValueError):env[0].prepare_item(op['id'],'t1')
    with env[1]() as db:assert len(db.scalars(select(InvoiceStepRow)).all())==1


def test_invoice_service_routing_never_legacy_provider(env,monkeypatch):
    from app.modules.m24_billing.service import Service as BillingService
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe()
    class Repo:
        def approval(self,aid):return {'status':'approved','payload':env[0].get(op['id'],'t1')['request']}
        def record_execution(self,*a):raise AssertionError('legacy receipt')
    class Legacy:
        async def create_invoice(self,*a):raise AssertionError('legacy provider bypass')
    dispatcher=InvoiceDispatcher(env[0],InvoiceAdapter('sk_test_fixture','test-account',httpx.MockTransport(mock)))
    service=BillingService(None,Repo(),Legacy(),invoice_dispatcher=dispatcher)
    assert asyncio.run(service.execute_approved(env[2]['id'],'t1'))['state']=='succeeded'
    assert len(mock.calls)==3


def test_old_omitted_pending_item_mock_contract_is_excluded_not_attached():
    from app.modules.m24_billing.stripe_client import StripeClient
    items=[]
    def handler(request):
        form={k:v[0] for k,v in parse_qs(request.content.decode()).items()}
        if request.url.path.endswith('invoiceitems'):
            assert 'invoice' not in form;items.append(form);return httpx.Response(200,json={'id':'ii_pending'})
        assert 'pending_invoice_items_behavior' not in form
        # Docs-based mock of omitted default exclude, NOT verified account default.
        return httpx.Response(200,json={'id':'in_empty','total':0,'lines':{'has_more':False,'data':[]}})
    result=asyncio.run(StripeClient('sk_test_fixture',httpx.MockTransport(handler)).create_invoice('cus_fixture','Reviewed draft',1234,'usd','approval-fixture'))
    assert len(items)==1 and result['total']==0 and result['lines']['data']==[]


def test_invoice_http_status_foreign_tenant_404_and_private_forms_hidden(env,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    from app.modules.m24_billing.routes import router,require_tenant
    import app.modules.m00_approval_center.service as approval_module
    op=prepare(env);monkeypatch.setattr(approval_module,'default_service',lambda:env[0].approvals)
    app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:SimpleNamespace(tenant_id='foreign')
    with TestClient(app) as client:assert client.get('/billing/invoice-operations/'+op['id']).status_code==404
    app.dependency_overrides[require_tenant]=lambda:SimpleNamespace(tenant_id='t1')
    with TestClient(app) as client:
        response=client.get('/billing/invoice-operations/'+op['id']);assert response.status_code==200
        data=response.json();assert 'request' not in data and 'provider_account' not in data
        assert set(data['steps']['draft-invoice'])=={'state','result','failure'}


def test_invoice_step_uncertain_cannot_be_marked_safe_by_same_fence(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);fence=env[0].claim_step(op['id'],'t1','draft-invoice')
    env[0].step_outcome(op['id'],'t1','draft-invoice',fence,state='outcome_unknown')
    with pytest.raises(wa.DispatchRefused,match='unknown'):env[0].step_outcome(op['id'],'t1','draft-invoice',fence,state='failed_before_dispatch')


def test_invoice_finish_rejects_fabricated_final_raw(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=MockStripe()
    # Perform both durable steps, leave parent uncompleted for explicit final control.
    dispatcher=InvoiceDispatcher(env[0],InvoiceAdapter('sk_test_fixture','test-account',httpx.MockTransport(mock)))
    asyncio.run(dispatcher._step(op['id'],'t1','draft-invoice'));env[0].prepare_item(op['id'],'t1');asyncio.run(dispatcher._step(op['id'],'t1','invoice-item'))
    with pytest.raises(ValueError):env[0].finish(op['id'],'t1','in_fixture','ii_fixture',{'id':'in_fixture','total':1234})
    assert env[0].get(op['id'],'t1')['state']=='prepared'


def test_sql_cutover_update_barrier_alone_refuses_locked_row(env,monkeypatch):
    """Isolate SQL barrier: bypass in-process readiness, never call entry/final guards."""
    op=prepare(env)
    monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    with env[1].begin() as db:
        db.add(wa.CutoverRow(id=1,protocol_epoch=0,state='locked',verification_digest=None,verified_at=None))
    with pytest.raises(wa.DispatchRefused,match='cutover locked'):
        env[0].claim_step(op['id'],'t1','draft-invoice')
    assert env[0].step(op['id'],'t1','draft-invoice')['step']['state']=='prepared'
    with env[1]() as db:
        assert db.scalar(select(InvoiceStepAttemptRow)) is None
