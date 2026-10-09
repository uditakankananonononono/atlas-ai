"""Signature admission + durable lifecycle, fixture-only TEST readiness."""
import copy,json,hmac,hashlib,time,asyncio
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m24_billing import write_ahead as wa
from app.modules.m24_billing.inbox import InboxRepository,WebhookAdmission,InboxRow,ResourceBindingRow,QuarantineRow,InboxRefused,identity
from app.modules.m24_billing.repository import TenantBillingRow
from app.modules.m24_billing.checkout_dispatcher import API_VERSION
from app.modules.m24_billing.schemas import BillingEventIn
from app.modules.m24_billing.service import Service

@pytest.fixture(params=['sqlite','postgres'])
def env(tmp_path,request,m24_postgres_schema):
    if request.param=='postgres':
        import pgserver
        pg=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');uri=pg.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri=f'sqlite:///{tmp_path}/inbox.db'
    engine=create_engine(uri);m24_postgres_schema(engine);Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    with sessions.begin() as db:
        db.add(TenantBillingRow(tenant_id='t1',customer_id='cus_fixture',subscription_id='sub_fixture',status='active'))
        db.add(ResourceBindingRow(identity=identity('acct_fixture','sub_fixture'),provider_account='acct_fixture',environment='test',resource_id='sub_fixture',tenant_id='t1',customer_id='cus_fixture',version=0))
    yield InboxRepository(sessions),sessions,WebhookAdmission('whsec_fixture','acct_fixture')
    engine.dispose()
    if request.param=='postgres':pg.cleanup()

def event(ident='evt_fixture',created=100,status='past_due'):
    return {'id':ident,'object':'event','type':'customer.subscription.updated','created':created,'livemode':False,'api_version':API_VERSION,
        'data':{'object':{'id':'sub_fixture','object':'subscription','customer':'cus_fixture','status':status,'cancel_at_period_end':False,'livemode':False,'metadata':{'atlas_tenant_id':'t1'}}}}

def signed(env,monkeypatch,data=None):
    monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    raw=json.dumps(data or event(),sort_keys=True).encode();now=int(time.time())
    sig=hmac.new(b'whsec_fixture',str(now).encode()+b'.'+raw,hashlib.sha256).hexdigest()
    return env[2].verify(raw,f't={now},v1={sig}')

def admit(env,monkeypatch,data=None):return env[0].admit(signed(env,monkeypatch,data))

def test_admit_pending_then_atomic_apply_replay(env,monkeypatch):
    ident=admit(env,monkeypatch)
    assert env[0].get(ident)['state']=='pending'
    with env[1]() as db:assert db.get(TenantBillingRow,'t1').status=='active'
    assert env[0].apply(ident)['processed'] is True
    assert env[0].apply(ident)['processed'] is True
    assert admit(env,monkeypatch)==ident
    with env[1]() as db:
        assert db.get(TenantBillingRow,'t1').status=='past_due'
        assert db.get(ResourceBindingRow,identity('acct_fixture','sub_fixture')).version==100
        assert len(db.scalars(select(InboxRow)).all())==1


def test_unsigned_same_id_separate_quarantine_then_signed_applies(env,monkeypatch):
    data=event();out=Service(None,None,None,inbox=env[0]).ingest_event(BillingEventIn(**{k:data[k] for k in ('id','type','created','data')}),trusted_provider=True)
    assert out.processed is False
    ident=admit(env,monkeypatch);assert env[0].apply(ident)['state']=='applied'
    with env[1]() as db:assert len(db.scalars(select(QuarantineRow)).all())==1


def test_apply_transaction_failure_retains_pending_and_redelivery(env,monkeypatch):
    ident=admit(env,monkeypatch)
    def fail(point):
        if point=='before-apply-commit':raise RuntimeError('lost commit')
    with pytest.raises(RuntimeError):env[0].apply(ident,hook=fail)
    with env[1]() as db:
        assert db.get(TenantBillingRow,'t1').status=='active'
        assert db.get(ResourceBindingRow,identity('acct_fixture','sub_fixture')).version==0
        assert db.get(InboxRow,ident).state=='pending' and db.get(InboxRow,ident).applied_at is None
    assert admit(env,monkeypatch)==ident
    assert env[0].apply(ident)['state']=='applied'


