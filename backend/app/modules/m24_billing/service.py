"""Official Stripe billing with test-mode validation and Module-0 money gates."""
from datetime import datetime,timezone
from uuid import uuid4
from app.core.models import ApprovalRequest
from .schemas import *
MODULE_ID=24
PLANS={p.id:p for p in [Plan(id="free",name="Free",monthly_price_usd=0,included_seats=1,included_runs=100,features=["BYOK","manual collectors"]),Plan(id="pro",name="Pro",monthly_price_usd=29,included_seats=1,included_runs=10000,features=["workers","monitoring","artifacts"]),Plan(id="team",name="Team",monthly_price_usd=99,included_seats=5,included_runs=50000,features=["team workspaces","priority queues","audit exports"])]}
class Service:
 def __init__(self,approvals,repo,stripe):self.approvals=approvals;self.repo=repo;self.stripe=stripe
 def plans(self):return list(PLANS.values())
 def propose_checkout(self,tenant_id,data:CheckoutIn):
  plan=PLANS.get(data.plan_id)
  if not plan:raise KeyError("plan not found")
  payload={"tenant_id":tenant_id,"plan":plan.model_dump(),"success_url":data.success_url,"cancel_url":data.cancel_url,"mode":"subscription","provider":"stripe"}
  req=self.approvals.put(ApprovalRequest(id=str(uuid4()),module_id=MODULE_ID,action_type="create_subscription_checkout",payload=payload));return ApprovalProposal(approval_id=req.id,action_type=req.action_type,payload=payload)
 async def execute_checkout(self,approval_id,tenant_id):
  view=self.repo.approval(approval_id)
  if view["status"]!="approved" or view["payload"]["tenant_id"]!=tenant_id:raise PermissionError("approved tenant-bound billing action required")
  plan=PLANS[view["payload"]["plan"]["id"]]
  if plan.monthly_price_usd<=0:raise ValueError("free plan does not need checkout")
  result=await self.stripe.create_checkout(plan,view["payload"]["success_url"],view["payload"]["cancel_url"],tenant_id,approval_id)
  self.repo.record_execution(approval_id,result);return result
 def propose_cancel(self,tenant_id,data:CancelIn):
  payload={"tenant_id":tenant_id,"subscription_id":data.subscription_id,"provider":"stripe","effect":"cancel_subscription"};req=self.approvals.put(ApprovalRequest(id=str(uuid4()),module_id=MODULE_ID,action_type="cancel_subscription",payload=payload));return ApprovalProposal(approval_id=req.id,action_type=req.action_type,payload=payload)
 def propose_invoice(self,tenant_id,data:InvoiceIn):
  payload={"tenant_id":tenant_id,**data.model_dump(),"provider":"stripe","effect":"create_draft_invoice"};req=self.approvals.put(ApprovalRequest(id=str(uuid4()),module_id=MODULE_ID,action_type="issue_invoice",payload=payload));return ApprovalProposal(approval_id=req.id,action_type=req.action_type,payload=payload)
 async def execute_approved(self,approval_id,tenant_id):
  view=self.repo.approval(approval_id)
  if not view or view["status"]!="approved" or view["payload"].get("tenant_id")!=tenant_id:raise PermissionError("approved tenant-bound billing action required")
  action=view["payload"].get("effect")
  if action=="cancel_subscription":result=await self.stripe.cancel_subscription(view["payload"]["subscription_id"],approval_id)
  elif action=="create_draft_invoice":result=await self.stripe.create_invoice(view["payload"]["customer_id"],view["payload"]["description"],view["payload"]["amount_cents"],view["payload"]["currency"],approval_id)
  else:raise ValueError("unsupported approved billing action")
  self.repo.record_execution(approval_id,result);return result
 def entitlements(self,tenant_id):
  row=self.repo.tenant_billing(tenant_id);plan=PLANS.get(row.plan_id if row else "free",PLANS["free"]);status=(row.status if row else "active")
  active=status in {"trialing","active"};limits={"seats":plan.included_seats,"runs":plan.included_runs} if active else {"seats":0,"runs":0}
  return EntitlementOut(plan_id=plan.id,status=status,features=plan.features if active else [],limits=limits,can_use_paid_features=active and plan.monthly_price_usd>0)
 def record_usage(self,tenant_id,data:UsageIn):
  ent=self.entitlements(tenant_id)
  if ent.status not in {"trialing","active","past_due"}:raise PermissionError("subscription cannot record usage in its current state")
  when=data.occurred_at or datetime.now(timezone.utc);ident=str(uuid4());row,created=self.repo.record_usage(tenant_id,ident,data.metric,data.quantity,data.idempotency_key,when,data.metadata)
  return UsageOut(id=row.id,metric=row.metric,quantity=row.quantity,occurred_at=row.occurred_at,created=created)
 def meter(self,tenant_id,start,end):
  if end<=start:raise ValueError("meter period end must follow start")
  ent=self.entitlements(tenant_id);usage=self.repo.usage_totals(tenant_id,start,end);included={"runs":ent.limits.get("runs",0)}
  return MeterOut(period_start=start,period_end=end,usage=usage,included=included,remaining={key:max(0,value-usage.get(key,0)) for key,value in included.items()})
 def subscription(self,tenant_id):
  row=self.repo.tenant_billing(tenant_id)
  if not row:return SubscriptionOut(tenant_id=tenant_id,plan_id="free",status="active")
  return SubscriptionOut.model_validate(row,from_attributes=True)
 def invoices(self,tenant_id):return [InvoiceOut.model_validate(x,from_attributes=True) for x in self.repo.list_invoices(tenant_id)]
 def _apply_lifecycle_event(self,event):
  obj=event.data.get("object",{});kind=event.type
  tenant_id=obj.get("metadata",{}).get("tenant_id") or obj.get("client_reference_id")
  if kind=="checkout.session.completed" and tenant_id:self.repo.upsert_tenant_billing(tenant_id,customer_id=obj.get("customer"),subscription_id=obj.get("subscription"),plan_id=obj.get("metadata",{}).get("plan_id","pro"),status="active")
  elif kind.startswith("customer.subscription."):
   tenant_id=tenant_id or obj.get("metadata",{}).get("atlas_tenant_id")
   if tenant_id:self.repo.upsert_tenant_billing(tenant_id,customer_id=obj.get("customer"),subscription_id=obj.get("id"),status=obj.get("status","canceled" if kind.endswith("deleted") else "active"),cancel_at_period_end=bool(obj.get("cancel_at_period_end")),current_period_start=datetime.fromtimestamp(obj["current_period_start"],timezone.utc) if obj.get("current_period_start") else None,current_period_end=datetime.fromtimestamp(obj["current_period_end"],timezone.utc) if obj.get("current_period_end") else None)
  elif kind.startswith("invoice."):
   tenant_id=tenant_id or obj.get("metadata",{}).get("atlas_tenant_id")
   if tenant_id:self.repo.upsert_invoice(tenant_id,id=obj["id"],status=obj.get("status",kind.removeprefix("invoice.")),currency=obj.get("currency","usd"),amount_due=int(obj.get("amount_due",0)),amount_paid=int(obj.get("amount_paid",0)),period_start=datetime.fromtimestamp(obj["period_start"],timezone.utc) if obj.get("period_start") else None,period_end=datetime.fromtimestamp(obj["period_end"],timezone.utc) if obj.get("period_end") else None,hosted_invoice_url=obj.get("hosted_invoice_url"))
 def ingest_event(self,event:BillingEventIn,*,trusted_provider=False):
  created=self.repo.save_event(event)
  if created and trusted_provider:self._apply_lifecycle_event(event)
  return BillingEventOut(id=event.id,type=event.type,processed=created,processed_at=datetime.now(timezone.utc))
