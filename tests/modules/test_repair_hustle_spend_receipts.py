import pytest
from app.modules.m18_side_hustle_scraper.runner import HustleRunner
class Approvals:
    def gate(self,**kw):return {'approval':{'id':'a'}}
    def consume_effect(self,*a,**kw):return {'allowed':True}

def test_m18_A05_spend_placeholder_cannot_issue_permit():
    runner=HustleRunner(Approvals());run=runner.create(title='Test',first_experiment='Observe',max_budget=25)
    step=next(s for s in run.steps if s.kind=='budget')
    with pytest.raises(ValueError,match='spend'):
        runner.request_action(run.id,step.id,'owner')

def test_m18_A06_success_receipt_requires_trusted_verification():
    runner=HustleRunner(Approvals());run=runner.create(title='Test',first_experiment='Observe')
    step=run.steps[0];runner.request_action(run.id,step.id,'owner');runner.authorize_action(run.id,step.id,'owner','worker')
    with pytest.raises(ValueError,match='verif'):
        runner.record_adapter_receipt(run.id,step.id,adapter='api',provider_receipt_id='invented',status='succeeded',observed_at='now',payload_sha256='a'*64)

def test_trusted_verifier_can_accept_exact_provider_receipt_and_reject_fabrication():
    runner=HustleRunner(Approvals(),receipt_verifier=lambda receipt,action,artifact:receipt['provider_receipt_id']=='known-id')
    run=runner.create(title='Test',first_experiment='Observe');step=run.steps[0]
    runner.request_action(run.id,step.id,'owner');runner.authorize_action(run.id,step.id,'owner','worker')
    with pytest.raises(ValueError,match='verification failed'):
        runner.record_adapter_receipt(run.id,step.id,adapter='api',provider_receipt_id='fake',status='succeeded',observed_at='now',payload_sha256='a'*64)
    receipt=runner.record_adapter_receipt(run.id,step.id,adapter='api',provider_receipt_id='known-id',status='succeeded',observed_at='now',payload_sha256='a'*64)
    assert receipt['verification']=='trusted host provider check'

def test_budget_with_restored_old_approval_is_still_refused_before_consume():
    class NeverConsume(Approvals):
        def consume_effect(self,*args,**kwargs):raise AssertionError('spend permit must not be consumed')
    runner=HustleRunner(NeverConsume());run=runner.create(title='Test',first_experiment='Observe')
    step=next(s for s in run.steps if s.kind=='budget');step.approval_id='legacy'
    with pytest.raises(ValueError,match='spend'):runner.authorize_action(run.id,step.id,'owner','worker')

def test_unknown_receipt_remains_unverified_observation():
    runner=HustleRunner(Approvals());run=runner.create(title='Test',first_experiment='Observe');step=run.steps[0]
    runner.request_action(run.id,step.id,'owner');runner.authorize_action(run.id,step.id,'owner','worker')
    receipt=runner.record_adapter_receipt(run.id,step.id,adapter='api',provider_receipt_id='unknown',status='unknown',observed_at='now',payload_sha256='a'*64)
    assert receipt['verification']=='unverified caller observation'
