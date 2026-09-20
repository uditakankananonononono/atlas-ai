"""Authenticated custom webhook intake that normalizes into the collection pipeline."""
import hashlib, hmac, json

def verify_webhook(secret: str, body: bytes, signature: str) -> dict:
    expected=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    supplied=signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected,supplied): raise ValueError("invalid webhook signature")
    payload=json.loads(body)
    if not isinstance(payload,dict): raise ValueError("webhook payload must be an object")
    return payload
