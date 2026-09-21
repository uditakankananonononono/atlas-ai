"""Deterministic subscription cost and cancellation preview before approval."""
from __future__ import annotations
from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any

def preview_commitment(*,plan:dict[str,Any],currency:str='USD',quantity:int=1,tax_rate_percent:float=0,renewal_interval:str='month',cancellation_policy:str,cancellation_deadline:datetime|None=None,as_of:datetime|None=None)->dict[str,Any]:
 if quantity<1:raise ValueError('quantity must be positive')
 if not 0<=tax_rate_percent<=100:raise ValueError('tax rate must be between 0 and 100')
 if renewal_interval not in {'month','year'}:raise ValueError('renewal interval must be month or year')
 currency=currency.upper()
 if len(currency)!=3:raise ValueError('currency must be a three-letter code')
 price=plan.get('monthly_price_usd')
 if price is None:raise ValueError('plan must include monthly_price_usd')
 if currency!='USD':raise ValueError('Atlas plan catalog is USD-only; no exchange rate is guessed')
 now=as_of or datetime.now(timezone.utc)
 if now.tzinfo is None:raise ValueError('as_of must be timezone-aware')
 if cancellation_deadline and cancellation_deadline.tzinfo is None:raise ValueError('cancellation_deadline must be timezone-aware')
 periods=12 if renewal_interval=='year' else 1
 subtotal=(Decimal(str(price))*quantity*periods).quantize(Decimal('.01'),ROUND_HALF_UP)
 tax=(subtotal*Decimal(str(tax_rate_percent))/100).quantize(Decimal('.01'),ROUND_HALF_UP)
 total=(subtotal+tax).quantize(Decimal('.01'),ROUND_HALF_UP)
 body={'plan_id':str(plan.get('id','')),'plan_name':str(plan.get('name','')),'currency':currency,'quantity':quantity,'renewal_interval':renewal_interval,'subtotal':str(subtotal),'tax_rate_percent':str(Decimal(str(tax_rate_percent))),'tax':str(tax),'exact_charge':str(total),'cancellation_policy':cancellation_policy.strip(),'cancellation_deadline':cancellation_deadline.isoformat() if cancellation_deadline else None,'generated_at':now.isoformat()}
 if not body['plan_id'] or not body['cancellation_policy']:raise ValueError('plan id and cancellation policy are required')
 digest=sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {**body,'preview_sha256':digest,'requires_exact_charge_approval':True,'executed':False,'warnings':(['Cancellation deadline has passed.'] if cancellation_deadline and cancellation_deadline<=now else [])+(['Tax rate was supplied by the caller and must be verified for the buyer jurisdiction.'] if tax_rate_percent else [])}