def test_changed_digest_same_identity_conflict(env,monkeypatch):
    ident=admit(env,monkeypatch)
    with pytest.raises(InboxRefused,match='changed digest'):admit(env,monkeypatch,event(status='canceled'))
    assert env[0].get(ident)['state']=='pending'
    with env[1]() as db:assert len(db.scalars(select(QuarantineRow)).all())==1


def test_older_and_equal_timestamp_conflicts_do_not_overwrite(env,monkeypatch):
    newer=admit(env,monkeypatch,event('evt_new',200,'canceled'));env[0].apply(newer)
    old=admit(env,monkeypatch,event('evt_old',100,'active'));assert env[0].apply(old)['state']=='ignored_stale'
    tie=admit(env,monkeypatch,event('evt_tie',200,'active'));assert env[0].apply(tie)['state']=='held'
    with env[1]() as db:assert db.get(TenantBillingRow,'t1').status=='canceled'


@pytest.mark.parametrize('field,value',[('livemode',True),('api_version','foreign'),('account','acct_foreign'),('object','subscription')])
def test_signed_envelope_binding_refuses_before_admission(env,monkeypatch,field,value):
    data=event();data[field]=value
    with pytest.raises(InboxRefused):admit(env,monkeypatch,data)
    with env[1]() as db:assert db.scalar(select(InboxRow)) is None


@pytest.mark.parametrize('field,value',[('customer','cus_foreign'),('metadata',{'atlas_tenant_id':'foreign'}),('livemode',True),('status','invalid'),('cancel_at_period_end','false')])
def test_object_binding_refuses_lifecycle_pending(env,monkeypatch,field,value):
    data=event();data['data']['object'][field]=value;ident=admit(env,monkeypatch,data)
    with pytest.raises(InboxRefused):env[0].apply(ident)
    assert env[0].get(ident)['state']=='pending'
    with env[1]() as db:assert db.get(TenantBillingRow,'t1').status=='active'


def test_signature_and_hard_readiness_fail_closed(env):
    from app.modules.m24_billing.webhooks import StripeSignatureError
    with pytest.raises(wa.DispatchRefused):env[2].verify(b'{}','')


def test_signature_wrong_secret_and_stale_refuse(env,monkeypatch):
    from app.modules.m24_billing.webhooks import StripeSignatureError
    monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    for header in ('t=1,v1=bad',f't={int(time.time())},v1=bad'):
        with pytest.raises(StripeSignatureError):env[2].verify(json.dumps(event()).encode(),header)
    with env[1]() as db:assert db.scalar(select(InboxRow)) is None


def checkout_event(env,monkeypatch,*,payment='paid',deadline=None):
    from app.modules.m00_approval_center.service import Service as ApprovalService
    from app.core.models import ApprovalStatus
    from app.modules.m24_billing.checkout_dispatcher import CheckoutRepository
    from app.modules.m24_billing.service import PLANS
    svc=ApprovalService(session_factory=env[1]);a=svc.submit(module_id=24,action_type='create_subscription_checkout',user_id='t1',payload={
        'tenant_id':'t1','provider':'stripe','mode':'subscription','plan':PLANS['pro'].model_dump(),'success_url':'https://example.test/s','cancel_url':'https://example.test/c'})
    svc.decide(a['id'],ApprovalStatus.APPROVED,'owner')
    op=CheckoutRepository(svc).prepare(a['id'],'t1',provider_account='acct_fixture',environment='test',api_version=API_VERSION,actor='worker')
    with env[1].begin() as db:
        row=db.get(wa.OperationRow,op['id']);row.state='succeeded';row.result={'id':'cs_test_fixture','amount_total':2900}
        if deadline is not None:
            from datetime import datetime,timezone
            row.dispatch_not_after=datetime.fromtimestamp(deadline,timezone.utc)
    data=event();data['type']='checkout.session.completed';data['data']['object']={
        'id':'cs_test_fixture','object':'checkout.session','customer':'cus_fixture','subscription':'sub_fixture','livemode':False,
        'status':'complete','payment_status':payment,'mode':'subscription','currency':'usd','amount_total':2900,'client_reference_id':'t1',
        'metadata':{'tenant_id':'t1','plan_id':'pro','atlas_operation_id':op['id'],'atlas_operation_step':'checkout','atlas_approval_id':a['id']}}
    return data


