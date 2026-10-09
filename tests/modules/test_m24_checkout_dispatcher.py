"""Checkout dispatcher controls. Activation bypass is fixture-only, not readiness."""
import pytest
from app.modules.m24_billing.checkout_dispatcher import CheckoutDispatcher, CheckoutRepository


def test_dispatcher_exists_without_activation_capability():
    from app.modules.m24_billing.write_ahead import require_dispatch_ready, DispatchRefused
    with pytest.raises(DispatchRefused):require_dispatch_ready()

import asyncio
import copy
import json
from datetime import datetime,timedelta,timezone
from urllib.parse import parse_qs
import httpx
from sqlalchemy import create_engine,select,update
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service,ApprovalRequestRow,ApprovalEffectRow
from app.modules.m24_billing import write_ahead as wa
from app.modules.m24_billing.checkout_dispatcher import CheckoutAdapter,CheckoutSnapshotRow,API_VERSION
from app.modules.m24_billing.service import PLANS

@pytest.fixture(params=['sqlite','postgres'])
def env(tmp_path,request):
    if request.param=='postgres':
        import pgserver
        pg=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
        engine=create_engine(pg.get_uri().replace('postgresql://','postgresql+psycopg://'))
    else:engine=create_engine(f'sqlite:///{tmp_path}/billing.db',connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    svc=Service(session_factory=sessions)
    payload={'tenant_id':'t1','plan':PLANS['pro'].model_dump(),'success_url':'https://example.test/s','cancel_url':'https://example.test/c','provider':'stripe','mode':'subscription'}
    a=svc.submit(module_id=24,action_type='create_subscription_checkout',payload=payload,user_id='t1')
    svc.decide(a['id'],ApprovalStatus.APPROVED,'owner')
    repo=CheckoutRepository(svc)
    yield repo,svc,sessions,a
    engine.dispose()
    if request.param=='postgres':pg.cleanup()


def prepare(env):
    repo,svc,sessions,a=env
    return repo.prepare(a['id'],'t1',provider_account='test-account',environment='test',api_version=API_VERSION,actor='worker')


def mock_ready(env,monkeypatch):
    # Mock-only isolation/readiness override. The product has no activation route.
    monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    with env[2].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='fixture-only',verified_at=datetime.now(timezone.utc)))


class MockStripe:
    def __init__(self,*,status=200,malformed=False,prune=False):
        self.calls=[];self.effects={};self.keys={};self.status=status;self.malformed=malformed;self.prune=prune
    def __call__(self,request):
        form={k:v[0] for k,v in parse_qs(request.content.decode()).items()};key=request.headers['Idempotency-Key'];self.calls.append((key,form))
        assert request.headers['Stripe-Version']==API_VERSION
        assert request.url.path=='/v1/checkout/sessions'
        if self.prune:self.keys.clear()
        if key in self.keys:
            before,status,body=self.keys[key]
            if before!=form:return httpx.Response(400,json={'error':'parameter mismatch'})
            return httpx.Response(status,json=body)
        body={'id':'cs_test_'+str(len(self.effects)+1),'object':'checkout.session','livemode':False,'mode':'subscription',
            'client_reference_id':form['client_reference_id'],'metadata':{k[9:-1]:v for k,v in form.items() if k.startswith('metadata[')},
            'amount_total':2900,'currency':'usd','status':'open','payment_status':'unpaid'}
        if self.malformed:body['amount_total']=9900
        self.effects[body['id']]=copy.deepcopy(body)
        self.keys[key]=(form,self.status,body)
        return httpx.Response(self.status,json=body)


def dispatch(env,op,mock):
    adapter=CheckoutAdapter('sk_test_fixture','test-account',httpx.MockTransport(mock))
    return asyncio.run(CheckoutDispatcher(env[0],adapter).dispatch(op['id'],'t1'))


