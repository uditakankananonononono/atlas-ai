from __future__ import annotations
import hashlib,json
from pydantic import BaseModel,Field,model_validator
class SubmitSnapshot(BaseModel):
 destination:str=Field(min_length=1,max_length=2000);fields:dict[str,str]=Field(default_factory=dict);total:str|None=None;currency:str|None=Field(default=None,pattern=r'^[A-Z]{3}$');irreversible_controls:list[str]=Field(default_factory=list)
 @model_validator(mode='after')
 def money(self):
  if (self.total is None)!=(self.currency is None):raise ValueError('total and currency must be supplied together')
  return self
class ReadbackDiffRequest(BaseModel):approved:SubmitSnapshot;current:SubmitSnapshot
def diff_readback(body:ReadbackDiffRequest)->dict:
 keys=sorted(set(body.approved.fields)|set(body.current.fields));changes=[{'field':k,'approved':body.approved.fields.get(k),'current':body.current.fields.get(k)} for k in keys if body.approved.fields.get(k)!=body.current.fields.get(k)]
 result={'destination_changed':body.approved.destination!=body.current.destination,'approved_destination':body.approved.destination,'current_destination':body.current.destination,'field_changes':changes,'price_changed':(body.approved.total,body.approved.currency)!=(body.current.total,body.current.currency),'approved_price':{'total':body.approved.total,'currency':body.approved.currency},'current_price':{'total':body.current.total,'currency':body.current.currency},'new_irreversible_controls':sorted(set(body.current.irreversible_controls)-set(body.approved.irreversible_controls))}
 result['requires_new_approval']=bool(result['destination_changed'] or changes or result['price_changed'] or result['new_irreversible_controls']);result['diff_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest();result['boundary']='Readback compares supplied snapshots only and never submits, clicks, pays, or treats DOM text as trusted.';return result
