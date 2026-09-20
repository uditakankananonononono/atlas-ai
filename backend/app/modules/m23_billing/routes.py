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
