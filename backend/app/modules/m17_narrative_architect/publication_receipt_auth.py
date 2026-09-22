from __future__ import annotations
import base64,hashlib,json
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel,Field
class SignedPublicationReceipt(BaseModel):
 provider:str=Field(min_length=1);provider_id:str=Field(min_length=1);essay_id:str=Field(min_length=1);revision_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');audience_boundary:str=Field(min_length=1);published_at:str=Field(min_length=1);key_id:str=Field(min_length=1);signature_base64:str=Field(min_length=1)
class VerifyPublicationReceipt(BaseModel):
 expected_essay_id:str=Field(min_length=1);expected_revision_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');expected_audience_boundary:str=Field(min_length=1);receipt:SignedPublicationReceipt;trusted_ed25519_public_keys:dict[str,str]=Field(min_length=1)
def verify_publication_receipt(body:VerifyPublicationReceipt)->dict:
 r=body.receipt
 if (r.essay_id,r.revision_sha256,r.audience_boundary)!=(body.expected_essay_id,body.expected_revision_sha256,body.expected_audience_boundary):raise ValueError('publication receipt binding mismatch')
 encoded=body.trusted_ed25519_public_keys.get(r.key_id)
 if encoded is None:raise ValueError('untrusted publication provider public key')
 try:key=Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded,validate=True));sig=base64.b64decode(r.signature_base64,validate=True)
 except Exception as exc:raise ValueError('invalid provider key or signature encoding') from exc
 p=r.model_dump(mode='json',exclude={'signature_base64'});canonical=json.dumps(p,sort_keys=True,separators=(',',':')).encode()
 try:key.verify(sig,canonical)
 except InvalidSignature as exc:raise ValueError('invalid publication receipt signature') from exc
 return {'verified':True,**p,'signature_algorithm':'Ed25519','receipt_sha256':hashlib.sha256(canonical+sig).hexdigest(),'boundary':'Authenticates the supplied publication receipt and exact essay, revision and audience binding with a configured Ed25519 key. It does not establish key provisioning, publish, disclose, or verify external content bytes.'}
