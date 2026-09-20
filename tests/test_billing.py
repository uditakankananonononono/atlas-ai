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

class LifecycleRepo(R):
 def __init__(self):super().__init__();self.billing={};self.usage={};self.invoice_rows=[]
 def tenant_billing(self,tenant):
  value=self.billing.get(tenant)
  return type('Row',(),value)() if value else None
 def upsert_tenant_billing(self,tenant,**values):self.billing.setdefault(tenant,{"tenant_id":tenant,"plan_id":"free","status":"active","customer_id":None,"subscription_id":None,"current_period_start":None,"current_period_end":None,"cancel_at_period_end":False}).update(values)
 def record_usage(self,tenant,ident,metric,quantity,key,when,metadata):
  prior=self.usage.get((tenant,key))
  if prior:return prior,False
  row=type('Usage',(),{"id":ident,"metric":metric,"quantity":quantity,"occurred_at":when})();self.usage[(tenant,key)]=row;return row,True
 def usage_totals(self,tenant,start,end):
  out={}
  for (owner,_),row in self.usage.items():
   if owner==tenant and start<=row.occurred_at<end:out[row.metric]=out.get(row.metric,0)+row.quantity
  return out
 def upsert_invoice(self,tenant,**values):self.invoice_rows.append((tenant,values))
 def list_invoices(self,tenant,limit=100):return []

def test_entitlements_metering_and_tenant_idempotency():
 from datetime import datetime,timezone,timedelta
 from app.modules.m24_billing.schemas import UsageIn
 repo=LifecycleRepo();repo.upsert_tenant_billing('t',plan_id='pro',status='active');s=Service(A(),repo,S());start=datetime(2026,1,1,tzinfo=timezone.utc);end=start+timedelta(days=30)
 assert s.entitlements('t').limits['runs']==10000
 first=s.record_usage('t',UsageIn(metric='runs',quantity=12,idempotency_key='job-1',occurred_at=start));again=s.record_usage('t',UsageIn(metric='runs',quantity=999,idempotency_key='job-1',occurred_at=start))
 assert first.created and not again.created and s.meter('t',start,end).usage=={'runs':12}

def test_subscription_and_invoice_events_update_lifecycle_once():
 from app.modules.m24_billing.schemas import BillingEventIn
 repo=LifecycleRepo();s=Service(A(),repo,S())
 sub=BillingEventIn(id='evt_sub',type='customer.subscription.updated',created=1,data={'object':{'id':'sub_1','customer':'cus_1','status':'past_due','metadata':{'atlas_tenant_id':'t'}}})
 assert s.ingest_event(sub,trusted_provider=True).processed and repo.billing['t']['status']=='past_due'
 inv=BillingEventIn(id='evt_inv',type='invoice.paid',created=1,data={'object':{'id':'in_1','status':'paid','currency':'usd','amount_due':2900,'amount_paid':2900,'metadata':{'atlas_tenant_id':'t'}}})
 assert s.ingest_event(inv,trusted_provider=True).processed and repo.invoice_rows[0][1]['amount_paid']==2900
 assert not s.ingest_event(inv,trusted_provider=True).processed and len(repo.invoice_rows)==1

def test_suspended_tenant_cannot_record_usage():
 from app.modules.m24_billing.schemas import UsageIn
 repo=LifecycleRepo();repo.upsert_tenant_billing('t',plan_id='pro',status='suspended');s=Service(A(),repo,S())
 with pytest.raises(PermissionError):s.record_usage('t',UsageIn(metric='runs',quantity=1,idempotency_key='x'))
