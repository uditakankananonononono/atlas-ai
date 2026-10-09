"""Legacy behavior RED probes; replaced by inactive verified-inbox controls."""
import pytest
from app.modules.m24_billing.service import Service
from app.modules.m24_billing.schemas import BillingEventIn

class LegacyRepo:
    def __init__(self):self.events=set();self.updates=[];self.fail=False
    def save_event(self,e):
        new=e.id not in self.events;self.events.add(e.id);return new
    def upsert_tenant_billing(self,tenant,**values):
        if self.fail:raise RuntimeError('apply failed')
        self.updates.append((tenant,values))

def event(ident='evt_fixture',created=10,payment='paid'):
    return BillingEventIn(id=ident,type='checkout.session.completed',created=created,data={'object':{
        'metadata':{'tenant_id':'t1','plan_id':'pro'},'customer':'cus_fixture','subscription':'sub_fixture','payment_status':payment}})

def test_unsigned_does_not_poison_signed_identity():
    repo=LegacyRepo();s=Service(None,repo,None);s.ingest_event(event())
    s.ingest_event(event(),trusted_provider=True)
    assert len(repo.updates)==1

def test_failed_apply_signed_redelivery_is_not_lost():
    repo=LegacyRepo();s=Service(None,repo,None);repo.fail=True
    with pytest.raises(RuntimeError):s.ingest_event(event(),trusted_provider=True)
    repo.fail=False;s.ingest_event(event(),trusted_provider=True)
    assert len(repo.updates)==1

def test_unpaid_checkout_never_grants_active():
    repo=LegacyRepo();s=Service(None,repo,None);s.ingest_event(event(payment='unpaid'),trusted_provider=True)
    assert repo.updates==[]

def test_older_event_never_overwrites_newer():
    repo=LegacyRepo();s=Service(None,repo,None)
    for ident,created,status in [('evt_new',20,'canceled'),('evt_old',10,'active')]:
        s.ingest_event(BillingEventIn(id=ident,type='customer.subscription.updated',created=created,data={'object':{
            'id':'sub_fixture','customer':'cus_fixture','status':status,'metadata':{'atlas_tenant_id':'t1'}}}),trusted_provider=True)
    assert len(repo.updates)==1 and repo.updates[-1][1]['status']=='canceled'