def test_paid_checkout_requires_durable_bound_receipt_and_deadline(env,monkeypatch):
    data=checkout_event(env,monkeypatch,deadline=200);ident=admit(env,monkeypatch,data)
    assert env[0].apply(ident)['state']=='applied'
    with env[1]() as db:assert db.get(TenantBillingRow,'t1').plan_id=='pro'


@pytest.mark.parametrize('bad',['unpaid','no_payment_required','deadline','amount','plan','reference','operation','approval'])
def test_checkout_single_binding_violation_never_grants_plan(env,monkeypatch,bad):
    data=checkout_event(env,monkeypatch,deadline=50 if bad=='deadline' else 200);obj=data['data']['object']
    if bad in {'unpaid','no_payment_required'}:obj['payment_status']=bad
    elif bad=='amount':obj['amount_total']=1
    elif bad=='plan':obj['metadata']['plan_id']='team'
    elif bad=='reference':obj['client_reference_id']='foreign'
    elif bad=='operation':obj['metadata']['atlas_operation_id']='missing'
    elif bad=='approval':obj['metadata']['atlas_approval_id']='missing'
    ident=admit(env,monkeypatch,data)
    with pytest.raises(InboxRefused):env[0].apply(ident)
    with env[1]() as db:
        assert db.get(TenantBillingRow,'t1').plan_id=='free'
        assert db.get(ResourceBindingRow,identity('acct_fixture','sub_fixture')).version==0
        assert db.get(InboxRow,ident).state=='pending'


def test_invoice_paid_atomic_and_foreign_binding_refuses(env,monkeypatch):
    from app.modules.m24_billing.repository import InvoiceRow
    with env[1].begin() as db:db.add(ResourceBindingRow(identity=identity('acct_fixture','in_fixture'),provider_account='acct_fixture',environment='test',resource_id='in_fixture',tenant_id='t1',customer_id='cus_fixture',version=0))
    data=event();data['type']='invoice.paid';data['data']['object']={
        'id':'in_fixture','object':'invoice','customer':'cus_fixture','livemode':False,'currency':'usd','status':'paid','amount_due':100,'amount_paid':100,'metadata':{'atlas_tenant_id':'t1'}}
    ident=admit(env,monkeypatch,data);assert env[0].apply(ident)['state']=='applied'
    with env[1]() as db:assert db.get(InvoiceRow,'in_fixture').amount_paid==100
    data['id']='evt_bad';data['created']=200;data['data']['object']['customer']='cus_foreign'
    bad=admit(env,monkeypatch,data)
    with pytest.raises(InboxRefused):env[0].apply(bad)
    with env[1]() as db:assert db.get(InvoiceRow,'in_fixture').amount_paid==100


