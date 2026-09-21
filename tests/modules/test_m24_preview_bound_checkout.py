import asyncio,pytest
from datetime import datetime,timezone
from app.modules.m24_billing.precommit import preview_commitment,verify_commitment_preview
from app.modules.m24_billing.service import Service,PLANS
from app.modules.m24_billing.schemas import PreviewedCheckoutIn
class A:
 def put(self,x):return x
class Repo:
 def __init__(self):self.item=None;self.recorded=[]
 def approval(self,_):return self.item
 def record_execution(self,a,r):self.recorded.append((a,r))
class Stripe:
 async def create_checkout(self,*args):return {'id':'cs_test','url':'https://stripe.test'}
def preview():return preview_commitment(plan=PLANS['pro'].model_dump(),cancellation_policy='Cancel before renewal',as_of=datetime(2026,9,22,tzinfo=timezone.utc))
def test_preview_bound_proposal_and_execution_revalidate_exact_approved_charge():
 repo=Repo();s=Service(A(),repo,Stripe());p=s.propose_previewed_checkout('tenant',PreviewedCheckoutIn(success_url='https://ok',cancel_url='https://cancel',commitment_preview=preview()))
 assert p.payload['commitment_preview_sha256']==preview()['preview_sha256'] and p.payload['expected_charge_cents']==2900
 repo.item={'status':'approved','payload':p.payload};assert asyncio.run(s.execute_checkout(p.approval_id,'tenant'))['id']=='cs_test'
def test_tampering_or_unsupported_checkout_shape_fails_closed():
 p=preview();p['exact_charge']='1.00'
 with pytest.raises(ValueError,match='hash mismatch'):verify_commitment_preview(p,PLANS['pro'].model_dump(),checkout_supported=True)
 annual=preview_commitment(plan=PLANS['pro'].model_dump(),renewal_interval='year',cancellation_policy='cancel',as_of=datetime(2026,9,22,tzinfo=timezone.utc))
 with pytest.raises(ValueError,match='currently supports'):verify_commitment_preview(annual,PLANS['pro'].model_dump(),checkout_supported=True)
