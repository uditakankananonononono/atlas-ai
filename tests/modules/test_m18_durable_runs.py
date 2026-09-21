import pytest
from app.modules.m18_side_hustle_scraper.runner import DurableRunStore,DurableHustleRunner
class A:
 def gate(self,**kw):return {'approval':{'id':'approval-1'}}
 def consume_effect(self,*a,**kw):return {'allowed':True}
def test_durable_run_survives_runner_restart_with_receipt_and_outcome(tmp_path):
 store=DurableRunStore(tmp_path/'runs.db');r=DurableHustleRunner('tenant-a',store,A());run=r.create(title='Research tutoring',first_experiment='measure signups');step=run.steps[0]
 r.request_action(run.id,step.id,'owner');r.authorize_action(run.id,step.id,'owner','owner');receipt=r.record_adapter_receipt(run.id,step.id,adapter='api',provider_receipt_id='p1',status='succeeded',observed_at='now',payload_sha256='a'*64);r.record_outcome(run.id,metric='signup',value=2,unit='people',observed_at='later',receipt_sha256=receipt['receipt_sha256'])
 loaded=DurableHustleRunner('tenant-a',store,A()).get(run.id)
 assert loaded.steps[0].approval_id=='approval-1' and loaded.receipts[0]['provider_receipt_id']=='p1' and loaded.outcomes[0]['value']==2
def test_durable_runs_are_tenant_isolated(tmp_path):
 store=DurableRunStore(tmp_path/'runs.db');run=DurableHustleRunner('a',store,A()).create(title='A',first_experiment='test')
 with pytest.raises(KeyError):DurableHustleRunner('b',store,A()).get(run.id)
 assert store.list('b')==[]
