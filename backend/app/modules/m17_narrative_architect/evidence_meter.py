from __future__ import annotations
import hashlib,json
from typing import Literal
from pydantic import BaseModel,Field,model_validator
class OwnerMaterial(BaseModel):material_id:str=Field(min_length=1);kind:Literal['owner_record','owner_statement','document','transcript'];sha256:str=Field(pattern=r'^[0-9a-f]{64}$');excerpt:str=Field(min_length=1,max_length=4000)
class NarrativeClaim(BaseModel):claim_id:str=Field(min_length=1);kind:Literal['concept','critique_suggestion'];text:str=Field(min_length=1,max_length=4000);material_ids:list[str]=Field(default_factory=list)
class EvidenceMeterRequest(BaseModel):
 materials:list[OwnerMaterial]=Field(default_factory=list,max_length=2000);claims:list[NarrativeClaim]=Field(min_length=1,max_length=2000)
 @model_validator(mode='after')
 def unique(self):
  for label,ids in [('material_id',[x.material_id for x in self.materials]),('claim_id',[x.claim_id for x in self.claims])]:
   if len(ids)!=len(set(ids)):raise ValueError(f'duplicate {label}')
  return self
def meter(body:EvidenceMeterRequest)->dict:
 known={x.material_id for x in body.materials};rows=[]
 for c in sorted(body.claims,key=lambda x:x.claim_id):
  linked=sorted(set(c.material_ids)&known);missing=sorted(set(c.material_ids)-known);rows.append({'claim_id':c.claim_id,'kind':c.kind,'text':c.text,'linked_material_ids':linked,'missing_material_ids':missing,'supported':bool(linked) and not missing,'needs_owner_input':not linked or bool(missing)})
 supported=sum(x['supported'] for x in rows);canonical=json.dumps(rows,sort_keys=True,separators=(',',':'))
 return {'claims':rows,'counts':{'total':len(rows),'supported':supported,'needs_owner_input':len(rows)-supported},'coverage':supported/len(rows),'meter_sha256':hashlib.sha256(canonical.encode()).hexdigest(),'boundary':'Links show supplied owner-material provenance only. Atlas does not prove factual truth, authorship, essay quality, or permission to disclose material.'}
