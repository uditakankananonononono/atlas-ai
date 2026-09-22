from __future__ import annotations
import base64,hashlib,json
from datetime import datetime
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel,Field,model_validator
class SignedLiveReceipt(BaseModel):
 receipt_id:str=Field(min_length=1);requirement_id:str=Field(min_length=1);deployed_version:str=Field(min_length=1);environment:str=Field(min_length=1);acceptance_inputs_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');result_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');status:str=Field(pattern=r'^(passed|failed)$');issued_at:datetime;key_id:str=Field(min_length=1);signature_base64:str=Field(min_length=1)
 @model_validator(mode='after')
 def aware(self):
  if self.issued_at.tzinfo is None:raise ValueError('issued_at must be timezone-aware')
  return self
class VerifyAsymmetricLiveReceipts(BaseModel):
 expected_version:str=Field(min_length=1);expected_environment:str=Field(min_length=1);expected_inputs_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');receipts:list[SignedLiveReceipt]=Field(min_length=1,max_length=1000);trusted_ed25519_public_keys:dict[str,str]=Field(min_length=1)
def verify_asymmetric_live_receipts(body:VerifyAsymmetricLiveReceipts)->dict:
 out=[]
 for r in body.receipts:
  if (r.deployed_version,r.environment,r.acceptance_inputs_sha256)!=(body.expected_version,body.expected_environment,body.expected_inputs_sha256):raise ValueError(f'live receipt binding mismatch: {r.receipt_id}')
  encoded=body.trusted_ed25519_public_keys.get(r.key_id)
  if encoded is None:raise ValueError(f'untrusted issuer public key: {r.key_id}')
  try:key=Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded,validate=True));signature=base64.b64decode(r.signature_base64,validate=True)
  except Exception as exc:raise ValueError('invalid issuer key or signature encoding') from exc
  p=r.model_dump(mode='json',exclude={'signature_base64'});canonical=json.dumps(p,sort_keys=True,separators=(',',':')).encode()
  try:key.verify(signature,canonical)
  except InvalidSignature as exc:raise ValueError(f'invalid receipt signature: {r.receipt_id}') from exc
  out.append({**p,'signature_algorithm':'Ed25519','signature_verified':True})
 artifact={'deployed_version':body.expected_version,'environment':body.expected_environment,'acceptance_inputs_sha256':body.expected_inputs_sha256,'receipts':out}
 return {'valid':True,**artifact,'proof_sha256':hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'boundary':'Verifies Ed25519-signed live receipts and exact deployment, environment and input bindings. It does not govern key provisioning, deploy, run acceptance tests, persist receipts, or independently authenticate issuers beyond configured public keys.'}