def test_exact_snapshot_and_step_key_before_provider(env):
    op=prepare(env);snapshot=env[0].snapshot(op['id'],'t1')
    assert op['provider_key']==op['id']+':checkout'
    assert snapshot['form']['metadata[atlas_operation_id]']==op['id']
    assert snapshot['form']['line_items[0][price_data][unit_amount]']=='2900'
    assert prepare(env)['id']==op['id']
    with env[2]() as db:assert len(db.scalars(select(ApprovalEffectRow)).all())==1


def test_snapshot_failure_rolls_back_permit_and_intent(env,monkeypatch):
    from sqlalchemy.orm import Session
    original=Session.add
    def fail(self,row,*args,**kwargs):
        if isinstance(row,CheckoutSnapshotRow):raise RuntimeError('snapshot failure')
        return original(self,row,*args,**kwargs)
    monkeypatch.setattr(Session,'add',fail)
    with pytest.raises(RuntimeError):prepare(env)
    with env[2]() as db:
        assert db.scalar(select(wa.OperationRow)) is None
        assert db.scalar(select(ApprovalEffectRow)) is None


def test_real_readiness_still_refuses_forged_row_zero_calls(env):
    op=prepare(env);mock=MockStripe()
    with env[2].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='forged',verified_at=datetime.now(timezone.utc)))
    with pytest.raises(wa.DispatchRefused):dispatch(env,op,mock)
    assert mock.calls==[]


def test_succeeded_replay_readback_no_new_calls_or_effects(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe()
    result=dispatch(env,op,mock)
    assert result['state']=='succeeded' and result['result']['id']=='cs_test_1'
    assert dispatch(env,op,mock)['result']==result['result']
    assert len(mock.calls)==len(mock.effects)==1
    with env[2]() as db:assert len(db.scalars(select(wa.AttemptRow)).all())==1


@pytest.mark.parametrize('kind',['http500','malformed','timeout'])
def test_post_entry_failures_stay_unknown_no_replay_even_pruned(env,monkeypatch,kind):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe(status=500 if kind=='http500' else 200,malformed=kind=='malformed',prune=True)
    def handler(request):
        response=mock(request)
        if kind=='timeout':raise httpx.ReadTimeout('fixture',request=request)
        return response
    result=dispatch(env,op,handler)
    assert result['state']=='outcome_unknown'
    assert dispatch(env,op,handler)['state']=='outcome_unknown'
    assert len(mock.calls)==len(mock.effects)==1


def test_two_concurrent_claims_one_attempt(env,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    op=prepare(env);mock_ready(env,monkeypatch);barrier=threading.Barrier(2)
    def run():
        barrier.wait(5)
        try:return env[0].claim(op['id'],'t1',protocol_epoch=2)
        except wa.DispatchRefused:return 'refused'
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:run(),range(2)))
    assert results.count('refused')==1
    with env[2]() as db:assert len(db.scalars(select(wa.AttemptRow)).all())==1


def test_attempt_committed_before_entry_is_never_reclaimed(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch)
    fence=env[0].claim(op['id'],'t1',protocol_epoch=2)
    with env[2].begin() as db:db.execute(update(wa.OperationRow).where(wa.OperationRow.id==op['id']).values(lease_until=datetime.now(timezone.utc)-timedelta(seconds=2)))
    assert env[0].expire_uncertain(op['id'],'t1')['state']=='outcome_unknown'
    with pytest.raises(wa.DispatchRefused):env[0].claim(op['id'],'t1',protocol_epoch=2)
    assert dispatch(env,op,MockStripe())['state']=='outcome_unknown'


