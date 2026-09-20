"""Stripe webhook signature verification using Stripe's documented scheme."""
import hashlib,hmac,json,time
class StripeSignatureError(ValueError):pass
def verify_stripe_signature(payload:bytes,header:str,secret:str,tolerance_seconds:int=300,now:int|None=None):
 if not secret:raise StripeSignatureError('STRIPE_WEBHOOK_SECRET is not configured')
 parts={}
 for item in header.split(','):
  k,sep,v=item.partition('=')
  if sep:parts.setdefault(k,[]).append(v)
 try:timestamp=int(parts['t'][0]);signatures=parts['v1']
 except (KeyError,ValueError,IndexError) as e:raise StripeSignatureError('malformed Stripe-Signature header') from e
 current=int(time.time()) if now is None else now
 if abs(current-timestamp)>tolerance_seconds:raise StripeSignatureError('Stripe signature timestamp outside tolerance')
 signed=f'{timestamp}.'.encode()+payload;expected=hmac.new(secret.encode(),signed,hashlib.sha256).hexdigest()
 if not any(hmac.compare_digest(expected,x) for x in signatures):raise StripeSignatureError('invalid Stripe webhook signature')
 try:return json.loads(payload)
 except json.JSONDecodeError as e:raise StripeSignatureError('invalid Stripe event JSON') from e
