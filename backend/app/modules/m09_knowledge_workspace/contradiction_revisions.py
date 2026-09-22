from __future__ import annotations
import hashlib,json
from datetime import datetime
from typing import Literal
from pydantic import BaseModel,Field,model_validator
class SourceSnapshot(BaseModel):evidence_id:str=Field(min_length=1);content_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
class DecisionRevision(BaseModel):
 revision_id:str=Field(min_length=1);claim_key:str=Field(min_length=1);action:Literal['retain_both','prefer'];preferred_evidence_id:str|None=None;rationale:str=Field(min_length=1);decided_at:datetime;actor_id:str=Field(min_length=1);previous_revision_sha256:str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$');source_snapshots:list[SourceSnapshot]=Field(min_length=1)
 @model_validator(mode='after')
 def valid(self):
  if self.decided_at.tzinfo is None:raise ValueError('decided_at must be timezone-aware')
  if self.action=='prefer' and not self.preferred_evidence_id:raise ValueError('prefer requires preferred_evidence_id')
  ids=[x.evidence_id for x in self.source_snapshots]
  if len(ids)!=len(set(ids)):raise ValueError('duplicate evidence_id in source snapshots')
  if self.preferred_evidence_id and self.preferred_evidence_id not in ids:raise ValueError('preferred evidence is not snapshotted')
  return self
class RevisionChainRequest(BaseModel):
 revisions:list[DecisionRevision]=Field(min_length=1,max_length=1000)
 @model_validator(mode='after')
 def unique(self):
  ids=[x.revision_id for x in self.revisions]
  if len(ids)!=len(set(ids)):raise ValueError('duplicate revision_id')
  return self
def verify_revision_chain(body:RevisionChainRequest)->dict:
 hashes=[];expected=None;claim=None
 for i,r in enumerate(body.revisions):
  if claim is None:claim=r.claim_key.casefold().strip()
  elif r.claim_key.casefold().strip()!=claim:raise ValueError('all revisions must target the same claim_key')
  if r.previous_revision_sha256!=expected:
   raise ValueError(f'revision chain break at index {i}')
  payload=r.model_dump(mode='json');digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest();hashes.append(digest);expected=digest
 return {'valid':True,'claim_key':body.revisions[0].claim_key,'revision_count':len(hashes),'revision_hashes':hashes,'head_sha256':hashes[-1],'latest_decision':body.revisions[-1].model_dump(mode='json'),'boundary':'The chain proves supplied revision ordering and source content-hash references. It does not persist revisions, verify source bytes, authenticate actors, or establish which claim is true.'}