def test_http_injected_signed_path_and_unsigned_namespace(env,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m24_billing.routes import router,get_service
    monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    service=Service(None,None,None,inbox=env[0],webhook_admission=env[2]);app=FastAPI();app.include_router(router);app.dependency_overrides[get_service]=lambda:service
    data=event();raw=json.dumps(data).encode();now=int(time.time());sig=hmac.new(b'whsec_fixture',str(now).encode()+b'.'+raw,hashlib.sha256).hexdigest()
    with TestClient(app) as client:
        assert client.post('/billing/events',json={k:data[k] for k in ('id','type','created','data')}).json()['processed'] is False
        assert client.post('/billing/stripe-webhook',content=raw,headers={'stripe-signature':f't={now},v1=bad'}).status_code==400
        response=client.post('/billing/stripe-webhook',content=raw,headers={'stripe-signature':f't={now},v1={sig}'})
        assert response.status_code==200 and response.json()['processed'] is True


def test_default_signed_path_refuses_without_configuration():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m24_billing.routes import router,get_service
    service=Service(None,None,None);app=FastAPI();app.include_router(router);app.dependency_overrides[get_service]=lambda:service
    with TestClient(app) as client:assert client.post('/billing/stripe-webhook',content=b'{}').status_code==409


@pytest.mark.parametrize('point',['pending','inside-apply','after-apply-commit'])
def test_real_sigkill_inbox_pending_apply_marker_resume(env,monkeypatch,tmp_path,point):
    import os,sys,subprocess,signal
    ident=admit(env,monkeypatch);ready=tmp_path/'ready';answer=tmp_path/'answer'
    script=r'''
import os,time,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m24_billing.inbox import InboxRepository
repo=InboxRepository(sessionmaker(bind=create_engine(os.environ['DATABASE']),expire_on_commit=False))
def hook(point):
 if os.environ['MODE']=='kill' and point==os.environ['POINT']:
  with open(os.environ['READY'],'w') as f:f.write(str(os.getpid()));f.flush();os.fsync(f.fileno())
  while True:time.sleep(.05)
hook('pending')
result=repo.apply(os.environ['IDENT'],hook=hook)
with open(os.environ['ANSWER'],'w') as f:json.dump({'pid':os.getpid(),'result':result},f,default=str)
'''
    settings={**os.environ,'DATABASE':str(env[1].kw['bind'].url),'IDENT':ident,'READY':str(ready),'ANSWER':str(answer),'MODE':'kill','POINT':point}
    child=subprocess.Popen([sys.executable,'-c',script],env=settings)
    try:
        until=time.monotonic()+12
        while not ready.exists() and time.monotonic()<until:
            assert child.poll() is None;time.sleep(.02)
        assert ready.exists() and int(ready.read_text())==child.pid
        os.kill(child.pid,signal.SIGKILL);assert child.wait(5)==-signal.SIGKILL
        with env[1]() as db:
            row=db.get(InboxRow,ident);local=db.get(TenantBillingRow,'t1');binding=db.get(ResourceBindingRow,identity('acct_fixture','sub_fixture'))
            assert row.state==('applied' if point=='after-apply-commit' else 'pending')
            assert local.status==('past_due' if point=='after-apply-commit' else 'active')
            assert binding.version==(100 if point=='after-apply-commit' else 0)
        restart=subprocess.run([sys.executable,'-c',script],env={**settings,'MODE':'resume'},capture_output=True,text=True,timeout=12)
        assert restart.returncode==0,restart.stderr
        result=json.loads(answer.read_text());assert result['pid']!=child.pid and result['result']['state']=='applied'
        with env[1]() as db:assert db.get(ResourceBindingRow,identity('acct_fixture','sub_fixture')).version==100
    finally:
        if child.poll() is None:child.kill();child.wait(5)


def test_concurrent_apply_same_event_one_atomic_marker(env,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    ident=admit(env,monkeypatch);barrier=threading.Barrier(2)
    def apply():barrier.wait(5);return env[0].apply(ident)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:apply(),range(2)))
    assert all(r['state']=='applied' for r in results)
    with env[1]() as db:
        assert db.get(ResourceBindingRow,identity('acct_fixture','sub_fixture')).version==100
        assert len(db.scalars(select(InboxRow)).all())==1


@pytest.mark.parametrize('database',['sqlite','postgres'])
def test_populated_inbox_migration_no_legacy_promotion_downgrade_refuses(tmp_path,database):
    import os,sys,subprocess
    from pathlib import Path
    from sqlalchemy import text
    root=Path(__file__).resolve().parents[2]
    if database=='postgres':
        import pgserver
        pg=pgserver.get_server(tmp_path/'migration-pg',cleanup_mode='stop');uri=pg.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri=f'sqlite:///{tmp_path}/migration.db'
    runenv={**os.environ,'PYTHONPATH':'backend','ATLAS_DATABASE_URL':uri}
    def migrate(*args):return subprocess.run([sys.executable,'-m','alembic',*args],cwd=root,env=runenv,capture_output=True,text=True,timeout=30)
    result=migrate('upgrade','20261009_m24_cancellation');assert result.returncode==0,result.stderr
    engine=create_engine(uri)
    with engine.begin() as db:db.execute(text("INSERT INTO m24_billing_events (id,type,payload,processed_at) VALUES ('evt_legacy','invoice.paid','{}',CURRENT_TIMESTAMP)"))
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    with engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM m24_verified_inbox')).scalar()==0
        assert db.execute(text('SELECT count(*) FROM m24_billing_events')).scalar()==1
    result=migrate('downgrade','20261009_m24_cancellation');assert result.returncode==0,result.stderr
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    sessions=sessionmaker(bind=engine,expire_on_commit=False);InboxRepository(sessions).quarantine('evt_unsigned','a'*64,'unsigned-diagnostic')
    result=migrate('downgrade','20261009_m24_cancellation');assert result.returncode!=0 and 'destructive downgrade refused' in result.stderr
    engine.dispose()
    if database=='postgres':pg.cleanup()


