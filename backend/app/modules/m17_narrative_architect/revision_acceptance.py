from __future__ import annotations
import hashlib,json
from datetime import datetime
from pydantic import BaseModel,Field,model_validator
class AcceptedSuggestion(BaseModel):suggestion_id:str=Field(min_length=1);suggestion_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');owner_record_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
class RevisionAcceptance(BaseModel):
 essay_id:str=Field(min_length=1);from_version:str=Field(min_length=1);to_version:str=Field(min_length=1);revision_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');accepted_suggestions:list[AcceptedSuggestion]=Field(min_length=1,max_length=1000);reviewed_by_owner:bool;reviewed_at:datetime;audience_boundary:str=Field(min_length=1);disclosure_approved:bool=False
 @model_validator(mode='after')
 def valid(self):
  if self.from_version==self.to_version:raise ValueError('revision versions must differ')
  if self.reviewed_at.tzinfo is None:raise ValueError('reviewed_at must be timezone-aware')
  if not self.reviewed_by_owner:raise ValueError('owner review is required')
  ids=[x.suggestion_id for x in self.accepted_suggestions]
  if len(ids)!=len(set(ids)):raise ValueError('duplicate suggestion_id')
  return self
def verify_revision_acceptance(body:RevisionAcceptance)->dict:
 payload=body.model_dump(mode='json');digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {'valid':True,**payload,'may_cross_audience_boundary':body.disclosure_approved,'acceptance_sha256':digest,'boundary':'Binds owner-reviewed accepted suggestions to a named essay revision and audience. It does not edit, publish, disclose, send, establish source truth, or treat review as disclosure approval; crossing the audience boundary requires disclosure_approved.'}
