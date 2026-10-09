"""Positive retrieve evidence, original authenticated reviewer, no retry authority."""
import asyncio
from datetime import datetime,timezone
import pytest,httpx
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.auth.context import TenantContext
from app.modules.m00_approval_center.service import Service,ApprovalRequestRow
from app.modules.m24_billing import write_ahead as wa
from app.modules.m24_billing.checkout_dispatcher import CheckoutRepository,API_VERSION
from app.modules.m24_billing.service import PLANS
from app.modules.m24_billing.reconciliation import ReconciliationRepository,PositiveLookupAdapter,LookupEvidenceRow

@pytest.fixture(params=['sqlite','postgres'])
def env(tmp_path,request):
    if request.param=='postgres':
        import pgserver
        pg=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');uri=pg.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri=f'sqlite:///{tmp_path}/reconcile.db'
    engine=create_engine(uri);Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False);svc=Service(session_factory=sessions)
    a=svc.submit(module_id=24,action_type='create_subscription_checkout',user_id='t1',payload={'tenant_id':'t1','provider':'stripe','mode':'subscription','plan':PLANS['pro'].model_dump(),'success_url':'https://example.test/s','cancel_url':'https://example.test/c'})
    svc.decide(a['id'],ApprovalStatus.APPROVED,'original-owner')
    repo=CheckoutRepository(svc);op=repo.prepare(a['id'],'t1',provider_account='test-account',environment='test',api_version=API_VERSION,actor='worker')
    yield svc,sessions,repo,op,ReconciliationRepository(svc)
    engine.dispose()
    if request.param=='postgres':pg.cleanup()

def principal(actor='original-owner',tenant='t1',roles=('atlas-approver',)):return TenantContext(tenant,actor,frozenset(roles))

def mark_uncertain(env,monkeypatch):
    monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    with env[1].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='fixture-only',verified_at=datetime.now(timezone.utc)))
    fence=env[2].claim(env[3]['id'],'t1',protocol_epoch=2)
    env[2].outcome(env[3]['id'],'t1',fence,state='outcome_unknown')

def lookup(env,monkeypatch,change=None):
    mark_uncertain(env,monkeypatch);op=env[3];calls=[]
    body={'id':'cs_test_fixture','object':'checkout.session','livemode':False,'mode':'subscription','client_reference_id':'t1',
        'metadata':{'atlas_operation_id':op['id'],'atlas_operation_step':'checkout','atlas_approval_id':op['approval_id'],'tenant_id':'t1','plan_id':'pro'},
        'amount_total':2900,'currency':'usd','status':'open','payment_status':'unpaid'}
    if change:body.update(change)
    def handler(request):calls.append(request.method);return httpx.Response(200,json=body)
    adapter=PositiveLookupAdapter('sk_test_fixture','test-account',httpx.MockTransport(handler))
    result=asyncio.run(env[4].lookup_positive(op['id'],'t1','checkout','cs_test_fixture',adapter))
    return result,calls

def test_positive_retrieve_reviewed_by_original_principal_no_new_effect(env,monkeypatch):
    evidence,calls=lookup(env,monkeypatch)
    assert calls==['GET'] and env[2].get(env[3]['id'],'t1')['state']=='outcome_unknown'
    result=env[4].accept_positive(env[3]['id'],evidence['evidence_id'],principal())
    assert result['state']=='accepted-no-provider-effect' and calls==['GET']
    assert env[2].get(env[3]['id'],'t1')['state']=='succeeded'
    assert env[4].accept_positive(env[3]['id'],evidence['evidence_id'],principal())['state']=='already-accepted'

@pytest.mark.parametrize('bad',['other-reviewer','missing-role','foreign-tenant','missing-designation'])
def test_wrong_principal_or_missing_designation_refuse(env,monkeypatch,bad):
    evidence,calls=lookup(env,monkeypatch)
    if bad=='missing-designation':
        with env[1].begin() as db:db.get(ApprovalRequestRow,env[3]['approval_id']).approved_by=None
    who=principal(actor='other') if bad=='other-reviewer' else principal(roles=()) if bad=='missing-role' else principal(tenant='foreign') if bad=='foreign-tenant' else principal()
    with pytest.raises((PermissionError,KeyError)):env[4].accept_positive(env[3]['id'],evidence['evidence_id'],who)
    assert env[2].get(env[3]['id'],'t1')['state']=='outcome_unknown'