@pytest.mark.parametrize('kind',['customer.subscription.updated','checkout.session.completed'])
def test_missing_resource_binding_cannot_be_created_by_signed_metadata(env,monkeypatch,kind):
    from sqlalchemy import delete
    with env[1].begin() as db:db.execute(delete(ResourceBindingRow))
    data=event() if kind.startswith('customer.') else checkout_event(env,monkeypatch)
    ident=admit(env,monkeypatch,data)
    with pytest.raises(InboxRefused,match='ownership unavailable'):env[0].apply(ident)
    with env[1]() as db:
        assert db.get(TenantBillingRow,'t1').plan_id=='free'
        assert db.scalar(select(ResourceBindingRow)) is None


def test_cross_account_same_event_id_namespace_is_distinct(env,monkeypatch):
    from app.modules.m24_billing.inbox import VerifiedEvent
    first=signed(env,monkeypatch)
    # Internal verified-producer fixture, not an account supplied to public API.
    second=VerifiedEvent('acct_other',copy.deepcopy(first.payload),first.raw_digest)
    assert env[0].admit(first)!=env[0].admit(second)
    with env[1]() as db:assert len(db.scalars(select(InboxRow)).all())==2


def test_unverified_boolean_or_mapping_cannot_admit(env):
    with pytest.raises(InboxRefused):env[0].admit(event())
    with env[1]() as db:assert db.scalar(select(InboxRow)) is None


def test_legacy_apply_helper_refuses_instead_of_independent_commits():
    service=Service(None,None,None)
    with pytest.raises(InboxRefused,match='disabled'):service._apply_lifecycle_event(BillingEventIn(id='evt_fixture',type='invoice.paid',created=1,data={}))


def test_stored_payload_only_tamper_refuses_atomic_apply(env,monkeypatch):
    ident=admit(env,monkeypatch)
    with env[1].begin() as db:
        row=db.get(InboxRow,ident);payload=copy.deepcopy(row.payload);payload['data']['object']['status']='canceled';row.payload=payload
    with pytest.raises(InboxRefused,match='payload digest'):env[0].apply(ident)
    with env[1]() as db:
        assert db.get(TenantBillingRow,'t1').status=='active'
        assert db.get(InboxRow,ident).state=='pending'


def test_concurrent_newer_older_resource_events_never_revert(env,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    newer=admit(env,monkeypatch,event('evt_new',200,'canceled'));older=admit(env,monkeypatch,event('evt_old',100,'active'));barrier=threading.Barrier(2)
    def apply(ident):barrier.wait(5);return env[0].apply(ident)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(apply,(newer,older)))
    with env[1]() as db:
        assert db.get(TenantBillingRow,'t1').status=='canceled'
        assert db.get(ResourceBindingRow,identity('acct_fixture','sub_fixture')).version==200
    assert results[0]['state']=='applied' and results[1]['state'] in {'applied','ignored_stale'}


def test_future_created_bound_alone_refuses_signed_event(env,monkeypatch):
    data=event(created=int(time.time())+3600)
    with pytest.raises(InboxRefused,match='created time'):admit(env,monkeypatch,data)
    with env[1]() as db:assert db.scalar(select(InboxRow)) is None


