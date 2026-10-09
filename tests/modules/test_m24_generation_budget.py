"""Inactive optional model generation; no real provider/model/charge."""
import asyncio,copy
from datetime import datetime,timezone
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service,ApprovalEffectRow
from app.modules.m24_billing import write_ahead as wa
from app.modules.m24_billing.generation import BudgetRow,GenerationRow,BudgetAttemptRow,GenerationRepository,GenerationDispatcher,ACTION

PRICE={'id':'fixture-usd-v1','currency':'USD','input_micro_usd_per_token':2,'output_micro_usd_per_token':3}

@pytest.fixture(params=['sqlite','postgres'])
def env(tmp_path,request):
    if request.param=='postgres':
        import pgserver
        pg=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');uri=pg.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:uri=f'sqlite:///{tmp_path}/generation.db'
    engine=create_engine(uri);Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False);svc=Service(session_factory=sessions)
    with sessions.begin() as db:db.add(BudgetRow(id='budget1',tenant_id='t1',account='fixture-account',price_schedule=copy.deepcopy(PRICE),available_input=100,available_output=100,available_micro_usd=500,available_attempts=5))
    yield svc,sessions,GenerationRepository(svc)
    engine.dispose()
    if request.param=='postgres':pg.cleanup()

def payload(**changes):
    p={'tenant_id':'t1','budget_id':'budget1','account':'fixture-account','model':'fixture-model','model_version':'v1','inputs':'Private billing description input',
        'options':{'temperature':0},'price_schedule':copy.deepcopy(PRICE),'max_input_tokens':10,'max_output_tokens':20,'max_micro_usd':80,'privacy':'private-no-delivery','regenerates':None}
    p.update(changes);return p

def approved(env,**changes):
    a=env[0].submit(module_id=24,action_type=ACTION,user_id='t1',payload=payload(**changes));env[0].decide(a['id'],ApprovalStatus.APPROVED,'owner');return a

def prepare(env,**changes):return env[2].prepare(approved(env,**changes)['id'],'t1')

def ready(env,monkeypatch):
    monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    with env[1].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='fixture-only',verified_at=datetime.now(timezone.utc)))

def response(**changes):
    r={'text':'Reviewed draft description','input_tokens':5,'output_tokens':10,'micro_usd':40,'account':'fixture-account','model':'fixture-model','model_version':'v1','price_schedule_id':PRICE['id'],'usage_verified':True}
    r.update(changes);return r

class Mock:
    account='fixture-account';model='fixture-model';model_version='v1'
    def __init__(self,raw=None,fail=False):self.calls=0;self.raw=raw or response();self.fail=fail
    async def generate(self,request):
        self.calls+=1
        if self.fail:raise TimeoutError('model accepted unknown charge')
        return self.raw

def dispatch(env,op,mock):return asyncio.run(GenerationDispatcher(env[2],mock).dispatch(op['id'],'t1'))


def test_reserve_atomic_replay_then_settle_output_usage_and_no_model_repeat(env,monkeypatch):
    a=approved(env);op=env[2].prepare(a['id'],'t1');assert env[2].prepare(a['id'],'t1')['id']==op['id']
    with env[1]() as db:
        b=db.get(BudgetRow,'budget1');assert (b.available_input,b.available_output,b.available_micro_usd,b.available_attempts)==(90,80,420,4)
        assert len(db.scalars(select(BudgetAttemptRow)).all())==1 and len(db.scalars(select(ApprovalEffectRow)).all())==1
    ready(env,monkeypatch);mock=Mock();result=dispatch(env,op,mock);assert result['state']=='succeeded'
    assert dispatch(env,op,mock)['state']=='succeeded' and mock.calls==1
    with env[1]() as db:
        b=db.get(BudgetRow,'budget1');assert (b.available_input,b.available_output,b.available_micro_usd,b.available_attempts)==(95,90,460,4)
        assert db.get(BudgetAttemptRow,op['id']).state=='settled'
    output=result['output'];assert env[2].description_for_proposal(op['id'],'t1',1,output['digest'])=='Reviewed draft description'


def test_after_balance_update_failure_rolls_back_permit_reserve_generation(env):
    a=approved(env)
    def fail(point):
        if point=='after-balance-update':raise RuntimeError('storage failure')
    with pytest.raises(RuntimeError):env[2].prepare(a['id'],'t1',hook=fail)
    with env[1]() as db:
        assert db.get(BudgetRow,'budget1').available_micro_usd==500
        assert db.scalar(select(GenerationRow)) is None and db.scalar(select(ApprovalEffectRow)) is None


