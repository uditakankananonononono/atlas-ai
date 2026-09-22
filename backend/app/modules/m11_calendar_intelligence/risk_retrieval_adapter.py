from __future__ import annotations
import hashlib
from typing import Protocol
from pydantic import BaseModel,Field
class RiskSourceRetriever(Protocol):
 def fetch(self,source_uri:str)->bytes:...
class RetrieveRiskSource(BaseModel):source_uri:str=Field(pattern=r'^https://',max_length=2000);expected_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');provider:str=Field(min_length=1);retrieval_token:str=Field(min_length=1)
def retrieve_risk_source(body:RetrieveRiskSource,retriever:RiskSourceRetriever)->dict:
 data=retriever.fetch(body.source_uri)
 if not data:raise ValueError('provider retrieval returned empty bytes')
 actual=hashlib.sha256(data).hexdigest()
 if actual!=body.expected_sha256:raise ValueError('retrieved source byte hash mismatch')
 return {'verified':True,'source_uri':body.source_uri,'provider':body.provider,'content_sha256':actual,'byte_count':len(data),'boundary':'Retrieves bytes only through the configured provider adapter and verifies the expected hash. It does not persist bytes, prove route or policy truth, change events, cancel, or spend. The adapter owns provider authentication.'}