@pytest.mark.parametrize('change',['approval','form','account','version','key','deadline'])
def test_changed_bindings_refuse_zero_provider(env,monkeypatch,change):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe()
    with env[2].begin() as db:
        if change=='approval':db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==env[3]['id']).values(status='denied'))
        elif change=='form':db.execute(update(CheckoutSnapshotRow).where(CheckoutSnapshotRow.operation_id==op['id']).values(form={'changed':'yes'}))
        elif change=='deadline':db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==env[3]['id']).values(expires_at=datetime.now(timezone.utc)-timedelta(seconds=5)))
        else:db.execute(update(wa.OperationRow).where(wa.OperationRow.id==op['id']).values(**{'account':{'provider_account':'foreign'},'version':{'api_version':'changed'},'key':{'provider_key':'changed'}}[change]))
    try:result=dispatch(env,op,mock)
    except wa.DispatchRefused:pass
    assert mock.calls==[]


def test_pre_entry_error_is_local_fact_only(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe()
    monkeypatch.setattr(env[0],'before_entry',lambda *args:(_ for _ in ()).throw(wa.DispatchRefused('lost authority')))
    assert dispatch(env,op,mock)['state']=='failed_before_dispatch'
    assert dispatch(env,op,mock)['state']=='failed_before_dispatch'
    assert mock.calls==[]


def test_receipt_storage_failure_returns_stable_unknown_no_redispatch(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe()
    original=env[0].outcome
    monkeypatch.setattr(env[0],'outcome',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('db lost')))
    result=dispatch(env,op,mock)
    assert result['id']==op['id'] and result['state']=='outcome_unknown'
    assert env[0].get(op['id'],'t1')['state']=='dispatching'
    assert dispatch(env,op,mock)['state']=='dispatching' and len(mock.calls)==1


def test_claim_commit_ack_loss_never_enters_adapter(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe();original=env[0].claim
    def lost(*a,**kw):original(*a,**kw);raise RuntimeError('commit ack lost')
    monkeypatch.setattr(env[0],'claim',lost)
    result=dispatch(env,op,mock)
    assert result['state']=='outcome_unknown' and result['failure']=='claim-commit-unconfirmed'
    assert env[0].get(op['id'],'t1')['state']=='dispatching' and mock.calls==[]


def test_late_result_recorded_no_stale_fence_or_replay(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);fence=env[0].claim(op['id'],'t1',protocol_epoch=2)
    with env[2].begin() as db:db.execute(update(wa.OperationRow).where(wa.OperationRow.id==op['id']).values(lease_until=datetime.now(timezone.utc)-timedelta(seconds=2)))
    env[0].expire_uncertain(op['id'],'t1')
    with pytest.raises(wa.DispatchRefused):env[0].outcome(op['id'],'t1','stale',state='succeeded',result={'id':'cs_test_late','object':'checkout.session','livemode':False,'mode':'subscription','amount_total':2900,'currency':'usd','status':'open','payment_status':'unpaid'})
    result=env[0].outcome(op['id'],'t1',fence,state='succeeded',result={'id':'cs_test_late','object':'checkout.session','livemode':False,'mode':'subscription','amount_total':2900,'currency':'usd','status':'open','payment_status':'unpaid'})
    assert result['state']=='succeeded_late'
    mock=MockStripe();assert dispatch(env,op,mock)['state']=='succeeded_late' and mock.calls==[]

@pytest.mark.parametrize('point',['prepared','attempt','adapter-entered','accepted','receipt'])
def test_pid_distinct_sigkill_and_restart_never_repeats_effect(env,tmp_path,point):
    import subprocess,sys,os,time,signal
    op=prepare(env)
    with env[2].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='fixture-only',verified_at=datetime.now(timezone.utc)))
    ready=tmp_path/'barrier';effects=tmp_path/'effects';answer=tmp_path/'answer'
    script=r'''
import asyncio,json,os,time
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m00_approval_center.service import Service
from app.modules.m24_billing import write_ahead as wa
from app.modules.m24_billing.checkout_dispatcher import CheckoutRepository,CheckoutDispatcher,CheckoutAdapter
# Explicit mock readiness only, never a product flag/API.
wa.require_dispatch_ready=lambda:None
engine=create_engine(os.environ['DATABASE'])
repo=CheckoutRepository(Service(session_factory=sessionmaker(bind=engine,expire_on_commit=False)))
def barrier(label):
    if os.environ['MODE']=='kill' and os.environ['POINT']==label:
        with open(os.environ['READY'],'w') as f:f.write(str(os.getpid()));f.flush();os.fsync(f.fileno())
        while True:time.sleep(.05)
original_claim=repo.claim
original_outcome=repo.outcome
def claim(*a,**kw):
    fence=original_claim(*a,**kw);barrier('attempt');return fence
repo.claim=claim
def outcome(*a,**kw):
    result=original_outcome(*a,**kw);barrier('receipt');return result
repo.outcome=outcome
class Adapter(CheckoutAdapter):
    async def invoke(self,request):
        barrier('adapter-entered')
        with open(os.environ['EFFECTS'],'a') as f:f.write(request.headers['Idempotency-Key']+'\n');f.flush();os.fsync(f.fileno())
        barrier('accepted')
        op=repo.get(os.environ['OP'],'t1')
        return {'id':'cs_test_kill','object':'checkout.session','livemode':False,'mode':'subscription','client_reference_id':'t1',
            'metadata':{'atlas_operation_id':op['id'],'atlas_operation_step':'checkout','atlas_approval_id':op['approval_id'],'tenant_id':'t1','plan_id':'pro'},
            'amount_total':2900,'currency':'usd','status':'open','payment_status':'unpaid'}
barrier('prepared')
result=asyncio.run(CheckoutDispatcher(repo,Adapter('sk_test_fixture','test-account')).dispatch(os.environ['OP'],'t1'))
with open(os.environ['ANSWER'],'w') as f:json.dump({'pid':os.getpid(),'result':result},f,default=str);f.flush();os.fsync(f.fileno())
'''
    settings={**os.environ,'DATABASE':str(env[2].kw['bind'].url),'OP':op['id'],'READY':str(ready),'EFFECTS':str(effects),'ANSWER':str(answer),'POINT':point,'MODE':'kill'}
    process=subprocess.Popen([sys.executable,'-c',script],env=settings)
    try:
        until=time.monotonic()+12
        while not ready.exists() and time.monotonic()<until:
            assert process.poll() is None;time.sleep(.02)
        assert ready.exists() and int(ready.read_text())==process.pid
        os.kill(process.pid,signal.SIGKILL);assert process.wait(5)==-signal.SIGKILL
        before=env[0].get(op['id'],'t1')
        assert before['state']==('prepared' if point=='prepared' else 'succeeded' if point=='receipt' else 'dispatching')
        restart=subprocess.run([sys.executable,'-c',script],env={**settings,'MODE':'restart'},capture_output=True,text=True,timeout=12)
        assert restart.returncode==0,restart.stderr
        recovered=json.loads(answer.read_text());assert recovered['pid']!=process.pid
        expected='succeeded' if point in {'prepared','receipt'} else 'dispatching'
        assert recovered['result']['state']==expected
        count=len(effects.read_text().splitlines()) if effects.exists() else 0
        assert count==(1 if point in {'prepared','accepted','receipt'} else 0)
        with env[2]() as db:assert len(db.scalars(select(wa.AttemptRow)).all())==1
    finally:
        if process.poll() is None:process.kill();process.wait(5)