def test_competing_approvals_cannot_overspend_any_balance(env):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    a=approved(env);b=approved(env)
    with env[1].begin() as db:db.get(BudgetRow,'budget1').available_micro_usd=80
    barrier=threading.Barrier(2)
    def run(approval):
        barrier.wait(5)
        try:return env[2].prepare(approval['id'],'t1')['id']
        except wa.DispatchRefused:return 'refused'
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(run,(a,b)))
    assert results.count('refused')==1
    with env[1]() as db:
        assert db.get(BudgetRow,'budget1').available_micro_usd==0
        assert len(db.scalars(select(GenerationRow)).all())==1 and len(db.scalars(select(ApprovalEffectRow)).all())==1


@pytest.mark.parametrize('field,value',[('account','foreign'),('privacy','public'),('max_micro_usd',79),('max_input_tokens',True),('price_schedule',{**PRICE,'currency':'EUR'})])
def test_changed_authority_or_unbounded_charge_refuses_no_debit(env,field,value):
    with pytest.raises(wa.DispatchRefused):prepare(env,**{field:value})
    with env[1]() as db:assert db.get(BudgetRow,'budget1').available_micro_usd==500 and db.scalar(select(ApprovalEffectRow)) is None


def test_hard_readiness_zero_model_calls(env):
    op=prepare(env);mock=Mock()
    with pytest.raises(wa.DispatchRefused):dispatch(env,op,mock)
    assert mock.calls==0


