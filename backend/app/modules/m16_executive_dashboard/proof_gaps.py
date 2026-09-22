from __future__ import annotations
import hashlib,json
from pydantic import BaseModel,Field,model_validator
class RequirementProof(BaseModel):
 requirement_id:str=Field(min_length=1,max_length=300);module_id:str=Field(min_length=1,max_length=100);artifact_sha256:str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$');test_name:str|None=None;test_passed:bool=False;live_receipt_id:str|None=None;live_acceptance_passed:bool=False
 @model_validator(mode='after')
 def consistent(self):
  if self.test_passed and not self.test_name:raise ValueError('test_passed requires test_name')
  if self.live_acceptance_passed and not self.live_receipt_id:raise ValueError('live acceptance requires receipt id')
  return self
class ProofGapRequest(BaseModel):
 requirements:list[RequirementProof]=Field(min_length=1,max_length=5000)
 @model_validator(mode='after')
 def unique(self):
  ids=[x.requirement_id for x in self.requirements]
  if len(ids)!=len(set(ids)):raise ValueError('duplicate requirement_id')
  return self
def dashboard(body:ProofGapRequest)->dict:
 rows=[]
 for x in sorted(body.requirements,key=lambda z:(z.module_id,z.requirement_id)):
  code=bool(x.artifact_sha256);test=bool(x.test_name and x.test_passed);live=bool(x.live_receipt_id and x.live_acceptance_passed);g=[]
  if not code:g.append('code_artifact')
  if not test:g.append('test_evidence')
  if not live:g.append('live_acceptance')
  rows.append({'requirement_id':x.requirement_id,'module_id':x.module_id,'code_complete':code,'test_complete':test,'live_acceptance_complete':live,'gaps':g})
 modules={}
 for r in rows:
  m=modules.setdefault(r['module_id'],{'total':0,'code_complete':0,'test_complete':0,'live_acceptance_complete':0});m['total']+=1
  for k in ('code_complete','test_complete','live_acceptance_complete'):m[k]+=int(r[k])
 canonical=json.dumps(rows,sort_keys=True,separators=(',',':'))
 return {'requirements':rows,'modules':modules,'counts':{'total':len(rows),'with_code_gap':sum('code_artifact' in r['gaps'] for r in rows),'with_test_gap':sum('test_evidence' in r['gaps'] for r in rows),'with_live_gap':sum('live_acceptance' in r['gaps'] for r in rows)},'dashboard_sha256':hashlib.sha256(canonical.encode()).hexdigest(),'boundary':'Code, tests and live acceptance remain separate. Supplied hashes and receipt IDs are not authenticated by this dashboard.'}
