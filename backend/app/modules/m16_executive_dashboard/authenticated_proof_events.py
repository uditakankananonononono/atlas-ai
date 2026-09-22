from __future__ import annotations
import hashlib,hmac,json
from datetime import datetime
from pydantic import BaseModel,Field,model_validator
class ProofEvent(BaseModel):
 event_id:str=Field(min_length=1);producer:str=Field(min_length=1);module_id:str=Field(min_length=1);requirement_id:str=Field(min_length=1);event_type:str=Field(pattern=r'^(artifact|test|deployment_receipt)$');proof_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');deployment_version:str|None=None;environment:str|None=None;issued_at:datetime;key_id:str=Field(min_length=1);signature_hmac_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
 @model_validator(mode='after')
 def valid(self):
  if self.issued_at.tzinfo is None:raise ValueError('issued_at must be timezone-aware')
  if self.event_type=='deployment_receipt' and (not self.deployment_version or not self.environment):raise ValueError('deployment receipt requires version and environment')
  return self
class VerifyProofEvents(BaseModel):events:list[ProofEvent]=Field(min_length=1,max_length=2000);trusted_producer_keys:dict[str,str]=Field(min_length=1)
def verify_proof_events(body:VerifyProofEvents)->dict:
 ids=[x.event_id for x in body.events]
 if len(ids)!=len(set(ids)):raise ValueError('duplicate event_id')
 out=[]
 for r in sorted(body.events,key=lambda x:x.event_id):
  key=body.trusted_producer_keys.get(r.key_id)
  if not key:raise ValueError(f'untrusted producer key: {r.key_id}')
  p=r.model_dump(mode='json',exclude={'signature_hmac_sha256'});sig=hmac.new(key.encode(),json.dumps(p,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
  if not hmac.compare_digest(sig,r.signature_hmac_sha256):raise ValueError(f'invalid producer event signature: {r.event_id}')
  out.append({**p,'signature_verified':True})
 artifact={'events':out};return {'valid':True,**artifact,'events_sha256':hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'boundary':'Authenticates supplied producer events using configured HMAC keys and preserves deployment bindings. It does not subscribe to producers, persist events, inspect proof bytes, deploy, or independently authenticate producers beyond configured keys.'}