def test_uncertain_charge_never_refunded_new_regeneration_reserves_separately(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=Mock(fail=True)
    assert dispatch(env,op,mock)['state']=='outcome_unknown'
    assert dispatch(env,op,mock)['state']=='outcome_unknown' and mock.calls==1
    with env[1]() as db:
        assert db.get(BudgetAttemptRow,op['id']).state=='charged-pending'
        assert db.get(BudgetRow,'budget1').available_micro_usd==420
    new=prepare(env,regenerates=op['id']);assert new['id']!=op['id']
    with env[1]() as db:
        assert db.get(BudgetRow,'budget1').available_micro_usd==340
        assert db.get(BudgetAttemptRow,op['id']).state=='charged-pending'
        assert len(db.scalars(select(BudgetAttemptRow)).all())==2


@pytest.mark.parametrize('field,value',[('usage_verified',False),('account','foreign'),('model_version','v2'),('micro_usd',39),('input_tokens',11),('text','')])
def test_unverified_or_changed_usage_holds_reserve_no_output(env,monkeypatch,field,value):
    op=prepare(env);ready(env,monkeypatch);mock=Mock(response(**{field:value}));assert dispatch(env,op,mock)['state']=='outcome_unknown'
    with env[1]() as db:
        assert db.get(GenerationRow,op['id']).output is None
        assert db.get(BudgetAttemptRow,op['id']).state=='charged-pending' and db.get(BudgetRow,'budget1').available_micro_usd==420
    with pytest.raises(wa.DispatchRefused):env[2].description_for_proposal(op['id'],'t1',1,'missing')


def test_output_commit_failure_rolls_back_settlement_and_output(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);fence=env[2].claim(op['id'],'t1')
    def fail(point):
        if point=='before-output-commit':raise RuntimeError('output commit refused')
    with pytest.raises(RuntimeError):env[2].settle(op['id'],'t1',fence,response(),hook=fail)
    with env[1]() as db:
        assert db.get(GenerationRow,op['id']).output is None
        assert db.get(BudgetRow,'budget1').available_micro_usd==420 and db.get(BudgetAttemptRow,op['id']).state=='charged-pending'


def test_foreign_output_version_digest_or_late_never_reaches_proposal(env,monkeypatch):
    from datetime import timedelta
    op=prepare(env);ready(env,monkeypatch);fence=env[2].claim(op['id'],'t1')
    with env[1].begin() as db:db.get(GenerationRow,op['id']).lease_until=datetime.now(timezone.utc)-timedelta(seconds=2)
    result=env[2].settle(op['id'],'t1',fence,response());assert result['state']=='succeeded_late'
    with pytest.raises(wa.DispatchRefused):env[2].description_for_proposal(op['id'],'t1',1,result['output']['digest'])
    with pytest.raises(KeyError):env[2].description_for_proposal(op['id'],'foreign',1,result['output']['digest'])


@pytest.mark.parametrize('point',['reservation','attempt','returned','output'])
def test_real_sigkill_generation_reserve_charge_output_resume(env,tmp_path,point):
    import os,sys,subprocess,signal,time,json
    a=approved(env);readyfile=tmp_path/'ready';effects=tmp_path/'effects';answer=tmp_path/'answer'
    with env[1].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=2,state='verified-active',verification_digest='fixture-only',verified_at=datetime.now(timezone.utc)))
    script=r'''
import asyncio,os,time,json
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.modules.m00_approval_center.service import Service
from app.modules.m24_billing import write_ahead as wa
from app.modules.m24_billing.generation import GenerationRepository,GenerationDispatcher
wa.require_dispatch_ready=lambda:None
repo=GenerationRepository(Service(session_factory=sessionmaker(bind=create_engine(os.environ['DATABASE']),expire_on_commit=False)))
def barrier(point):
 if os.environ['MODE']=='kill' and point==os.environ['POINT']:
  with open(os.environ['READY'],'w') as f:f.write(str(os.getpid()));f.flush();os.fsync(f.fileno())
  while True:time.sleep(.05)
op=repo.prepare(os.environ['APPROVAL'],'t1',hook=lambda p:barrier('reservation') if p=='after-reservation-commit' else None)
original=repo.claim
def claim(*a):
 fence=original(*a);barrier('attempt');return fence
repo.claim=claim
class Mock:
 account='fixture-account';model='fixture-model';model_version='v1'
 async def generate(self,request):
  with open(os.environ['EFFECTS'],'a') as f:f.write('generation\n');f.flush();os.fsync(f.fileno())
  barrier('returned')
  return {'text':'Reviewed draft description','input_tokens':5,'output_tokens':10,'micro_usd':40,'account':self.account,'model':self.model,'model_version':self.model_version,'price_schedule_id':'fixture-usd-v1','usage_verified':True}
result=asyncio.run(GenerationDispatcher(repo,Mock()).dispatch(op['id'],'t1'))
barrier('output')
if result['state']=='succeeded':
 output=result['output'];text=repo.description_for_proposal(op['id'],'t1',output['version'],output['digest'])
else:text=None
with open(os.environ['ANSWER'],'w') as f:json.dump({'pid':os.getpid(),'result':result,'text':text},f,default=str)
'''
    settings={**os.environ,'DATABASE':str(env[1].kw['bind'].url),'APPROVAL':a['id'],'READY':str(readyfile),'EFFECTS':str(effects),'ANSWER':str(answer),'MODE':'kill','POINT':point}
    child=subprocess.Popen([sys.executable,'-c',script],env=settings)
    try:
        until=time.monotonic()+12
        while not readyfile.exists() and time.monotonic()<until:
            assert child.poll() is None;time.sleep(.02)
        assert readyfile.exists() and int(readyfile.read_text())==child.pid
        os.kill(child.pid,signal.SIGKILL);assert child.wait(5)==-signal.SIGKILL
        with env[1]() as db:
            row=db.scalar(select(GenerationRow));attempt=db.get(BudgetAttemptRow,row.id);budget=db.get(BudgetRow,'budget1')
            assert row.state==('prepared' if point=='reservation' else 'succeeded' if point=='output' else 'dispatching')
            assert attempt.state==('reserved' if point=='reservation' else 'settled' if point=='output' else 'charged-pending')
            assert budget.available_micro_usd==(460 if point=='output' else 420)
            assert (row.output is not None)==(point=='output')
        previous=effects.read_text().splitlines() if effects.exists() else []
        restart=subprocess.run([sys.executable,'-c',script],env={**settings,'MODE':'resume'},capture_output=True,text=True,timeout=12)
        assert restart.returncode==0,restart.stderr
        result=json.loads(answer.read_text());assert result['pid']!=child.pid
        actual=effects.read_text().splitlines() if effects.exists() else []
        if point in {'reservation','output'}:
            assert result['result']['state']=='succeeded' and result['text']=='Reviewed draft description' and len(actual)==1
        else:
            assert result['result']['state']=='dispatching' and result['text'] is None and actual==previous
        with env[1]() as db:assert len(db.scalars(select(BudgetAttemptRow)).all())==1
    finally:
        if child.poll() is None:child.kill();child.wait(5)


