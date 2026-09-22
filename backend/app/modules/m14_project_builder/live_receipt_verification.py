from __future__ import annotations
import hashlib,hmac,json
from datetime import datetime
from pydantic import BaseModel,Field,model_validator
class LiveReceipt(BaseModel):
 receipt_id:str=Field(min_length=1);requirement_id:str=Field(min_length=1);deployed_version:str=Field(min_length=1);environment:str=Field(min_length=1);acceptance_inputs_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');result_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');status:str=Field(pattern=r'^(passed|failed)$');issued_at:datetime;key_id:str=Field(min_length=1);signature_hmac_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
 @model_validator(mode='after')
 def aware(self):
  if self.issued_at.tzinfo is None:raise ValueError('issued_at must be timezone-aware')
  return self
class VerifyLiveReceipts(BaseModel):
 expected_version:str=Field(min_length=1);expected_environment:str=Field(min_length=1);expected_inputs_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');receipts:list[LiveReceipt]=Field(min_length=1,max_length=1000);trusted_keys:dict[str,str]=Field(min_length=1)
def verify_live_receipts(body:VerifyLiveReceipts)->dict:
 out=[]
 for r in body.receipts:
  if (r.deployed_version,r.environment,r.acceptance_inputs_sha256)!=(body.expected_version,body.expected_environment,body.expected_inputs_sha256):raise ValueError(f'live receipt binding mismatch: {r.receipt_id}')
  key=body.trusted_keys.get(r.key_id)
  if not key:raise ValueError(f'untrusted receipt key: {r.key_id}')
  payload=r.model_dump(mode='json',exclude={'signature_hmac_sha256'});expected=hmac.new(key.encode(),json.dumps(payload,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
  if not hmac.compare_digest(expected,r.signature_hmac_sha256):raise ValueError(f'invalid receipt signature: {r.receipt_id}')
  out.append({**payload,'signature_verified':True})
 artifact={'deployed_version':body.expected_version,'environment':body.expected_environment,'acceptance_inputs_sha256':body.expected_inputs_sha256,'receipts':out}
 return {'valid':True,**artifact,'proof_sha256':hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'boundary':'Verifies supplied HMAC receipts against configured keys and exact deployment, environment and input bindings. It does not deploy, execute acceptance tests, persist receipts, or independently authenticate the issuer.'}
