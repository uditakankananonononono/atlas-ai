from __future__ import annotations
import hashlib,hmac,json
from pydantic import BaseModel,Field
class ProducerEnvelope(BaseModel):producer:str=Field(min_length=1);delivery_id:str=Field(min_length=1);payload:dict;key_id:str=Field(min_length=1);signature_hmac_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
class VerifyProducerDelivery(BaseModel):envelope:ProducerEnvelope;trusted_delivery_keys:dict[str,str]=Field(min_length=1)
def verify_producer_delivery(body:VerifyProducerDelivery)->dict:
 e=body.envelope;key=body.trusted_delivery_keys.get(e.key_id)
 if not key:raise ValueError('untrusted producer delivery key')
 p=e.model_dump(mode='json',exclude={'signature_hmac_sha256'});expected=hmac.new(key.encode(),json.dumps(p,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
 if not hmac.compare_digest(expected,e.signature_hmac_sha256):raise ValueError('invalid producer delivery signature')
 return {'verified':True,'producer':e.producer,'delivery_id':e.delivery_id,'payload':e.payload,'delivery_sha256':hashlib.sha256(json.dumps(e.model_dump(mode='json'),sort_keys=True,separators=(',',':')).encode()).hexdigest(),'boundary':'Verifies one pushed producer delivery using a configured transport key. It does not create a remote subscription, persist events, validate nested proof semantics, inspect proof bytes, or deploy.'}