@pytest.mark.parametrize('field',['available_input','available_output','available_micro_usd','available_attempts'])
def test_each_insufficient_balance_refuses_no_permit(env,field):
    with env[1].begin() as db:setattr(db.get(BudgetRow,'budget1'),field,0)
    with pytest.raises(wa.DispatchRefused,match='exhausted'):prepare(env)
    with env[1]() as db:assert db.scalar(select(GenerationRow)) is None and db.scalar(select(ApprovalEffectRow)) is None


def test_zero_price_still_reserves_token_and_attempt_allowance(env,monkeypatch):
    price={**PRICE,'input_micro_usd_per_token':0,'output_micro_usd_per_token':0}
    with env[1].begin() as db:db.get(BudgetRow,'budget1').price_schedule=price
    op=prepare(env,price_schedule=price,max_micro_usd=0);ready(env,monkeypatch)
    result=dispatch(env,op,Mock(response(micro_usd=0)));assert result['state']=='succeeded'
    with env[1]() as db:
        b=db.get(BudgetRow,'budget1');assert b.available_micro_usd==500 and b.available_input==95 and b.available_attempts==4


def test_adapter_binding_and_readback_mismatch_zero_model(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);mock=Mock();mock.account='foreign'
    with pytest.raises(wa.DispatchRefused,match='adapter binding'):dispatch(env,op,mock)
    assert mock.calls==0
    mock.account='fixture-account';original=env[2].get;reads=[]
    def get(*a):
        result=original(*a);reads.append(1)
        if len(reads)==2:result['fence']='foreign'
        return result
    monkeypatch.setattr(env[2],'get',get)
    assert dispatch(env,op,mock)['state']=='outcome_unknown' and mock.calls==0


def test_revoked_authority_and_elapsed_lease_zero_entry(env,monkeypatch):
    from datetime import timedelta
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    op=prepare(env);ready(env,monkeypatch);fence=env[2].claim(op['id'],'t1')
    with env[1].begin() as db:db.get(GenerationRow,op['id']).lease_until=datetime.now(timezone.utc)-timedelta(seconds=2)
    with pytest.raises(wa.DispatchRefused,match='lease lost'):env[2].before_entry(op['id'],'t1',fence)
    with env[1].begin() as db:db.get(ApprovalRequestRow,op['approval_id']).status='rejected'
    with pytest.raises(wa.DispatchRefused,match='revoked'):env[2].before_entry(op['id'],'t1',fence)


def test_settled_output_never_overwritten_and_bad_proposal_version_refuses(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);result=dispatch(env,op,Mock());output=result['output']
    with pytest.raises(wa.DispatchRefused):env[2].settle(op['id'],'t1',result['fence'],response(text='changed'))
    for version,dig in ((2,output['digest']),(1,'wrong')):
        with pytest.raises(wa.DispatchRefused):env[2].description_for_proposal(op['id'],'t1',version,dig)
    assert env[2].get(op['id'],'t1')['output']==output


def test_generation_only_creates_pending_exact_invoice_proposal_not_money(env,monkeypatch):
    from app.modules.m24_billing.service import Service as BillingService
    from app.modules.m24_billing.schemas import InvoiceIn
    op=prepare(env);ready(env,monkeypatch);result=dispatch(env,op,Mock());output=result['output'];created=[]
    class Approvals:
        def put(self,request):created.append(request);return request
    billing=BillingService(Approvals(),None,None)
    data=InvoiceIn(customer_id='cus_fixture',description=output['text'],amount_cents=100)
    proposal=billing.propose_invoice_from_generation('t1',data,env[2],op['id'],1,output['digest'])
    assert proposal.status=='pending' and proposal.payload['generation']=={'id':op['id'],'version':1,'digest':output['digest']}
    assert proposal.approval_id!=op['approval_id'] and proposal.payload['amount_cents']==100 and len(created)==1
    with pytest.raises(ValueError,match='differs'):billing.propose_invoice_from_generation('t1',data.model_copy(update={'description':'transient'}),env[2],op['id'],1,output['digest'])
    assert len(created)==1


