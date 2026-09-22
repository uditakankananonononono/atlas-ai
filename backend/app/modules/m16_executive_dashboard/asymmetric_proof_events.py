from __future__ import annotations
import base64,hashlib,json
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel,Field
from .authenticated_proof_events import ProofEvent
class SignedProofEvent(ProofEvent):signature_hmac_sha256:str|None=None;signature_base64:str=Field(min_length=1)
class VerifyAsymmetricProofEvents(BaseModel):events:list[SignedProofEvent]=Field(min_length=1,max_length=2000);trusted_ed25519_public_keys:dict[str,str]=Field(min_length=1)
def verify_asymmetric_proof_events(body:VerifyAsymmetricProofEvents)->dict:
 ids=[x.event_id for x in body.events]
 if len(ids)!=len(set(ids)):raise ValueError('duplicate event_id')
 out=[]
 for r in sorted(body.events,key=lambda x:x.event_id):
  encoded=body.trusted_ed25519_public_keys.get(r.key_id)
  if encoded is None:raise ValueError(f'untrusted producer public key: {r.key_id}')
  try:key=Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded,validate=True));sig=base64.b64decode(r.signature_base64,validate=True)
  except Exception as exc:raise ValueError('invalid producer key or signature encoding') from exc
  p=r.model_dump(mode='json',exclude={'signature_base64','signature_hmac_sha256'});canonical=json.dumps(p,sort_keys=True,separators=(',',':')).encode()
  try:key.verify(sig,canonical)
  except InvalidSignature as exc:raise ValueError(f'invalid producer event signature: {r.event_id}') from exc
  out.append({**p,'signature_algorithm':'Ed25519','signature_verified':True})
 artifact={'events':out};return {'valid':True,**artifact,'events_sha256':hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'boundary':'Authenticates supplied producer events using configured Ed25519 public keys and preserves deployment bindings. It does not govern key provisioning, subscribe, persist events, inspect proof bytes, or deploy.'}
