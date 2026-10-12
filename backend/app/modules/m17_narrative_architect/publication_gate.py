from __future__ import annotations
from typing import Protocol
from pydantic import BaseModel,Field
class PublicationAdapter(Protocol):
 def prepare(self,audience_boundary:str,revision_sha256:str)->dict:...
 def publish(self,audience_boundary:str,revision_sha256:str)->dict:...
class PublicationGateRequest(BaseModel):
 essay_id:str=Field(min_length=1);to_version:str=Field(min_length=1);revision_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');acceptance_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');reviewed_by_owner:bool;audience_boundary:str=Field(min_length=1);disclosure_approved:bool

def publish_through_gate(body:PublicationGateRequest,adapter:PublicationAdapter,acceptance:dict,*,key_registry=None)->dict:
 if acceptance.get('acceptance_sha256')!=body.acceptance_sha256 or acceptance.get('revision_sha256')!=body.revision_sha256 or acceptance.get('to_version')!=body.to_version or acceptance.get('audience_boundary')!=body.audience_boundary:raise ValueError('publication request does not match persisted revision acceptance')
 if not acceptance.get('reviewed_by_owner') or not body.reviewed_by_owner:raise ValueError('owner review is required before publication')
 if not acceptance.get('disclosure_approved') or not body.disclosure_approved:raise ValueError('disclosure approval is required for this audience boundary')
 if key_registry is None or not callable(getattr(key_registry,'verify',None)):raise ValueError('configured publication key registry required before publish')
 if not callable(getattr(adapter,'prepare',None)):raise ValueError('side-effect-free signed publication preflight required before publish')
 prepared=adapter.prepare(body.audience_boundary,body.revision_sha256)
 key_registry.verify(prepared,essay_id=body.essay_id,revision_sha256=body.revision_sha256,audience_boundary=body.audience_boundary)
 receipt=adapter.publish(body.audience_boundary,body.revision_sha256)
 verified=key_registry.verify(receipt,essay_id=body.essay_id,revision_sha256=body.revision_sha256,audience_boundary=body.audience_boundary)
 return {'published':True,'essay_id':body.essay_id,'to_version':body.to_version,'acceptance_sha256':body.acceptance_sha256,'audience_boundary':body.audience_boundary,'revision_sha256':body.revision_sha256,'publication_receipt':verified,'boundary':'Requires an exact signed side-effect-free preflight from an active configured provider key before calling the trusted adapter. Authenticates returned receipt after publishing; does not prove external content bytes or guarantee an arbitrary adapter obeys its preflight.'}
