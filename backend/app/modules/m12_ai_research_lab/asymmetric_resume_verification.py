"""Provider-issued Ed25519 receipt verification for reproducible-run resume."""
from __future__ import annotations
import base64,hashlib,json
from datetime import datetime
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel,Field,model_validator
class SignedProviderReceipt(BaseModel):
 node_id:str=Field(min_length=1);provider:str=Field(min_length=1);model:str=Field(min_length=1);input_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');output_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');spent_cents:int=Field(ge=0);issued_at:datetime;key_id:str=Field(min_length=1);signature_base64:str=Field(min_length=1)
 @model_validator(mode='after')
 def aware(self):
  if self.issued_at.tzinfo is None:raise ValueError('receipt issued_at must be timezone-aware')
  return self
class AsymmetricResumeVerificationRequest(BaseModel):
 checkpoint_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');resume_from_node_id:str=Field(min_length=1);provider_receipts:list[SignedProviderReceipt]=Field(min_length=1,max_length=2000);trusted_ed25519_public_keys:dict[str,str]=Field(min_length=1,max_length=100)
 @model_validator(mode='after')
 def unique(self):
  ids=[x.node_id for x in self.provider_receipts]
  if len(ids)!=len(set(ids)):raise ValueError('duplicate node_id')
  return self
def verify_asymmetric_resume(body:AsymmetricResumeVerificationRequest)->dict:
 out=[]
 for row in sorted(body.provider_receipts,key=lambda x:x.node_id):
  encoded=body.trusted_ed25519_public_keys.get(row.key_id)
  if encoded is None:raise ValueError(f'untrusted provider public key: {row.key_id}')
  try:key_bytes=base64.b64decode(encoded,validate=True);signature=base64.b64decode(row.signature_base64,validate=True);key=Ed25519PublicKey.from_public_bytes(key_bytes)
  except Exception as exc:raise ValueError(f'invalid provider key or signature encoding: {row.key_id}') from exc
  payload=row.model_dump(mode='json',exclude={'signature_base64'});canonical=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
  try:key.verify(signature,canonical)
  except InvalidSignature as exc:raise ValueError(f'invalid provider receipt signature: {row.node_id}') from exc
  out.append({**payload,'signature_algorithm':'Ed25519','signature_verified':True,'receipt_sha256':hashlib.sha256(canonical+signature).hexdigest()})
 artifact={'checkpoint_sha256':body.checkpoint_sha256,'resume_from_node_id':body.resume_from_node_id,'provider_receipts':out}
 return {'valid':True,**artifact,'verification_sha256':hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'boundary':'Verifies provider-issued Ed25519 signatures using caller-configured public keys. It does not establish how keys were provisioned, persist checkpoints, enqueue or execute work, retrieve datasets, or resume a run.'}
