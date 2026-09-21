from datetime import datetime
from typing import Literal
from pydantic import BaseModel,Field
class Plan(BaseModel): id:str;name:str;monthly_price_usd:float;included_seats:int;included_runs:int;features:list[str]
class CheckoutIn(BaseModel):plan_id:str;success_url:str;cancel_url:str
class ApprovalProposal(BaseModel):approval_id:str;action_type:Literal["create_subscription_checkout","cancel_subscription","issue_invoice"];payload:dict;status:Literal["pending"]="pending"
class BillingEventIn(BaseModel):id:str;type:str;created:int;data:dict
class BillingEventOut(BaseModel):id:str;type:str;processed:bool;processed_at:datetime

class CancelIn(BaseModel):subscription_id:str=Field(min_length=5,max_length=200)
class InvoiceIn(BaseModel):customer_id:str=Field(min_length=5,max_length=200);description:str=Field(min_length=1,max_length=1000);amount_cents:int=Field(gt=0,le=100000000);currency:str=Field(default="usd",pattern="^[a-z]{3}$")

SubscriptionStatus = Literal["trialing","active","past_due","suspended","canceled","incomplete","incomplete_expired","unpaid","paused","none"]
class EntitlementOut(BaseModel):
 plan_id:str;status:SubscriptionStatus;features:list[str];limits:dict[str,int];can_use_paid_features:bool
class UsageIn(BaseModel):
 metric:str=Field(min_length=1,max_length=80,pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$");quantity:int=Field(gt=0,le=100000000);idempotency_key:str=Field(min_length=1,max_length=160);occurred_at:datetime|None=None;metadata:dict[str,str]=Field(default_factory=dict)
class UsageOut(BaseModel):
 id:str;metric:str;quantity:int;occurred_at:datetime;created:bool
class MeterOut(BaseModel):
 period_start:datetime;period_end:datetime;usage:dict[str,int];included:dict[str,int];remaining:dict[str,int]
class SubscriptionOut(BaseModel):
 tenant_id:str;plan_id:str;status:SubscriptionStatus;customer_id:str|None=None;subscription_id:str|None=None;current_period_start:datetime|None=None;current_period_end:datetime|None=None;cancel_at_period_end:bool=False
class InvoiceOut(BaseModel):
 id:str;status:str;currency:str;amount_due:int;amount_paid:int;period_start:datetime|None=None;period_end:datetime|None=None;hosted_invoice_url:str|None=None

class CommitmentPreviewIn(BaseModel):
 plan_id:str=Field(min_length=1,max_length=40);currency:str=Field(default='USD',min_length=3,max_length=3);quantity:int=Field(default=1,ge=1,le=10000);tax_rate_percent:float=Field(default=0,ge=0,le=100);renewal_interval:Literal['month','year']='month';cancellation_policy:str=Field(min_length=1,max_length=5000);cancellation_deadline:datetime|None=None;as_of:datetime|None=None
