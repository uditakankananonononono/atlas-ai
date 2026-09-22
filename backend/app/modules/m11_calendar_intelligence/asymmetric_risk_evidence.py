from __future__ import annotations
import base64,hashlib,json
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel,Field
class SignedRiskSnapshot(BaseModel):
 evidence_id:str=Field(min_length=1);kind:str=Field(pattern=r'^(travel_estimate|cancellation_policy)$');source_uri:str=Field(min_length=1);retrieved_at:str=Field(min_length=1);content_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');provider:str=Field(min_length=1);key_id:str=Field(min_length=1);signature_base64:str=Field(min_length=1)
class VerifySignedRiskEvidence(BaseModel):snapshots:list[SignedRiskSnapshot]=Field(min_length=1,max_length=2000);trusted_ed25519_public_keys:dict[str,str]=Field(min_length=1)
def verify_signed_risk_evidence(body:VerifySignedRiskEvidence)->dict:
 ids=[x.evidence_id for x in body.snapshots]
 if len(ids)!=len(set(ids)):raise ValueError('duplicate evidence_id')
 out=[]
 for r in sorted(body.snapshots,key=lambda x:x.evidence_id):
  encoded=body.trusted_ed25519_public_keys.get(r.key_id)
  if encoded is None:raise ValueError(f'untrusted provider public key: {r.key_id}')
  try:key=Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded,validate=True));sig=base64.b64decode(r.signature_base64,validate=True)
  except Exception as exc:raise ValueError('invalid provider key or signature encoding') from exc
  p=r.model_dump(mode='json',exclude={'signature_base64'});canonical=json.dumps(p,sort_keys=True,separators=(',',':')).encode()
  try:key.verify(sig,canonical)
  except InvalidSignature as exc:raise ValueError(f'invalid risk evidence signature: {r.evidence_id}') from exc
  out.append({**p,'signature_algorithm':'Ed25519','signature_verified':True,'snapshot_receipt_sha256':hashlib.sha256(canonical+sig).hexdigest()})
 artifact={'snapshots':out};return {'valid':True,**artifact,'artifact_sha256':hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'boundary':'Verifies provider-signed risk snapshot metadata and content hashes with configured Ed25519 public keys. It does not retrieve or persist source bytes, prove route or policy truth, change events, cancel, or spend.'}
