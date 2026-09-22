from __future__ import annotations
import base64,hashlib,json
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel,Field,model_validator
class AuthenticatedMessage(BaseModel):message_id:str=Field(min_length=1);content_base64:str=Field(min_length=1);content_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
class ReviewerAttestation(BaseModel):reviewer_id:str=Field(min_length=1);decision_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');key_id:str=Field(min_length=1);signature_base64:str=Field(min_length=1)
class VerifyReconciliationEvidence(BaseModel):
 messages:list[AuthenticatedMessage]=Field(min_length=1,max_length=1000)
 attestations:list[ReviewerAttestation]=Field(min_length=1,max_length=1000)
 trusted_reviewer_public_keys:dict[str,str]=Field(min_length=1)
 @model_validator(mode='after')
 def unique(self):
  for label,ids in [('message_id',[x.message_id for x in self.messages]),('reviewer_id',[x.reviewer_id for x in self.attestations])]:
   if len(ids)!=len(set(ids)):raise ValueError(f'duplicate {label}')
  return self
def verify_reconciliation_evidence(body:VerifyReconciliationEvidence)->dict:
 messages=[]
 for m in sorted(body.messages,key=lambda x:x.message_id):
  try:raw=base64.b64decode(m.content_base64,validate=True)
  except Exception as exc:raise ValueError(f'invalid source-message encoding: {m.message_id}') from exc
  actual=hashlib.sha256(raw).hexdigest()
  if actual!=m.content_sha256:raise ValueError(f'source-message byte hash mismatch: {m.message_id}')
  messages.append({'message_id':m.message_id,'content_sha256':actual,'byte_count':len(raw)})
 reviews=[]
 for a in sorted(body.attestations,key=lambda x:x.reviewer_id):
  encoded=body.trusted_reviewer_public_keys.get(a.key_id)
  if encoded is None:raise ValueError(f'untrusted reviewer public key: {a.key_id}')
  try:key=Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded,validate=True));sig=base64.b64decode(a.signature_base64,validate=True)
  except Exception as exc:raise ValueError('invalid reviewer key or signature encoding') from exc
  payload={'reviewer_id':a.reviewer_id,'decision_sha256':a.decision_sha256,'key_id':a.key_id};canonical=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
  try:key.verify(sig,canonical)
  except InvalidSignature as exc:raise ValueError(f'invalid reviewer signature: {a.reviewer_id}') from exc
  reviews.append({**payload,'signature_algorithm':'Ed25519','signature_verified':True})
 artifact={'messages':messages,'reviewers':reviews};return {'valid':True,**artifact,'evidence_sha256':hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'boundary':'Verifies supplied source-message bytes and reviewer Ed25519 attestations against configured public keys. It does not establish key ownership or message authorship, persist reconciliation, create tasks, draft, remind, or send.'}