def test_mock_contract_first500_replay_parameter_mismatch_and_pruning():
    from urllib.parse import urlencode
    mock=MockStripe(status=500)
    form={'client_reference_id':'t1','metadata[atlas_operation_id]':'op','metadata[atlas_operation_step]':'checkout','metadata[atlas_approval_id]':'a','metadata[tenant_id]':'t1','metadata[plan_id]':'pro'}
    def req(form):return httpx.Request('POST','https://api.stripe.com/v1/checkout/sessions',headers={'Stripe-Version':API_VERSION,'Idempotency-Key':'key'},content=urlencode(form))
    assert mock(req(form)).status_code==500
    assert mock(req(form)).status_code==500 and len(mock.effects)==1
    assert mock(req({**form,'changed':'yes'})).status_code==400
    mock.prune=True;assert mock(req(form)).status_code==500 and len(mock.effects)==2


def test_foreign_tenant_and_live_adapter_refused(env):
    op=prepare(env)
    with pytest.raises(KeyError):env[0].snapshot(op['id'],'foreign')
    with pytest.raises(ValueError):CheckoutAdapter('sk_live_fixture','test-account')


def test_existing_plain_intent_not_silently_upgraded(env):
    repo,svc,sessions,a=env
    wa.OperationRepository(svc).prepare(a['id'],'t1',provider_account='test-account',environment='test',api_version=API_VERSION,actor='worker')
    with pytest.raises(wa.DispatchRefused,match='snapshot'):prepare(env)


