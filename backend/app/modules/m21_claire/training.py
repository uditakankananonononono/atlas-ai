"""Reviewable local-model training jobs; execution is approval-gated."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json,uuid
from app.core.models import ApprovalRequest
@dataclass(frozen=True)
class TrainingDataset:
 kind:str;examples:list[dict];sha256:str
class TrainingService:
 def __init__(self,approvals):self.approvals=approvals
 def voice_dataset(self,samples:list[str]):
  clean=[x.strip() for x in samples if x.strip()]
  if not 50<=len(clean)<=2000:raise ValueError('voice tuning requires 50-2000 owner-authored samples')
  examples=[{'text':x,'provenance':'owner_authored'} for x in clean];body=json.dumps(examples,sort_keys=True).encode()
  return TrainingDataset('voice_lora',examples,sha256(body).hexdigest())
 def preference_dataset(self,rankings:list[dict]):
  if not isinstance(rankings,list):raise ValueError('rankings must be a list')
  examples=[]
  for r in rankings:
   if not isinstance(r,dict):raise ValueError('each ranking must be a record')
   opts=r.get('options',[]);order=r.get('ranking',[])
   if (not isinstance(opts,list) or not isinstance(order,list) or len(opts)<2
       or any(not isinstance(x,str) or not x.strip() for x in opts+order)
       or len(order)!=len(opts) or len(set(opts))!=len(opts)
       or len(set(order))!=len(order) or set(opts)!=set(order)):raise ValueError('ranking must order every supplied option exactly once')
   context=r.get('context','')
   if not isinstance(context,str):raise ValueError('ranking context must be text')
   examples.append({'context':context,'ranking':list(order),'options':list(opts),'provenance':'owner_ranked'})
  if len(examples)<20:raise ValueError('preference training requires at least 20 owner rankings')
  body=json.dumps(examples,sort_keys=True).encode();return TrainingDataset('preference',examples,sha256(body).hexdigest())
 def propose_training(self,dataset:TrainingDataset,base_model:str,method:str):
  if dataset.kind=='voice_lora' and method!='lora':raise ValueError('voice tuning supports LoRA only')
  payload={'dataset_kind':dataset.kind,'dataset_sha256':dataset.sha256,'example_count':len(dataset.examples),'base_model':base_model,'method':method,'execution_environment':'paired_local_pc_or_reviewed_gpu_worker','publishing':False,'estimated_cost_requires_review':True}
  req=self.approvals.put(ApprovalRequest(id=str(uuid.uuid4()),module_id=21,action_type='train_personalization_model',payload=payload));return {'approval_id':req.id,'status':'pending','payload':payload}
