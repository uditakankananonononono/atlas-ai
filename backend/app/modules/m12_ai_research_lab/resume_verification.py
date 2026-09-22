"""Fail-closed verification of dataset bytes and signed provider receipts before resume."""
from __future__ import annotations
import base64,hashlib,hmac,json
from datetime import datetime
from pydantic import BaseModel,Field,model_validator

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
class DatasetBytes(BaseModel):
 dataset_id:str=Field(min_length=1);expected_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');content_base64:str=Field(min_length=1);source_ref:str=Field(min_length=1);retrieved_at:datetime
 @model_validator(mode='after')
 def aware(self):
  if self.retrieved_at.tzinfo is None:raise ValueError('dataset retrieved_at must be timezone-aware')
  return self
class ProviderReceipt(BaseModel):
 node_id:str=Field(min_length=1);provider:str=Field(min_length=1);model:str=Field(min_length=1);input_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');output_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');spent_cents:int=Field(ge=0);issued_at:datetime;key_id:str=Field(min_length=1);signature_sha256_hmac:str=Field(pattern=r'^[0-9a-f]{64}$')
 @model_validator(mode='after')
 def aware(self):
  if self.issued_at.tzinfo is None:raise ValueError('receipt issued_at must be timezone-aware')
  return self
class ResumeVerificationRequest(BaseModel):
 checkpoint_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');resume_from_node_id:str=Field(min_length=1);datasets:list[DatasetBytes]=Field(min_length=1,max_length=500);provider_receipts:list[ProviderReceipt]=Field(default_factory=list,max_length=2000);trusted_hmac_keys:dict[str,str]=Field(min_length=1,max_length=100)
 @model_validator(mode='after')
 def unique(self):
  for label,ids in [('dataset_id',[x.dataset_id for x in self.datasets]),('node_id',[x.node_id for x in self.provider_receipts])]:
   if len(ids)!=len(set(ids)):raise ValueError(f'duplicate {label}')
  return self
def verify_resume(body:ResumeVerificationRequest)->dict:
 ds=[]
 for row in sorted(body.datasets,key=lambda x:x.dataset_id):
  try:raw=base64.b64decode(row.content_base64,validate=True)
  except Exception as exc:raise ValueError(f'invalid dataset base64: {row.dataset_id}') from exc
  actual=hashlib.sha256(raw).hexdigest()
  if actual!=row.expected_sha256:raise ValueError(f'dataset byte hash mismatch: {row.dataset_id}')
  ds.append({'dataset_id':row.dataset_id,'sha256':actual,'byte_count':len(raw),'source_ref':row.source_ref,'retrieved_at':row.retrieved_at.isoformat()})
 receipts=[]
 for row in sorted(body.provider_receipts,key=lambda x:x.node_id):
  key=body.trusted_hmac_keys.get(row.key_id)
  if key is None:raise ValueError(f'untrusted provider receipt key: {row.key_id}')
  payload=row.model_dump(mode='json',exclude={'signature_sha256_hmac'})
  expected=hmac.new(key.encode(),json.dumps(payload,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
  if not hmac.compare_digest(expected,row.signature_sha256_hmac):raise ValueError(f'invalid provider receipt signature: {row.node_id}')
  receipts.append({**payload,'signature_verified':True,'receipt_sha256':digest(row.model_dump(mode='json'))})
 artifact={'checkpoint_sha256':body.checkpoint_sha256,'resume_from_node_id':body.resume_from_node_id,'datasets':ds,'provider_receipts':receipts}
 return {'valid':True,**artifact,'verification_sha256':digest(artifact),'boundary':'This endpoint verifies supplied dataset bytes and HMAC-signed provider receipts against caller-configured trusted keys. It does not persist checkpoints, enqueue or execute work, retrieve datasets, validate provider identity beyond those keys, or resume a run.'}