def test_changed_lookup_receipt_and_digest_refuse(env,monkeypatch):
    evidence,_=lookup(env,monkeypatch)
    with env[1].begin() as db:db.get(LookupEvidenceRow,evidence['evidence_id']).receipt={'id':'cs_test_forged'}
    with pytest.raises(wa.DispatchRefused):env[4].accept_positive(env[3]['id'],evidence['evidence_id'],principal())


def test_positive_mismatch_never_saved_as_evidence(env,monkeypatch):
    with pytest.raises(ValueError):lookup(env,monkeypatch,{'amount_total':9999})
    with env[1]() as db:assert db.scalar(select(LookupEvidenceRow)) is None


def test_unsent_cancel_terminal_no_new_authority(env):
    result=env[4].cancel_unsent_or_close_unknown(env[3]['id'],principal())
    assert result['state']=='cancelled_before_dispatch' and result['retry_allowed'] is False
    assert env[2].get(env[3]['id'],'t1')['state']=='cancelled_before_dispatch'


def test_uncertain_close_blocks_positive_acceptance_and_never_retries(env,monkeypatch):
    evidence,_=lookup(env,monkeypatch)
    result=env[4].cancel_unsent_or_close_unknown(env[3]['id'],principal())
    assert result['state']=='closed_unknown' and result['retry_allowed'] is False
    with pytest.raises(wa.DispatchRefused):env[4].accept_positive(env[3]['id'],evidence['evidence_id'],principal())
    with pytest.raises(wa.DispatchRefused):env[2].claim(env[3]['id'],'t1',protocol_epoch=2)


def test_http_acceptance_authenticated_original_subject_only(env,monkeypatch,oidc_auth_headers):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m24_billing.routes import router
    import app.modules.m00_approval_center.service as am
    evidence,_=lookup(env,monkeypatch);monkeypatch.setattr(am,'default_service',lambda:env[0])
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    app=FastAPI();app.include_router(router)
    route='/billing/operations/'+env[3]['id']+'/accept-positive';body={'evidence_id':evidence['evidence_id']}
    with TestClient(app) as client:
        assert client.post(route,json=body).status_code==401
        assert client.post(route,json=body,headers=oidc_auth_headers('foreign','original-owner',['atlas-approver'])).status_code==404
        assert client.post(route,json=body,headers=oidc_auth_headers('t1','other',['atlas-approver'])).status_code==403
        assert client.post(route,json=body,headers=oidc_auth_headers('t1','original-owner',[])).status_code==403
        assert client.post(route,json=body,headers=oidc_auth_headers('t1','original-owner',['atlas-approver'])).status_code==200


def test_http_unknown_close_terminal_authenticated_owner(env,monkeypatch,oidc_auth_headers):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m24_billing.routes import router
    import app.modules.m00_approval_center.service as am
    mark_uncertain(env,monkeypatch);monkeypatch.setattr(am,'default_service',lambda:env[0]);monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    app=FastAPI();app.include_router(router)
    with TestClient(app) as client:
        result=client.post('/billing/operations/'+env[3]['id']+'/cancel-or-close',headers=oidc_auth_headers('t1','original-owner',['atlas-approver']))
        assert result.status_code==200 and result.json()['state']=='closed_unknown' and result.json()['retry_allowed'] is False

