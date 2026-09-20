"""Official Stripe billing with test-mode validation and Module-0 money gates."""
from datetime import datetime,timezone
from uuid import uuid4
from app.core.models import ApprovalRequest
from .schemas import *
MODULE_ID=23
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
 def ingest_event(self,event:BillingEventIn):
  created=self.repo.save_event(event)
  return BillingEventOut(id=event.id,type=event.type,processed=created,processed_at=datetime.now(timezone.utc))
