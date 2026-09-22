import httpx
class StripeClient:
 def __init__(self,secret_key:str,transport=None):
  if not secret_key.startswith("sk_test_"):raise ValueError("Atlas billing wiring requires a Stripe test-mode key until production launch approval")
  self.key=secret_key;self.transport=transport
 async def create_checkout(self,plan,success_url,cancel_url,tenant_id,approval_id):
  data={"mode":"subscription","success_url":success_url,"cancel_url":cancel_url,"client_reference_id":tenant_id,"metadata[atlas_approval_id]":approval_id,"metadata[tenant_id]":tenant_id,"metadata[plan_id]":plan.id,"subscription_data[metadata][atlas_tenant_id]":tenant_id,"subscription_data[metadata][plan_id]":plan.id,"line_items[0][price_data][currency]":"usd","line_items[0][price_data][product_data][name]":f"Atlas {plan.name}","line_items[0][price_data][unit_amount]":str(round(plan.monthly_price_usd*100)),"line_items[0][price_data][recurring][interval]":"month","line_items[0][quantity]":"1"}
  async with httpx.AsyncClient(timeout=30,transport=self.transport) as client:r=await client.post("https://api.stripe.com/v1/checkout/sessions",headers={"Authorization":f"Bearer {self.key}","Idempotency-Key":approval_id},data=data)
  r.raise_for_status();return r.json()

 async def cancel_subscription(self,subscription_id,approval_id):
  async with httpx.AsyncClient(timeout=30,transport=self.transport) as client:r=await client.delete(f"https://api.stripe.com/v1/subscriptions/{subscription_id}",headers={"Authorization":f"Bearer {self.key}","Idempotency-Key":approval_id})
  r.raise_for_status();return r.json()
 async def create_invoice(self,customer_id,description,amount_cents,currency,approval_id):
  headers={"Authorization":f"Bearer {self.key}","Idempotency-Key":approval_id}
  async with httpx.AsyncClient(timeout=30,transport=self.transport) as client:
   item=await client.post("https://api.stripe.com/v1/invoiceitems",headers=headers,data={"customer":customer_id,"description":description,"amount":str(amount_cents),"currency":currency});item.raise_for_status()
   invoice=await client.post("https://api.stripe.com/v1/invoices",headers=headers,data={"customer":customer_id,"auto_advance":"false","metadata[atlas_approval_id]":approval_id});invoice.raise_for_status();return invoice.json()


class UnconfiguredStripeClient:
    """Fail closed only when an approved billing mutation needs Stripe.

    Read-only plans, previews, entitlements and usage remain available without
    provider credentials; no request can be mistaken for external execution.
    """

    _message = "STRIPE_SECRET_KEY is required for external billing execution"

    async def create_checkout(self, *args, **kwargs):
        raise RuntimeError(self._message)

    async def cancel_subscription(self, *args, **kwargs):
        raise RuntimeError(self._message)

    async def create_invoice(self, *args, **kwargs):
        raise RuntimeError(self._message)