def test_service_uses_durable_dispatcher_not_legacy_provider(env,monkeypatch):
    from app.modules.m24_billing.service import Service as BillingService
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe()
    class ReadRepo:
        def approval(self,aid):return env[1].get(aid)
        def record_execution(self,*a):raise AssertionError('legacy receipt not authoritative')
    class LegacyProvider:
        async def create_checkout(self,*a):raise AssertionError('legacy bypass')
    adapter=CheckoutAdapter('sk_test_fixture','test-account',httpx.MockTransport(mock))
    svc=BillingService(None,ReadRepo(),LegacyProvider(),CheckoutDispatcher(env[0],adapter))
    assert asyncio.run(svc.execute_checkout(env[3]['id'],'t1'))['state']=='succeeded'
    assert len(mock.calls)==1


def test_12h_first_attempt_bound_never_refreshes(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);past=datetime.now(timezone.utc)-timedelta(hours=13)
    with env[2].begin() as db:db.execute(update(wa.OperationRow).where(wa.OperationRow.id==op['id']).values(first_attempt_at=past))
    with pytest.raises(wa.DispatchRefused,match='bound'):env[0].claim(op['id'],'t1',protocol_epoch=2)
    assert wa._aware(env[0].get(op['id'],'t1')['first_attempt_at']).astimezone(timezone.utc)==past


def test_pre_entry_revocation_after_claim_zero_network(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe();original=env[0].claim
    def revoke(*a,**kw):
        fence=original(*a,**kw)
        with env[2].begin() as db:db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==env[3]['id']).values(status='denied'))
        return fence
    monkeypatch.setattr(env[0],'claim',revoke)
    assert dispatch(env,op,mock)['state']=='failed_before_dispatch' and mock.calls==[]