@pytest.mark.parametrize('database',['sqlite','postgres'])
def test_populated_generation_migration_no_backfill_downgrade_refuses(tmp_path,database):
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
    result=migrate('upgrade','20261009_m24_verified_inbox');assert result.returncode==0,result.stderr
    engine=create_engine(uri)
    with engine.begin() as db:db.execute(text("INSERT INTO m24_billing_events (id,type,payload,processed_at) VALUES ('evt_legacy','invoice.paid','{}',CURRENT_TIMESTAMP)"))
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    with engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM m24_generations')).scalar()==0
        assert db.execute(text('SELECT count(*) FROM m24_generation_budgets')).scalar()==0
        assert db.execute(text('SELECT count(*) FROM m24_billing_events')).scalar()==1
    result=migrate('downgrade','20261009_m24_verified_inbox');assert result.returncode==0,result.stderr
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    sessions=sessionmaker(bind=engine,expire_on_commit=False)
    with sessions.begin() as db:db.add(BudgetRow(id='budget1',tenant_id='t1',account='fixture-account',price_schedule=PRICE,available_input=10,available_output=20,available_micro_usd=80,available_attempts=1))
    svc=Service(session_factory=sessions);a=svc.submit(module_id=24,action_type=ACTION,user_id='t1',payload=payload());svc.decide(a['id'],ApprovalStatus.APPROVED,'owner');GenerationRepository(svc).prepare(a['id'],'t1')
    result=migrate('downgrade','20261009_m24_verified_inbox');assert result.returncode!=0 and 'destructive downgrade refused' in result.stderr
    engine.dispose()
    if database=='postgres':pg.cleanup()


def test_sql_cutover_barrier_alone_refuses_without_pending_charge(env,monkeypatch):
    op=prepare(env);monkeypatch.setattr(wa,'require_dispatch_ready',lambda:None)
    with env[1].begin() as db:db.add(wa.CutoverRow(id=1,protocol_epoch=0,state='locked'))
    with pytest.raises(wa.DispatchRefused,match='cutover locked'):env[2].claim(op['id'],'t1')
    with env[1]() as db:assert db.get(BudgetAttemptRow,op['id']).state=='reserved' and db.get(GenerationRow,op['id']).fence is None


def test_same_approval_concurrent_reservation_debits_only_once(env):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    a=approved(env);barrier=threading.Barrier(2)
    def reserve():barrier.wait(5);return env[2].prepare(a['id'],'t1')
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:reserve(),range(2)))
    assert results[0]['id']==results[1]['id']
    with env[1]() as db:assert db.get(BudgetRow,'budget1').available_micro_usd==420 and len(db.scalars(select(BudgetAttemptRow)).all())==1


def test_reserved_binding_tamper_and_old_unknown_never_refunded(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch)
    with env[1].begin() as db:db.get(BudgetAttemptRow,op['id']).reserved_micro_usd=1
    with pytest.raises(wa.DispatchRefused,match='reservation differs'):env[2].claim(op['id'],'t1')
    with env[1]() as db:assert db.get(BudgetRow,'budget1').available_micro_usd==420


def test_real_sigkill_balance_update_before_reservation_commit_rolls_back(env,tmp_path):
    import os,sys,subprocess,signal,time
    a=approved(env);readyfile=tmp_path/'ready'
    script=r'''
import os,time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m00_approval_center.service import Service
from app.modules.m24_billing.generation import GenerationRepository
repo=GenerationRepository(Service(session_factory=sessionmaker(bind=create_engine(os.environ['DATABASE']),expire_on_commit=False)))
def hook(point):
 if point=='after-balance-update':
  with open(os.environ['READY'],'w') as f:f.write(str(os.getpid()));f.flush();os.fsync(f.fileno())
  while True:time.sleep(.05)
repo.prepare(os.environ['APPROVAL'],'t1',hook=hook)
'''
    child=subprocess.Popen([sys.executable,'-c',script],env={**os.environ,'DATABASE':str(env[1].kw['bind'].url),'APPROVAL':a['id'],'READY':str(readyfile)})
    try:
        until=time.monotonic()+12
        while not readyfile.exists() and time.monotonic()<until:
            assert child.poll() is None;time.sleep(.02)
        assert readyfile.exists() and int(readyfile.read_text())==child.pid
        os.kill(child.pid,signal.SIGKILL);assert child.wait(5)==-signal.SIGKILL
        with env[1]() as db:
            assert db.get(BudgetRow,'budget1').available_micro_usd==500
            assert db.scalar(select(GenerationRow)) is None and db.scalar(select(ApprovalEffectRow)) is None
        assert env[2].prepare(a['id'],'t1')['state']=='prepared'
    finally:
        if child.poll() is None:child.kill();child.wait(5)


