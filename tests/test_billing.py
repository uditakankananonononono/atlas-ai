import asyncio,httpx,pytest
from app.modules.m24_billing.service import Service
from app.modules.m24_billing.schemas import CheckoutIn,BillingEventIn
from app.modules.m24_billing.stripe_client import StripeClient
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

def test_stripe_webhook_signature_timestamp_and_payload_are_verified():
 import hashlib,hmac,json
 from app.modules.m24_billing.webhooks import verify_stripe_signature,StripeSignatureError
 payload=json.dumps({'id':'evt','type':'invoice.paid','created':100,'data':{}}).encode();ts=1000;sig=hmac.new(b'whsec_test',f'{ts}.'.encode()+payload,hashlib.sha256).hexdigest()
 assert verify_stripe_signature(payload,f't={ts},v1={sig}','whsec_test',now=1000)['id']=='evt'
 with pytest.raises(StripeSignatureError):verify_stripe_signature(payload,f't={ts},v1=bad','whsec_test',now=1000)
 with pytest.raises(StripeSignatureError):verify_stripe_signature(payload,f't={ts},v1={sig}','whsec_test',now=2000)

def test_cancel_and_invoice_are_separate_tenant_bound_approval_actions():
 from app.modules.m24_billing.schemas import CancelIn,InvoiceIn
 r=R();s=Service(A(),r,S())
 c=s.propose_cancel('t',CancelIn(subscription_id='sub_12345'));i=s.propose_invoice('t',InvoiceIn(customer_id='cus_12345',description='Atlas Team',amount_cents=9900))
 assert c.action_type=='cancel_subscription' and c.payload['subscription_id']=='sub_12345'
 assert i.action_type=='issue_invoice' and i.payload['amount_cents']==9900 and i.payload['effect']=='create_draft_invoice'