@pytest.mark.parametrize('database',['sqlite','postgres'])
def test_lookup_evidence_migration_no_backfill_and_populated_downgrade_refusal(tmp_path,database):
    import subprocess,sys,os
    from pathlib import Path
    from sqlalchemy import text
    root=Path(__file__).resolve().parents[2]
    if database=='postgres':
        import pgserver
        pg=pgserver.get_server(tmp_path/'migration-pg',cleanup_mode='stop');uri=pg.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri=f'sqlite:///{tmp_path}/migration.db'
    runenv={**os.environ,'ATLAS_DATABASE_URL':uri,'PYTHONPATH':'backend'}
    def migrate(*args):return subprocess.run([sys.executable,'-m','alembic',*args],cwd=root,env=runenv,capture_output=True,text=True,timeout=30)
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    engine=create_engine(uri)
    with engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM m24_lookup_evidence')).scalar()==0
        assert db.execute(text('SELECT count(*) FROM m24_cancellation_snapshots')).scalar()==0
        assert db.execute(text('SELECT protocol_epoch FROM m24_dispatch_cutover')).scalar()==0
    result=migrate('downgrade','20261009_m24_invoice_steps');assert result.returncode==0,result.stderr
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    sessions=sessionmaker(bind=engine,expire_on_commit=False);svc=Service(session_factory=sessions)
    a=svc.submit(module_id=24,action_type='create_subscription_checkout',user_id='t1',payload={'tenant_id':'t1','provider':'stripe','mode':'subscription','plan':PLANS['pro'].model_dump(),'success_url':'https://example.test/s','cancel_url':'https://example.test/c'});svc.decide(a['id'],ApprovalStatus.APPROVED,'owner')
    op=CheckoutRepository(svc).prepare(a['id'],'t1',provider_account='test-account',environment='test',api_version=API_VERSION,actor='worker')
    with sessions.begin() as db:db.add(LookupEvidenceRow(id='fixture-evidence',operation_id=op['id'],tenant_id='t1',role='checkout',binding_hash='a'*64,provider_account='test-account',environment='test',api_version=API_VERSION,object_id='cs_test_fixture',receipt={'id':'cs_test_fixture'},evidence_digest='b'*64,observed_at=datetime.now(timezone.utc)))
    result=migrate('downgrade','20261009_m24_invoice_steps');assert result.returncode!=0 and 'destructive downgrade refused' in result.stderr
    engine.dispose()
    if database=='postgres':pg.cleanup()


def test_invoice_positive_draft_lookup_acceptance_releases_dependency_only(env,monkeypatch):
    from app.modules.m24_billing.invoice_dispatcher import InvoiceRepository
    from app.modules.m24_billing.repository import TenantBillingRow
    svc,sessions,_,_,rr=env
    with sessions.begin() as db:db.add(TenantBillingRow(tenant_id='t1',customer_id='cus_fixture'))
    a=svc.submit(module_id=24,action_type='issue_invoice',user_id='t1',payload={'tenant_id':'t1','provider':'stripe','effect':'create_draft_invoice','customer_id':'cus_fixture','description':'draft','amount_cents':100,'currency':'usd'});svc.decide(a['id'],ApprovalStatus.APPROVED,'original-owner')
    repo=InvoiceRepository(svc);op=repo.prepare(a['id'],'t1',provider_account='test-account',environment='test',api_version=API_VERSION,actor='worker')
    monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    with sessions.begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='fixture-only',verified_at=datetime.now(timezone.utc)))
    fence=repo.claim_step(op['id'],'t1','draft-invoice');repo.step_outcome(op['id'],'t1','draft-invoice',fence,state='outcome_unknown')
    body={'id':'in_fixture','object':'invoice','customer':'cus_fixture','currency':'usd','status':'draft','auto_advance':False,'total':0,'livemode':False,
        'metadata':{'atlas_operation_id':op['id'],'atlas_operation_step':'draft-invoice','atlas_approval_id':a['id']}}
    calls=[]
    def handler(request):calls.append(request.method);return httpx.Response(200,json=body)
    adapter=PositiveLookupAdapter('sk_test_fixture','test-account',httpx.MockTransport(handler))
    e=asyncio.run(rr.lookup_positive(op['id'],'t1','draft-invoice','in_fixture',adapter))
    rr.accept_positive(op['id'],e['evidence_id'],principal())
    assert repo.prepare_item(op['id'],'t1')['state']=='prepared'
    assert repo.get(op['id'],'t1')['state']=='prepared' and calls==['GET']


