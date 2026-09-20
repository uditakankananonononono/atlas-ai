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
