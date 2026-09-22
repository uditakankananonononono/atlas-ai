from __future__ import annotations
import base64,hashlib,json
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel,Field
from .provider_receipt import ProviderPublicationReceipt
class AsymmetricProviderPublicationReceipt(ProviderPublicationReceipt):
 signature_hmac_sha256:str|None=None;signature_base64:str=Field(min_length=1)
class VerifyAsymmetricProviderPublication(BaseModel):
 expected_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');approval_consumed:bool;receipt:AsymmetricProviderPublicationReceipt;trusted_ed25519_public_keys:dict[str,str]=Field(min_length=1)
def verify_asymmetric_provider_publication(body:VerifyAsymmetricProviderPublication)->dict:
 if not body.approval_consumed:raise ValueError('approval must be consumed')
 r=body.receipt
 if r.published_sha256!=body.expected_sha256:raise ValueError('published hash does not match approved render')
 encoded=body.trusted_ed25519_public_keys.get(r.key_id)
 if encoded is None:raise ValueError('untrusted provider public key')
 try:key=Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded,validate=True));sig=base64.b64decode(r.signature_base64,validate=True)
 except Exception as exc:raise ValueError('invalid provider key or signature encoding') from exc
 p=r.model_dump(mode='json',exclude={'signature_base64','signature_hmac_sha256'});canonical=json.dumps(p,sort_keys=True,separators=(',',':')).encode()
 try:key.verify(sig,canonical)
 except InvalidSignature as exc:raise ValueError('invalid provider receipt signature') from exc
 return {'verified':True,**p,'signature_algorithm':'Ed25519','provider_signature_verified':True,'receipt_sha256':hashlib.sha256(canonical+sig).hexdigest(),'boundary':'Authenticates a supplied provider receipt with a configured Ed25519 public key and approved-render hash. It does not govern key provisioning, render, upload, inspect remote bytes, consume approval, or prove provider identity beyond that key.'}
