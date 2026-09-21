from app.modules.m18_side_hustle_scraper.runner import HustleRunner,StepState
class A:
 def gate(self,**kw):return {'approval':{'id':'approval-1'}}
 def consume_effect(self,*a,**kw):return {'allowed':True}
def test_receipt_and_outcome_bind_consumed_approval_without_fabricating_verification():
 r=HustleRunner(A());run=r.create(title='Lab tutoring',first_experiment='Measure qualified interest');step=run.steps[0]
 r.request_action(run.id,step.id,'u');r.authorize_action(run.id,step.id,'u','owner')
 rec=r.record_adapter_receipt(run.id,step.id,adapter='official-api',provider_receipt_id='post-1',status='succeeded',observed_at='2026-09-22T00:00:00Z',payload_sha256='a'*64)
 out=r.record_outcome(run.id,metric='qualified_interest',value=3,unit='people',observed_at='2026-09-23T00:00:00Z',receipt_sha256=rec['receipt_sha256'])
 assert rec['approval_id']=='approval-1' and len(rec['receipt_sha256'])==64
 assert 'not independently verified' in out['claim'] and r.view(run)['outcomes'][0]['value']==3
def test_receipt_rejected_before_consumed_approval_and_cross_run_outcome_rejected():
 import pytest
 r=HustleRunner(A());a=r.create(title='A',first_experiment='test');b=r.create(title='B',first_experiment='test');step=a.steps[0]
 with pytest.raises(ValueError,match='consumed approval'):r.record_adapter_receipt(a.id,step.id,adapter='x',provider_receipt_id='1',status='succeeded',observed_at='now',payload_sha256='a'*64)
 with pytest.raises(ValueError,match='does not belong'):r.record_outcome(b.id,metric='m',value=1,unit='u',observed_at='now',receipt_sha256='b'*64)