def test_reconciliation_accept_rollback_is_atomic(env,monkeypatch):
    from sqlalchemy.orm import Session
    from app.modules.m24_billing.write_ahead import OperationEventRow
    evidence,_=lookup(env,monkeypatch);original=Session.add
    def fail(self,row,*a,**kw):
        if isinstance(row,OperationEventRow) and row.event=='positive-evidence-accepted':raise RuntimeError('commit-path fixture failure')
        return original(self,row,*a,**kw)
    monkeypatch.setattr(Session,'add',fail)
    with pytest.raises(RuntimeError):env[4].accept_positive(env[3]['id'],evidence['evidence_id'],principal())
    assert env[2].get(env[3]['id'],'t1')['state']=='outcome_unknown'
    with env[1]() as db:assert db.get(LookupEvidenceRow,evidence['evidence_id']).accepted_at is None


def test_evidence_digest_alone_corrupt_refuses_even_valid_receipt(env,monkeypatch):
    evidence,_=lookup(env,monkeypatch)
    with env[1].begin() as db:db.get(LookupEvidenceRow,evidence['evidence_id']).evidence_digest='0'*64
    with pytest.raises(wa.DispatchRefused,match='evidence binding'):env[4].accept_positive(env[3]['id'],evidence['evidence_id'],principal())
    assert env[2].get(env[3]['id'],'t1')['state']=='outcome_unknown'

@pytest.mark.parametrize('point',['before-accept','after-accept'])
def test_reconciliation_sigkill_resume_acceptance_no_provider_dispatch(env,monkeypatch,tmp_path,point):
    import subprocess,sys,os,time,signal,json
    evidence,calls=lookup(env,monkeypatch);ready=tmp_path/'ready';answer=tmp_path/'answer'
    script=r'''
import os,time,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m00_approval_center.service import Service
from app.auth.context import TenantContext
from app.modules.m24_billing.reconciliation import ReconciliationRepository
repo=ReconciliationRepository(Service(session_factory=sessionmaker(bind=create_engine(os.environ['DATABASE']),expire_on_commit=False)))
def barrier(point):
 if os.environ['MODE']=='kill' and point==os.environ['POINT']:
  with open(os.environ['READY'],'w') as f:f.write(str(os.getpid()));f.flush();os.fsync(f.fileno())
  while True:time.sleep(.05)
barrier('before-accept')
result=repo.accept_positive(os.environ['OP'],os.environ['EVIDENCE'],TenantContext('t1','original-owner',frozenset({'atlas-approver'})))
barrier('after-accept')
with open(os.environ['ANSWER'],'w') as f:json.dump({'pid':os.getpid(),'result':result},f)
'''
    settings={**os.environ,'DATABASE':str(env[1].kw['bind'].url),'OP':env[3]['id'],'EVIDENCE':evidence['evidence_id'],'READY':str(ready),'ANSWER':str(answer),'POINT':point,'MODE':'kill'}
    child=subprocess.Popen([sys.executable,'-c',script],env=settings)
    try:
        until=time.monotonic()+12
        while not ready.exists() and time.monotonic()<until:
            assert child.poll() is None;time.sleep(.02)
        assert ready.exists() and int(ready.read_text())==child.pid
        os.kill(child.pid,signal.SIGKILL);assert child.wait(5)==-signal.SIGKILL
        assert env[2].get(env[3]['id'],'t1')['state']==('succeeded' if point=='after-accept' else 'outcome_unknown')
        resumed=subprocess.run([sys.executable,'-c',script],env={**settings,'MODE':'resume'},capture_output=True,text=True,timeout=12)
        assert resumed.returncode==0,resumed.stderr
        result=json.loads(answer.read_text());assert result['pid']!=child.pid
        assert result['result']['state']==('already-accepted' if point=='after-accept' else 'accepted-no-provider-effect')
        assert env[2].get(env[3]['id'],'t1')['state']=='succeeded' and calls==['GET']
    finally:
        if child.poll() is None:child.kill();child.wait(5)