@pytest.mark.parametrize('field,value',[('customer_id','cus_other'),('subscription_id','sub_other')])
def test_local_mapping_drift_alone_refuses(env,monkeypatch,field,value):
    ident=admit(env,monkeypatch)
    with env[1].begin() as db:setattr(db.get(TenantBillingRow,'t1'),field,value)
    with pytest.raises(InboxRefused,match='local .* mapping differs'):env[0].apply(ident)
    with env[1]() as db:
        assert db.get(TenantBillingRow,'t1').status=='active'
        assert db.get(ResourceBindingRow,identity('acct_fixture','sub_fixture')).version==0
        assert db.get(InboxRow,ident).state=='pending'


@pytest.mark.parametrize('field,value',[('state','outcome_unknown'),('result',{'id':'cs_test_other','amount_total':2900})])
def test_checkout_operation_state_or_receipt_id_alone_refuses(env,monkeypatch,field,value):
    data=checkout_event(env,monkeypatch);ident=admit(env,monkeypatch,data)
    with env[1].begin() as db:setattr(db.get(wa.OperationRow,data['data']['object']['metadata']['atlas_operation_id']),field,value)
    with pytest.raises(InboxRefused,match='durable operation differs'):env[0].apply(ident)
    with env[1]() as db:
        assert db.get(TenantBillingRow,'t1').plan_id=='free'
        assert db.get(ResourceBindingRow,identity('acct_fixture','sub_fixture')).version==0
        assert db.get(InboxRow,ident).state=='pending'


def invoice_event(env,*,status='paid',paid=100):
    with env[1].begin() as db:db.add(ResourceBindingRow(identity=identity('acct_fixture','in_fixture'),provider_account='acct_fixture',environment='test',resource_id='in_fixture',tenant_id='t1',customer_id='cus_fixture',version=0))
    data=event();data['type']='invoice.paid';data['data']['object']={
        'id':'in_fixture','object':'invoice','customer':'cus_fixture','livemode':False,'currency':'usd','status':status,'amount_due':100,'amount_paid':paid,'metadata':{'atlas_tenant_id':'t1'}}
    return data


@pytest.mark.parametrize('field,value',[('status','open'),('amount_paid',99)])
def test_invoice_confirmed_paid_single_field_refuses(env,monkeypatch,field,value):
    from app.modules.m24_billing.repository import InvoiceRow
    data=invoice_event(env);data['data']['object'][field]=value;ident=admit(env,monkeypatch,data)
    with pytest.raises(InboxRefused,match='not confirmed paid'):env[0].apply(ident)
    with env[1]() as db:
        assert db.get(InvoiceRow,'in_fixture') is None
        assert db.get(ResourceBindingRow,identity('acct_fixture','in_fixture')).version==0
        assert db.get(InboxRow,ident).state=='pending'


def test_current_invoice_foreign_tenant_alone_refuses(env,monkeypatch):
    from app.modules.m24_billing.repository import InvoiceRow
    data=invoice_event(env)
    with env[1].begin() as db:db.add(InvoiceRow(id='in_fixture',tenant_id='foreign',status='open',currency='usd',amount_due=100,amount_paid=0))
    ident=admit(env,monkeypatch,data)
    with pytest.raises(InboxRefused,match='invoice tenant differs'):env[0].apply(ident)
    with env[1]() as db:
        row=db.get(InvoiceRow,'in_fixture');assert row.tenant_id=='foreign' and row.status=='open' and row.amount_paid==0
        assert db.get(ResourceBindingRow,identity('acct_fixture','in_fixture')).version==0
        assert db.get(InboxRow,ident).state=='pending'


def test_deleted_subscription_active_status_alone_refuses(env,monkeypatch):
    data=event(status='active');data['type']='customer.subscription.deleted';ident=admit(env,monkeypatch,data)
    with pytest.raises(InboxRefused,match='deleted subscription not canceled'):env[0].apply(ident)
    with env[1]() as db:
        assert db.get(TenantBillingRow,'t1').status=='active'
        assert db.get(ResourceBindingRow,identity('acct_fixture','sub_fixture')).version==0
        assert db.get(InboxRow,ident).state=='pending'
