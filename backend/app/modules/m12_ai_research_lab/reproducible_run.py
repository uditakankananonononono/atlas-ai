"""Canonical, resumable research-run checkpoint contract."""
from __future__ import annotations
import hashlib,json
from datetime import datetime
from typing import Literal
from pydantic import BaseModel,Field,model_validator
class DatasetPin(BaseModel):
 dataset_id:str=Field(min_length=1,max_length=300);sha256:str=Field(pattern=r'^[0-9a-f]{64}$');source_ref:str=Field(min_length=1,max_length=1000)
class NodeReceipt(BaseModel):
 node_id:str=Field(min_length=1,max_length=300);status:Literal['queued','running','completed','failed'];provider:str=Field(min_length=1,max_length=100);model:str=Field(min_length=1,max_length=300);seed:int|None=None;budget_cents:int=Field(ge=0);spent_cents:int=Field(ge=0);input_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');output_sha256:str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$');receipt_ref:str|None=None
 @model_validator(mode='after')
 def valid(self):
  if self.spent_cents>self.budget_cents:raise ValueError(f'spent_cents exceeds budget_cents: {self.node_id}')
  if self.status=='completed' and not self.output_sha256:raise ValueError(f'completed node requires output_sha256: {self.node_id}')
  return self
class ReproducibleRunRequest(BaseModel):
 run_id:str=Field(min_length=1,max_length=300);workflow_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');code_version:str=Field(min_length=1,max_length=200);created_at:datetime;datasets:list[DatasetPin]=Field(default_factory=list,max_length=500);nodes:list[NodeReceipt]=Field(min_length=1,max_length=2000);resume_from_node_id:str|None=None
 @model_validator(mode='after')
 def unique(self):
  if self.created_at.tzinfo is None:raise ValueError('created_at must be timezone-aware')
  for label,values in [('dataset_id',[x.dataset_id for x in self.datasets]),('node_id',[x.node_id for x in self.nodes])]:
   if len(values)!=len(set(values)):raise ValueError(f'duplicate {label}')
  if self.resume_from_node_id and self.resume_from_node_id not in {x.node_id for x in self.nodes}:raise ValueError('resume_from_node_id is unknown')
  return self
def checkpoint(body:ReproducibleRunRequest)->dict:
 nodes=[x.model_dump(mode='json') for x in body.nodes];datasets=[x.model_dump(mode='json') for x in body.datasets]
 resume=next((x for x in body.nodes if x.node_id==body.resume_from_node_id),None)
 if resume and resume.status=='completed':raise ValueError('cannot resume from a completed node')
 canonical={'run_id':body.run_id,'workflow_sha256':body.workflow_sha256,'code_version':body.code_version,'created_at':body.created_at.isoformat(),'datasets':datasets,'nodes':nodes,'resume_from_node_id':body.resume_from_node_id}
 digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {**canonical,'total_budget_cents':sum(x.budget_cents for x in body.nodes),'total_spent_cents':sum(x.spent_cents for x in body.nodes),'completed_nodes':sum(x.status=='completed' for x in body.nodes),'checkpoint_sha256':digest,'resumable':any(x.status in {'queued','running','failed'} for x in body.nodes),'boundary':'This checkpoint validates supplied identities, hashes, budgets, seeds and resume state. It does not execute nodes, verify dataset bytes, or authenticate provider receipts.'}