def test_explicit_regeneration_cannot_bypass_exhausted_budget_or_overwrite_prior(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);dispatch(env,op,Mock(fail=True))
    with env[1].begin() as db:db.get(BudgetRow,'budget1').available_micro_usd=0
    with pytest.raises(wa.DispatchRefused,match='exhausted'):prepare(env,regenerates=op['id'])
    with env[1]() as db:
        assert db.get(BudgetAttemptRow,op['id']).state=='charged-pending'
        assert db.get(GenerationRow,op['id']).output is None
        assert len(db.scalars(select(BudgetAttemptRow)).all())==1


def test_changed_approval_inputs_refuse_replay_before_model(env):
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    a=approved(env);op=env[2].prepare(a['id'],'t1')
    with env[1].begin() as db:
        row=db.get(ApprovalRequestRow,a['id']);p=copy.deepcopy(row.payload);p['inputs']='Changed';row.payload=p
    with pytest.raises(wa.DispatchRefused,match='approval differs'):env[2].prepare(a['id'],'t1')
    with env[1]() as db:assert db.get(BudgetRow,'budget1').available_micro_usd==420


@pytest.mark.parametrize('inp,out,cost',[(11,10,52),(5,21,73),(11,21,85)])
def test_consistent_cost_over_token_or_charge_caps_refuses_no_release(env,monkeypatch,inp,out,cost):
    op=prepare(env);ready(env,monkeypatch);fence=env[2].claim(op['id'],'t1')
    with pytest.raises(wa.DispatchRefused,match='exceeds'):env[2].settle(op['id'],'t1',fence,response(input_tokens=inp,output_tokens=out,micro_usd=cost))
    with env[1]() as db:
        assert db.get(GenerationRow,op['id']).output is None
        assert db.get(BudgetRow,'budget1').available_micro_usd==420
        assert db.get(BudgetAttemptRow,op['id']).state=='charged-pending'


@pytest.mark.parametrize('method',['settle','before_entry','unknown'])
def test_wrong_fence_alone_refuses_all_three_boundaries(env,monkeypatch,method):
    op=prepare(env);ready(env,monkeypatch);fence=env[2].claim(op['id'],'t1')
    args=(op['id'],'t1','wrong-fence')
    with pytest.raises(wa.DispatchRefused):
        if method=='settle':env[2].settle(*args,response())
        else:getattr(env[2],method)(*args)
    with env[1]() as db:
        row=db.get(GenerationRow,op['id']);assert row.state=='dispatching' and row.fence==fence and row.output is None
        assert db.get(BudgetAttemptRow,op['id']).state=='charged-pending'
        assert db.get(BudgetRow,'budget1').available_micro_usd==420


@pytest.mark.parametrize('state',['prepared','succeeded'])
def test_regeneration_ineligible_target_state_refuses_new_reservation(env,state):
    op=prepare(env)
    with env[1].begin() as db:db.get(GenerationRow,op['id']).state=state
    with pytest.raises(wa.DispatchRefused,match='target unavailable'):prepare(env,regenerates=op['id'])
    with env[1]() as db:assert len(db.scalars(select(BudgetAttemptRow)).all())==1 and db.get(BudgetRow,'budget1').available_micro_usd==420


@pytest.mark.parametrize('different',['tenant','budget'])
def test_regeneration_cross_owner_or_budget_refuses_target(env,different):
    # Existing target identity is valid but isolated ownership field differs;
    # target is not revalidated, so no other binding guard masks this predicate.
    op=prepare(env)
    with env[1].begin() as db:
        db.add(BudgetRow(id='budget2',tenant_id='foreign' if different=='tenant' else 't1',account='fixture-account',price_schedule=PRICE,available_input=100,available_output=100,available_micro_usd=500,available_attempts=5))
        row=db.get(GenerationRow,op['id']);row.state='outcome_unknown'
        if different=='tenant':row.tenant_id='foreign'
        else:row.budget_id='budget2'
    with pytest.raises(wa.DispatchRefused,match='target unavailable'):prepare(env,regenerates=op['id'])
    with env[1]() as db:assert len(db.scalars(select(BudgetAttemptRow)).all())==1 and db.get(BudgetRow,'budget1').available_micro_usd==420


