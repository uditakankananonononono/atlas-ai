"""Strong bounded implementations for atomic concepts 24-46.

Design sources:
- Hugging Face PEFT LoRA docs: https://huggingface.co/docs/peft/main/en/conceptual_guides/adapter
- NIST AI RMF privacy/control: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf
- Bradley-Terry preference model assumptions: https://academic.oup.com/jrsssa/article/187/3/898/7471963
The module creates real local records, datasets and evaluation proposals. It never claims
training, activation, GPU readiness, telemetry collection, or convergence without evidence.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from hashlib import sha256
from math import exp,log,sqrt
from datetime import datetime,timezone
from typing import Any
ROWS={'3.2':'Correction-pair vector retrieval','3.3':'Retrieved corrections injected as few-shot examples','3.4':'Repeat-error tracking against prior corrections','4.1':'Consented collection of 50-200 owner writing samples','4.2':'Voice dataset validation and provenance','4.3':'LoRA fine-tuning job proposal for a local model','4.4':'Ollama-compatible local training target','4.5':'GPU/resource readiness and cost estimate','4.6':'Voice-similarity and factuality evaluation before activation','5.1':'Owner-authored reasoning-note capture','5.2':'Reasoning-note embedding and retrieval','5.3':'Similar-problem retrieval at decision time','5.4':'Owner reasoning-note use as a decision template','5.5':'Explicit rejection of hidden model chain-of-thought capture','6.1':'Three-to-five option generation','6.2':'Complete owner ranking capture','6.3':'Pairwise preference-dataset construction','6.4':'Local preference-model training proposal','6.5':'Preference-model evaluation before activation','7.1':'Explicit opt-in telemetry consent','7.2':'Link-click telemetry','7.3':'Opportunity-application telemetry','7.4':'Draft-edit-duration telemetry'}
RESEARCH={'peft_lora':'https://huggingface.co/docs/peft/main/en/conceptual_guides/adapter','nist_privacy':'https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf','bradley_terry':'https://academic.oup.com/jrsssa/article/187/3/898/7471963'}
class AtomicError(ValueError):pass
def _cos(a,b):
 if not a or len(a)!=len(b):raise AtomicError('embeddings must be nonempty and aligned')
 den=sqrt(sum(x*x for x in a)*sum(x*x for x in b));return sum(x*y for x,y in zip(a,b))/den if den else 0.
def _id(*parts):return sha256('|'.join(map(str,parts)).encode()).hexdigest()[:24]
def _now():return datetime.now(timezone.utc).isoformat()
@dataclass
class AtomicStore:
 corrections:list[dict]=field(default_factory=list);samples:list[dict]=field(default_factory=list);reasoning_notes:list[dict]=field(default_factory=list);rankings:list[dict]=field(default_factory=list);consents:dict[str,dict]=field(default_factory=dict);telemetry:list[dict]=field(default_factory=list)
class AtomicService:
 def __init__(self,embed=None,store=None):self.embed=embed or self._embed;self.store=store or AtomicStore()
 @staticmethod
 def _embed(text):
  toks=text.lower().split();return [float(len(toks)),float(sum(c.isalpha() for c in text)),float(sum(t in {'i','my','me'} for t in toks)),float(len(set(toks)))]
 def correction(self,tenant,original,corrected,context='',tags=None):
  if not tenant or not original.strip() or not corrected.strip() or original.strip()==corrected.strip():raise AtomicError('tenant and distinct nonempty original/correction required')
  rec={'id':_id(tenant,original,corrected,context),'tenant_id':tenant,'original':original,'correction':corrected,'context':context,'tags':tags or [],'embedding':self.embed(original+' '+context),'created_at':_now(),'active':True};self.store.corrections.append(rec);return rec
 def retrieve_corrections(self,tenant,query,k=5,min_similarity=0):
  if not 1<=k<=20:raise AtomicError('k must be 1..20')
  q=self.embed(query);hits=[{'correction_id':x['id'],'original':x['original'],'correction':x['correction'],'context':x['context'],'similarity':round(_cos(q,x['embedding']),6)} for x in self.store.corrections if x['tenant_id']==tenant and x['active']];return [x for x in sorted(hits,key=lambda z:(-z['similarity'],z['correction_id'])) if x['similarity']>=min_similarity][:k]
 def few_shot(self,tenant,query,k=3):
  hits=self.retrieve_corrections(tenant,query,k);return {'messages':[m for h in hits for m in ({'role':'assistant','content':h['original']},{'role':'user','content':h['correction']})],'correction_ids':[h['correction_id'] for h in hits],'instruction':'Treat owner corrections as scoped examples, not permission or universal rules. Current request wins.','generated_output':False}
 def repeat_error(self,tenant,candidate,query,threshold=.85):
  if not 0<=threshold<=1:raise AtomicError('threshold must be in [0,1]')
  hits=self.retrieve_corrections(tenant,query,20);violations=[h for h in hits if h['similarity']>=threshold and h['original'].strip().lower() in candidate.lower() and h['correction'].strip().lower() not in candidate.lower()];return {'repeat_error':bool(violations),'violations':violations,'checked_correction_ids':[h['correction_id'] for h in hits],'candidate_blocked':bool(violations)}
 def add_sample(self,tenant,text,source,consented,owner_authored=True,license_status='owner'):
  if not consented:raise AtomicError('explicit owner consent required')
  if not owner_authored or license_status!='owner':raise AtomicError('only owner-authored, owner-controlled samples accepted')
  if len(text.strip())<20:raise AtomicError('sample too short')
  rec={'id':_id(tenant,source,text),'tenant_id':tenant,'text':text,'source':source,'consent':True,'owner_authored':True,'license_status':license_status,'sha256':sha256(text.encode()).hexdigest(),'collected_at':_now()};self.store.samples.append(rec);return rec
 def validate_dataset(self,tenant):
  xs=[x for x in self.store.samples if x['tenant_id']==tenant];unique={x['sha256']:x for x in xs};word_counts=[len(x['text'].split()) for x in unique.values()];count=len(unique);return {'sample_count':count,'duplicate_count':len(xs)-count,'total_words':sum(word_counts),'source_counts':{s:sum(x['source']==s for x in unique.values()) for s in {x['source'] for x in unique.values()}},'provenance_complete':all(x['consent'] and x['owner_authored'] and x['license_status']=='owner' for x in unique.values()),'target_range':[50,200],'target_met':50<=count<=200,'ready_for_split':50<=count<=200 and all(x['consent'] for x in unique.values()),'records':[{'id':x['id'],'source':x['source'],'sha256':x['sha256']} for x in unique.values()]}
 def lora_proposal(self,tenant,base_model,config):
  ds=self.validate_dataset(tenant)
  if not ds['ready_for_split']:raise AtomicError('validated 50-200 sample dataset required')
  required=('rank','alpha','dropout','target_modules','epochs','learning_rate')
  if any(k not in config for k in required):raise AtomicError('complete LoRA config required')
  if not (1<=config['rank']<=256 and 0<=config['dropout']<1 and config['target_modules']):raise AtomicError('invalid LoRA configuration')
  return {'job_type':'peft_lora_causal_lm','base_model':base_model,'dataset_manifest':ds['records'],'split':{'train':.8,'validation':.1,'test':.1,'group_by_source':True},'config':config,'evaluation_before_activation':['held-out perplexity','blind owner voice preference','factual consistency','memorization/canary check'],'status':'proposal_not_started','adapter_trained':False,'reference':RESEARCH['peft_lora']}
 def ollama_target(self,proposal,model_name):
  if proposal.get('job_type')!='peft_lora_causal_lm':raise AtomicError('LoRA proposal required')
  return {'model_name':model_name,'base_model':proposal['base_model'],'adapter_artifact_required':True,'modelfile_template':f'FROM {proposal["base_model"]}\nADAPTER ./adapter\nPARAMETER temperature 0.3','ollama_import_test':['adapter path resolves','tokenizer compatible','smoke inference','base-vs-adapter comparison'],'compatible_claim':'pending_adapter_export_and_local_import_test','installed':False}
 @staticmethod
 def readiness(hardware,job,cloud_rate_per_hour=None,estimated_hours=None):
  vram=float(hardware.get('vram_gb',0));disk=float(hardware.get('free_disk_gb',0));ram=float(hardware.get('ram_gb',0));quant=job.get('quantization_bits',16);needed=10 if quant<=4 else 18;checks={'vram':vram>=needed,'ram':ram>=16,'disk':disk>=20,'cuda_or_mps':bool(hardware.get('accelerator'))};cost=None if cloud_rate_per_hour is None or estimated_hours is None else round(float(cloud_rate_per_hour)*float(estimated_hours),2);return {'checks':checks,'local_ready':all(checks.values()),'minimum_vram_gb_assumption':needed,'estimated_cloud_cost':cost,'currency':hardware.get('currency','USD'),'estimate_only':True,'training_started':False}
 @staticmethod
 def evaluate_voice(rows,thresholds):
  if not rows:raise AtomicError('held-out evaluation rows required')
  required=('voice_preference','factuality','memorization_match')
  if any(any(k not in r for k in required) for r in rows):raise AtomicError('complete evaluation metrics required')
  metrics={k:sum(float(r[k]) for r in rows)/len(rows) for k in required};passed=metrics['voice_preference']>=thresholds.get('voice_preference',.6) and metrics['factuality']>=thresholds.get('factuality',.98) and metrics['memorization_match']<=thresholds.get('memorization_match',.05);return {'held_out_count':len(rows),'metrics':metrics,'thresholds':thresholds,'activation_recommended':passed,'activated':False,'failure_reasons':[k for k in required if (k!='memorization_match' and metrics[k]<thresholds.get(k,0)) or (k=='memorization_match' and metrics[k]>thresholds.get(k,1))]}
 def reasoning_note(self,tenant,problem,steps,conclusion,owner_authored,consented=True):
  if not owner_authored or not consented:raise AtomicError('only consented owner-authored reasoning notes accepted')
  if not problem.strip() or len(steps)<2 or any(not str(x).strip() for x in steps):raise AtomicError('problem and at least two explicit owner steps required')
  text=problem+' '+' '.join(steps)+' '+conclusion;rec={'id':_id(tenant,text),'tenant_id':tenant,'problem':problem,'steps':steps,'conclusion':conclusion,'owner_authored':True,'embedding':self.embed(text),'created_at':_now(),'hidden_model_chain_of_thought':False};self.store.reasoning_notes.append(rec);return rec
 def retrieve_reasoning(self,tenant,problem,k=3):
  q=self.embed(problem);hits=[{'note_id':x['id'],'problem':x['problem'],'steps':x['steps'],'conclusion':x['conclusion'],'similarity':round(_cos(q,x['embedding']),6)} for x in self.store.reasoning_notes if x['tenant_id']==tenant];return sorted(hits,key=lambda x:-x['similarity'])[:k]
 def decision_template(self,tenant,problem):
  hits=self.retrieve_reasoning(tenant,problem);return {'retrieved_notes':hits,'template':{'owner_steps':[{'note_id':h['note_id'],'steps':h['steps']} for h in hits],'apply_by_analogy_not_copy':True,'verify_current_facts':True,'current_owner_review_required':True},'hidden_chain_of_thought_requested':False}
 @staticmethod
 def reject_hidden_cot(source_type):
  if source_type!='owner_authored_note':return {'accepted':False,'reason':'Hidden model chain-of-thought is not collected, exposed, stored, or treated as owner reasoning. Use concise rationale or owner-authored notes.'}
  return {'accepted':True,'reason':'Explicit owner-authored reasoning note is eligible with consent.'}
 @staticmethod
 def generate_options(candidates):
  if not 3<=len(candidates)<=5:raise AtomicError('exactly 3-5 distinct options required')
  ids=[x.get('id') for x in candidates]
  if None in ids or len(set(ids))!=len(ids):raise AtomicError('options need unique ids')
  if any(not x.get('tradeoffs') for x in candidates):raise AtomicError('each option needs explicit tradeoffs')
  return {'options':candidates,'count':len(candidates),'ranking_requested':True,'selected':None}
 def capture_ranking(self,tenant,options,ordered_ids,context=''):
  ids=[x['id'] for x in options]
  if len(ids)!=len(ordered_ids) or set(ids)!=set(ordered_ids) or len(set(ordered_ids))!=len(ordered_ids):raise AtomicError('complete permutation ranking required')
  rec={'id':_id(tenant,context,*ordered_ids),'tenant_id':tenant,'context':context,'options':options,'ranking':ordered_ids,'created_at':_now()};self.store.rankings.append(rec);return rec
 @staticmethod
 def pairwise(ranking):
  pairs=[]
  for i,w in enumerate(ranking['ranking']):
   for l in ranking['ranking'][i+1:]:pairs.append({'ranking_id':ranking['id'],'winner':w,'loser':l,'context':ranking['context']})
  return {'pairs':pairs,'pair_count':len(pairs),'expected_pair_count':len(ranking['ranking'])*(len(ranking['ranking'])-1)//2,'complete':True}
 @staticmethod
 def preference_proposal(dataset,features):
  if len(dataset)<3:raise AtomicError('at least three pairwise comparisons required')
  return {'model_family':'Bradley-Terry logistic preference','features':features,'training_rows':len(dataset),'split':'grouped by ranking_id to prevent leakage','regularization':'L2','calibration_required':True,'assumption_checks':['one-dimensional utility may be inadequate','comparisons may be dependent','owner preference may drift'],'status':'proposal_not_trained','reference':RESEARCH['bradley_terry']}
 @staticmethod
 def evaluate_preference(predictions,min_accuracy=.6):
  if not predictions or any('probability' not in x or 'label' not in x for x in predictions):raise AtomicError('held-out probabilities and labels required')
  if any(not 0<=x['probability']<=1 or x['label'] not in (0,1) for x in predictions):raise AtomicError('invalid probability or label')
  acc=sum((x['probability']>=.5)==bool(x['label']) for x in predictions)/len(predictions);brier=sum((x['probability']-x['label'])**2 for x in predictions)/len(predictions);return {'held_out_count':len(predictions),'pairwise_accuracy':acc,'brier_score':brier,'activation_recommended':acc>=min_accuracy,'activated':False,'drift_monitor_required':True}
 def consent(self,tenant,scopes,retention_days,granted):
  allowed={'link_click','opportunity_application','draft_edit_duration'}
  if not granted or not scopes or not set(scopes)<=allowed:raise AtomicError('explicit opt-in and valid scopes required')
  if not 1<=retention_days<=365:raise AtomicError('retention_days must be 1..365')
  rec={'consent_id':_id(tenant,*sorted(scopes),_now()),'tenant_id':tenant,'scopes':sorted(set(scopes)),'retention_days':retention_days,'granted_at':_now(),'revoked_at':None,'data_minimization':True,'reference':RESEARCH['nist_privacy']};self.store.consents[tenant]=rec;return rec
 def revoke(self,tenant):
  if tenant not in self.store.consents:raise AtomicError('no consent')
  self.store.consents[tenant]['revoked_at']=_now();return {'revoked':True,'future_collection_blocked':True}
 def telemetry_event(self,tenant,event_type,data):
  consent=self.store.consents.get(tenant)
  if not consent or consent['revoked_at'] or event_type not in consent['scopes']:raise AtomicError('active scoped consent required')
  out={'id':_id(tenant,event_type,_now(),data.get('resource_id')),'tenant_id':tenant,'type':event_type,'at':_now(),'consent_id':consent['consent_id']}
  if event_type=='link_click':
   if not data.get('url') or not data.get('resource_id'):raise AtomicError('url and resource_id required')
   out.update({'url':data['url'],'resource_id':data['resource_id'],'page_title':data.get('page_title')})
  elif event_type=='opportunity_application':
   if data.get('status') not in ('started','submitted','withdrawn'):raise AtomicError('valid application status required')
   out.update({'opportunity_id':data.get('opportunity_id'),'status':data['status'],'submission_claim_verified':bool(data.get('provider_receipt')) if data['status']=='submitted' else None,'provider_receipt':data.get('provider_receipt')})
   if not out.get('opportunity_id'):raise AtomicError('opportunity_id required')
  else:
   seconds=data.get('active_seconds')
   if not isinstance(seconds,(int,float)) or not 0<=seconds<=86400:raise AtomicError('active_seconds must be 0..86400')
   out.update({'draft_id':data.get('draft_id'),'active_seconds':seconds,'idle_threshold_seconds':data.get('idle_threshold_seconds',60),'wall_clock_not_used':True})
   if not out.get('draft_id'):raise AtomicError('draft_id required')
  self.store.telemetry.append(out);return out
