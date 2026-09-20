import httpx
class StripeClient:
 def __init__(self,secret_key:str,transport=None):
  if not secret_key.startswith("sk_test_"):raise ValueError("Atlas billing wiring requires a Stripe test-mode key until production launch approval")
  self.key=secret_key;self.transport=transport
 async def create_checkout(self,plan,success_url,cancel_url,tenant_id,approval_id):
  data={"mode":"subscription","success_url":success_url,"cancel_url":cancel_url,"client_reference_id":tenant_id,"metadata[atlas_approval_id]":approval_id,"line_items[0][price_data][currency]":"usd","line_items[0][price_data][product_data][name]":f"Atlas {plan.name}","line_items[0][price_data][unit_amount]":str(round(plan.monthly_price_usd*100)),"line_items[0][price_data][recurring][interval]":"month","line_items[0][quantity]":"1"}
  async with httpx.AsyncClient(timeout=30,transport=self.transport) as client:r=await client.post("https://api.stripe.com/v1/checkout/sessions",headers={"Authorization":f"Bearer {self.key}","Idempotency-Key":approval_id},data=data)
  r.raise_for_status();return r.json()