def test_response_price_schedule_id_alone_refuses(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);fence=env[2].claim(op['id'],'t1')
    with pytest.raises(wa.DispatchRefused,match='response authority'):env[2].settle(op['id'],'t1',fence,response(price_schedule_id='different'))
    with env[1]() as db:assert db.get(BudgetRow,'budget1').available_micro_usd==420 and db.get(GenerationRow,op['id']).output is None


@pytest.mark.parametrize('different',['price','account'])
def test_request_matches_budget_price_and_account_directly(env,different):
    from app.modules.m24_billing.generation import validate_request
    with env[1]() as db:
        budget=db.get(BudgetRow,'budget1');p=payload()
        if different=='price':p['price_schedule']={**PRICE,'id':'other-valid-schedule'}
        else:p['account']='other-account'
        with pytest.raises(wa.DispatchRefused):validate_request(p,'t1',budget)


@pytest.mark.parametrize('different',['binding_hash','permit'])
def test_generation_binding_hash_or_exact_permit_alone_refuses(env,monkeypatch,different):
    op=prepare(env);ready(env,monkeypatch)
    with env[1].begin() as db:
        if different=='binding_hash':db.get(GenerationRow,op['id']).binding_hash='0'*64
        else:db.scalar(select(ApprovalEffectRow).where(ApprovalEffectRow.approval_id==op['approval_id'])).effect_id='wrong-permit-id'
    with pytest.raises(wa.DispatchRefused,match='binding differs|permit differs'):env[2].claim(op['id'],'t1')
    with env[1]() as db:assert db.get(BudgetAttemptRow,op['id']).state=='reserved' and db.get(GenerationRow,op['id']).state=='prepared'


def test_before_entry_pending_charge_alone_refuses(env,monkeypatch):
    op=prepare(env);ready(env,monkeypatch);fence=env[2].claim(op['id'],'t1')
    with env[1].begin() as db:db.get(BudgetAttemptRow,op['id']).state='reserved'
    with pytest.raises(wa.DispatchRefused,match='pending charge missing'):env[2].before_entry(op['id'],'t1',fence)
    with env[1]() as db:assert db.get(GenerationRow,op['id']).state=='dispatching' and db.get(BudgetRow,'budget1').available_micro_usd==420


@pytest.mark.parametrize('different',['stored-digest','usage-digest'])
def test_proposal_digest_checks_independent_tampered_row(env,monkeypatch,different):
    op=prepare(env);ready(env,monkeypatch);result=dispatch(env,op,Mock());expected=result['output']['digest']
    with env[1].begin() as db:
        row=db.get(GenerationRow,op['id']);output=copy.deepcopy(row.output)
        if different=='stored-digest':output['digest']='0'*64
        else:output['usage']['output_tokens']=9
        row.output=output
    with pytest.raises(wa.DispatchRefused,match='output version'):env[2].description_for_proposal(op['id'],'t1',1,expected)


@pytest.mark.parametrize('field,value',[('tenant_id','foreign'),('account','foreign-account')])
def test_budget_owner_cas_isolated_change_between_validation_and_debit(env,monkeypatch,field,value):
    from sqlalchemy.orm import Session
    from sqlalchemy import update
    original=Session.execute;fired=[]
    def execute(db,statement,*args,**kwargs):
        if not fired and getattr(statement,'is_update',False) and getattr(getattr(statement,'table',None),'name',None)=='m24_generation_budgets':
            fired.append(True)
            # Same-transaction predicate isolation, NOT a concurrent-writer proof.
            # Change only the DB row after validation, before the original CAS.
            original(db,update(BudgetRow).where(BudgetRow.id=='budget1').values(**{field:value}))
        return original(db,statement,*args,**kwargs)
    monkeypatch.setattr(Session,'execute',execute)
    with pytest.raises(wa.DispatchRefused,match='exhausted'):prepare(env)
    assert fired
    with env[1]() as db:
        assert db.get(BudgetRow,'budget1').tenant_id=='t1' and db.get(BudgetRow,'budget1').account=='fixture-account'
        assert db.get(BudgetRow,'budget1').available_micro_usd==500 and db.scalar(select(ApprovalEffectRow)) is None
