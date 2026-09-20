import os
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from app.core.approvals import approvals
from .schemas import *
from .service import Service
from .repository import Repository
from .stripe_client import StripeClient
router=APIRouter(prefix="/billing",tags=["billing"])
def get_service():return Service(approvals,Repository(),StripeClient(os.getenv("STRIPE_SECRET_KEY","sk_test_unconfigured")))
@router.get("/plans",response_model=list[Plan])
def plans(s:Service=Depends(get_service)):return s.plans()
@router.post("/checkout-proposals",response_model=ApprovalProposal,status_code=201)
def propose(data:CheckoutIn,t:TenantContext=Depends(require_tenant),s:Service=Depends(get_service)):
 try:return s.propose_checkout(t.tenant_id,data)
 except KeyError as e:raise HTTPException(404,str(e))
@router.post("/checkout/{approval_id}/execute")
async def execute(approval_id:str,t:TenantContext=Depends(require_tenant),s:Service=Depends(get_service)):
 try:return await s.execute_checkout(approval_id,t.tenant_id)
 except (PermissionError,RuntimeError,ValueError) as e:raise HTTPException(409,str(e))
@router.post("/events",response_model=BillingEventOut)
def event(data:BillingEventIn,s:Service=Depends(get_service)):return s.ingest_event(data)
from fastapi import Request
from .webhooks import verify_stripe_signature,StripeSignatureError
@router.post('/cancel-proposals',response_model=ApprovalProposal,status_code=201)
def cancel_proposal(data:CancelIn,t:TenantContext=Depends(require_tenant),s:Service=Depends(get_service)):return s.propose_cancel(t.tenant_id,data)
@router.post('/invoice-proposals',response_model=ApprovalProposal,status_code=201)
def invoice_proposal(data:InvoiceIn,t:TenantContext=Depends(require_tenant),s:Service=Depends(get_service)):return s.propose_invoice(t.tenant_id,data)
@router.post('/approved/{approval_id}/execute')
async def execute_approved(approval_id:str,t:TenantContext=Depends(require_tenant),s:Service=Depends(get_service)):
 try:return await s.execute_approved(approval_id,t.tenant_id)
 except (PermissionError,RuntimeError,ValueError) as e:raise HTTPException(409,str(e))
@router.post('/stripe-webhook',response_model=BillingEventOut)
async def stripe_webhook(request:Request,s:Service=Depends(get_service)):
 payload=await request.body()
 try:data=verify_stripe_signature(payload,request.headers.get('stripe-signature',''),os.getenv('STRIPE_WEBHOOK_SECRET',''))
 except StripeSignatureError as e:raise HTTPException(400,str(e))
 return s.ingest_event(BillingEventIn(id=data['id'],type=data['type'],created=data['created'],data=data.get('data',{})))
from datetime import datetime
@router.get('/entitlements',response_model=EntitlementOut)
def entitlements(t:TenantContext=Depends(require_tenant),s:Service=Depends(get_service)):return s.entitlements(t.tenant_id)
@router.post('/usage',response_model=UsageOut,status_code=201)
def usage(data:UsageIn,t:TenantContext=Depends(require_tenant),s:Service=Depends(get_service)):
 try:return s.record_usage(t.tenant_id,data)
 except PermissionError as e:raise HTTPException(409,str(e))
@router.get('/meter',response_model=MeterOut)
def meter(start:datetime,end:datetime,t:TenantContext=Depends(require_tenant),s:Service=Depends(get_service)):
 try:return s.meter(t.tenant_id,start,end)
 except ValueError as e:raise HTTPException(422,str(e))
@router.get('/subscription',response_model=SubscriptionOut)
def subscription(t:TenantContext=Depends(require_tenant),s:Service=Depends(get_service)):return s.subscription(t.tenant_id)
@router.get('/invoices',response_model=list[InvoiceOut])
def invoices(t:TenantContext=Depends(require_tenant),s:Service=Depends(get_service)):return s.invoices(t.tenant_id)