def test_cross_adapter_account_refused_before_attempt(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe()
    adapter=CheckoutAdapter('sk_test_fixture','foreign-account',httpx.MockTransport(mock))
    with pytest.raises(wa.DispatchRefused):asyncio.run(CheckoutDispatcher(env[0],adapter).dispatch(op['id'],'t1'))
    assert mock.calls==[]
    with env[2]() as db:assert db.scalar(select(wa.AttemptRow)) is None


@pytest.mark.parametrize('database',['sqlite','postgres'])
def test_populated_checkout_migration_no_backfill_and_downgrade_refusal(tmp_path,database):
    import subprocess,sys,os
    from pathlib import Path
    from sqlalchemy import text,inspect
    root=Path(__file__).resolve().parents[2]
    if database=='postgres':
        import pgserver
        server=pgserver.get_server(tmp_path/'migration-pg',cleanup_mode='stop')
        uri=server.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri=f'sqlite:///{tmp_path}/migration.db'
    runenv={**os.environ,'ATLAS_DATABASE_URL':uri,'PYTHONPATH':'backend'}
    def migrate(*args):return subprocess.run([sys.executable,'-m','alembic',*args],cwd=root,env=runenv,capture_output=True,text=True,timeout=30)
    result=migrate('upgrade','20261009_m24_write_ahead');assert result.returncode==0,result.stderr
    engine=create_engine(uri);sessions=sessionmaker(bind=engine,expire_on_commit=False);svc=Service(session_factory=sessions)
    payload={'tenant_id':'t1','plan':PLANS['pro'].model_dump(),'success_url':'https://example.test/s','cancel_url':'https://example.test/c','provider':'stripe','mode':'subscription'}
    a=svc.submit(module_id=24,action_type='create_subscription_checkout',payload=payload,user_id='t1');svc.decide(a['id'],ApprovalStatus.APPROVED,'owner')
    op=wa.OperationRepository(svc).prepare(a['id'],'t1',provider_account='test-account',environment='test',api_version=API_VERSION,actor='worker')
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    with engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM m24_checkout_snapshots')).scalar()==0
        assert db.execute(text('SELECT protocol_epoch FROM m24_dispatch_cutover')).scalar()==0
    with pytest.raises(wa.DispatchRefused):CheckoutRepository(svc).snapshot(op['id'],'t1')
    # Empty snapshot downgrade allowed; upgrade again without blessing old intents.
    result=migrate('downgrade','20261009_m24_write_ahead');assert result.returncode==0,result.stderr
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    b=svc.submit(module_id=24,action_type='create_subscription_checkout',payload=payload,user_id='t1');svc.decide(b['id'],ApprovalStatus.APPROVED,'owner')
    CheckoutRepository(svc).prepare(b['id'],'t1',provider_account='test-account',environment='test',api_version=API_VERSION,actor='worker')
    result=migrate('downgrade','20261009_m24_write_ahead');assert result.returncode!=0 and 'destructive downgrade refused' in result.stderr
    engine.dispose()
    if database=='postgres':server.cleanup()


def test_claim_transaction_failure_rolls_back_attempt_zero_calls(env,monkeypatch):
    from sqlalchemy.orm import Session
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe();original=Session.add
    def fail(self,row,*a,**kw):
        if isinstance(row,wa.AttemptRow):raise RuntimeError('internal sensitive db failure')
        return original(self,row,*a,**kw)
    monkeypatch.setattr(Session,'add',fail)
    result=dispatch(env,op,mock)
    assert result['failure']=='claim-commit-unconfirmed' and 'sensitive' not in str(result)
    assert env[0].get(op['id'],'t1')['state']=='prepared'
    with env[2]() as db:assert db.scalar(select(wa.AttemptRow)) is None
    assert mock.calls==[]


def test_commit_readback_failure_never_enters_adapter(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe();original=env[0].get
    def unreadable(*a,**kw):
        result=original(*a,**kw)
        if result['state']=='dispatching':raise RuntimeError('database inaccessible')
        return result
    monkeypatch.setattr(env[0],'get',unreadable)
    result=dispatch(env,op,mock)
    assert result['state']=='outcome_unknown' and result['failure']=='claim-readback-unavailable'
    assert mock.calls==[]


def test_unknown_http_status_tenant_isolation_no_private_form(env,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m24_billing.routes import router,require_tenant
    import app.modules.m00_approval_center.service as approval_module
    from types import SimpleNamespace
    op=prepare(env)
    monkeypatch.setattr(approval_module,'default_service',lambda:env[1])
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[require_tenant]=lambda:SimpleNamespace(tenant_id='foreign')
    with TestClient(app) as client:assert client.get('/billing/checkout-operations/'+op['id']).status_code==404
    app.dependency_overrides[require_tenant]=lambda:SimpleNamespace(tenant_id='t1')
    with TestClient(app) as client:
        response=client.get('/billing/checkout-operations/'+op['id'])
        assert response.status_code==200 and response.json()['state']=='prepared'
        assert 'request' not in response.json() and 'provider_account' not in response.json()


def test_concurrent_dispatchers_one_provider_call_and_effect(env,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe();barrier=threading.Barrier(2)
    def run():barrier.wait(5);return dispatch(env,op,mock)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:run(),range(2)))
    assert len(mock.calls)==len(mock.effects)==1
    assert {r['state'] for r in results}<={'dispatching','succeeded'}


def test_invalid_bounded_result_cannot_silently_mark_success(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);fence=env[0].claim(op['id'],'t1',protocol_epoch=2)
    with pytest.raises(ValueError):env[0].outcome(op['id'],'t1',fence,state='succeeded',result={'id':'cs_test_fake','secret':'unexpected'})
    assert env[0].get(op['id'],'t1')['state']=='dispatching'

@pytest.mark.parametrize('difference',['fence','state'])
def test_claim_readback_difference_never_enters_adapter(env,monkeypatch,difference):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe();original=env[0].get
    def changed(*a,**kw):
        result=original(*a,**kw)
        if result['state']=='dispatching':result[difference]='wrong-fence' if difference=='fence' else 'prepared'
        return result
    monkeypatch.setattr(env[0],'get',changed)
    with pytest.raises(wa.DispatchRefused,match='readback'):dispatch(env,op,mock)
    assert mock.calls==[]


def test_lease_expires_between_claim_and_entry_zero_network(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);mock=MockStripe();original=env[0].claim
    def elapsed(*a,**kw):
        fence=original(*a,**kw)
        with env[2].begin() as db:db.execute(update(wa.OperationRow).where(wa.OperationRow.id==op['id']).values(lease_until=datetime.now(timezone.utc)-timedelta(seconds=2)))
        return fence
    monkeypatch.setattr(env[0],'claim',elapsed)
    assert dispatch(env,op,mock)['state']=='failed_before_dispatch' and mock.calls==[]


@pytest.mark.parametrize('stage',['claim','entry'])
def test_commitment_deadline_elapsed_refused_at_both_boundaries(env,monkeypatch,stage):
    from app.modules.m24_billing.precommit import preview_commitment
    from datetime import timedelta
    repo,svc,sessions,a=env;future=datetime.now(timezone.utc)+timedelta(hours=1)
    preview=preview_commitment(plan=PLANS['pro'].model_dump(),cancellation_policy='Cancel before renewal',cancellation_deadline=future)
    with sessions.begin() as db:
        row=db.get(ApprovalRequestRow,a['id']);row.payload={**row.payload,'commitment_preview':preview,'commitment_preview_sha256':preview['preview_sha256'],'expected_charge_cents':2900}
    op=prepare(env);mock_ready(env,monkeypatch)
    if stage=='entry':fence=repo.claim(op['id'],'t1',protocol_epoch=2)
    # Advance only repository DB-clock fixture, beyond commitment but within lease.
    original=repo._now
    monkeypatch.setattr(repo,'_now',lambda db:future+timedelta(seconds=1))
    if stage=='entry':
        with sessions.begin() as db:db.execute(update(wa.OperationRow).where(wa.OperationRow.id==op['id']).values(lease_until=future+timedelta(seconds=30),dispatch_not_after=future+timedelta(seconds=30)))
        with pytest.raises(wa.DispatchRefused,match='commitment'):repo.before_entry(op['id'],'t1',fence)
    else:
        with pytest.raises(wa.DispatchRefused,match='commitment'):repo.claim(op['id'],'t1',protocol_epoch=2)
        with sessions() as db:assert db.scalar(select(wa.AttemptRow)) is None


def test_uncertain_cannot_become_failed_before_dispatch(env,monkeypatch):
    op=prepare(env);mock_ready(env,monkeypatch);fence=env[0].claim(op['id'],'t1',protocol_epoch=2)
    env[0].outcome(op['id'],'t1',fence,state='outcome_unknown',failure='uncertain')
    with pytest.raises(wa.DispatchRefused,match='uncertain'):env[0].outcome(op['id'],'t1',fence,state='failed_before_dispatch')
    assert env[0].get(op['id'],'t1')['state']=='outcome_unknown'
