import asyncio,httpx,pytest
from app.modules.m23_billing.service import Service
from app.modules.m23_billing.schemas import CheckoutIn,BillingEventIn
from app.modules.m23_billing.stripe_client import StripeClient
class A:
 def put(self,x):return x
class R:
 def __init__(self):self.events=set();self.recorded=[]
 def approval(self,x):return {"status":"approved","payload":{"tenant_id":"t","plan":{"id":"pro"},"success_url":"https://ok","cancel_url":"https://no"}}
 def record_execution(self,a,r):self.recorded.append(a)
 def save_event(self,e):new=e.id not in self.events;self.events.add(e.id);return new
class S:
 async def create_checkout(self,*x):return {"id":"cs_test","url":"https://checkout.stripe.test"}
def test_money_requires_proposal_and_approved_execution():
 r=R();s=Service(A(),r,S());p=s.propose_checkout("t",CheckoutIn(plan_id="pro",success_url="https://ok",cancel_url="https://no"));assert p.status=="pending"
 assert asyncio.run(s.execute_checkout(p.approval_id,"t"))["id"]=="cs_test"
def test_webhook_idempotency():
 s=Service(A(),R(),S());e=BillingEventIn(id="evt_1",type="invoice.paid",created=1,data={});assert s.ingest_event(e).processed and not s.ingest_event(e).processed
def test_stripe_requires_test_mode():
 with pytest.raises(ValueError):StripeClient("sk_live_never")
