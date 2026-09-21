"""Atomic concepts at ledger positions 47-69: consented learning and self-improvement proposals.

References researched before design: embeddings/retrieval guidance, InstructGPT's
ranked-feedback reward-model method, privacy opt-out/deletion practice, and empirical
challenge-skill balance measurement. No model training or behavior mutation occurs here.
"""
from __future__ import annotations
import hashlib,math
from collections import defaultdict
from datetime import datetime,timedelta
from typing import Any
ROWS={'7.5':'scope_limited_local_telemetry','7.6':'revealed_preference_scoring','7.7':'telemetry_revocation_deletion','8.1':'writing_sample_embedding','8.2':'decision_embedding','8.3':'correction_embedding','8.4':'unified_vector_index','8.5':'query_personalization_memory','8.6':'preference_aware_default','9.1':'weekly_review_schedule','9.2':'completed_action_review_list','9.3':'good_bad_unclear_labels','9.4':'review_notes_training_signals','9.5':'small_reward_model_proposal','9.6':'alignment_trend_evaluation','10.1':'own_performance_metric_analysis','10.2':'reviewed_prompt_rewrite_proposal','10.3':'reviewed_algorithm_change_proposal','11.1':'cross_domain_pattern_extraction','11.2':'unrelated_domain_pattern_transfer','13.1':'knowledge_boundary_estimation','13.2':'uncertainty_flag_before_claim','17.1':'challenge_skill_balance'}
SOURCES={'embeddings':'https://developers.openai.com/api/docs/guides/embeddings','retrieval':'https://developers.openai.com/api/docs/guides/retrieval','reward':'https://arxiv.org/abs/2203.02155','privacy':'https://www.ftc.gov/system/files/documents/public_events/1548288/privacycon-2020-hana_habib.pdf','flow':'https://www.nrpa.org/globalassets/journals/jlr/1998/volume-30/jlr-volume-30-number-3-pp-380-389.pdf'}
class AtomicError(ValueError):pass
def need(d,k,t=None):
 v=d.get(k)
 if v is None or v=='' or (t and not isinstance(v,t)) or (isinstance(v,(list,dict)) and not v):raise AtomicError(f'{k} is required')
 return v
def cos(a,b):
 if not a or len(a)!=len(b):raise AtomicError('embedding dimensions must match and be nonempty')
 z=math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b));return sum(x*y for x,y in zip(a,b))/z if z else 0
def run(row:str,d:dict[str,Any])->dict[str,Any]:
 if row not in ROWS:raise AtomicError('unknown atomic row')
 if row=='7.5':
  scope=need(d,'consent_scope',dict);events=need(d,'events',list);allowed=set(scope.get('event_types',[]));fields=set(scope.get('fields',[]));clean=[]
  for e in events:
   if e.get('type') in allowed:clean.append({'event_id':e.get('event_id'),'type':e['type'],'occurred_at':e.get('occurred_at'),'data':{k:v for k,v in e.get('data',{}).items() if k in fields}})
  r={'collector':'local_only','consent_id':scope.get('consent_id'),'accepted_events':clean,'dropped_count':len(events)-len(clean),'raw_text_forbidden':True,'network_export':False,'source':SOURCES['privacy']}
 elif row=='7.6':
  events=need(d,'consented_events',list);weights=d.get('weights',{'chosen':1,'completed':1,'undone':-1,'dismissed':-.5});scores=defaultdict(float);evidence=defaultdict(list)
  for e in events:
   option=e.get('option_id');kind=e.get('event_type')
   if option and kind in weights:scores[option]+=float(weights[kind]);evidence[option].append(e.get('event_id'))
  r={'scores':[{'option_id':k,'score':v,'event_ids':evidence[k],'interpretation':'revealed signal, not stable preference'} for k,v in sorted(scores.items())],'weights':weights,'consent_required':True,'no_inference_from_non_events':True}
 elif row=='7.7':
  records=need(d,'records',list);subject=need(d,'subject_id',str);action=need(d,'action',str)
  if action not in {'revoke_collection','delete_subject_data'}:raise AtomicError('unsupported privacy action')
  affected=[x.get('record_id') for x in records if x.get('subject_id')==subject];r={'action':action,'affected_record_ids':affected,'future_collection_allowed':False,'deletion_plan':{'primary':affected,'derived_embeddings':d.get('derived_embedding_ids',[]),'indexes':d.get('index_entry_ids',[]),'backups':'expire under documented retention policy'},'executed':False,'source':SOURCES['privacy']}
 elif row in {'8.1','8.2','8.3'}:
  text=need(d,'text',str);vector=need(d,'embedding',list)
  if any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in vector):raise AtomicError('embedding must contain finite numbers')
  kind={'8.1':'writing_sample','8.2':'decision','8.3':'correction'}[row];r={'entry_id':hashlib.sha256((kind+'|'+text).encode()).hexdigest()[:24],'kind':kind,'text_hash':hashlib.sha256(text.encode()).hexdigest(),'vector':vector,'dimensions':len(vector),'metadata':d.get('metadata',{}),'model':d.get('model'),'raw_text_storage':bool(d.get('store_raw_text',False)),'source':SOURCES['embeddings']}
 elif row=='8.4':
  entries=need(d,'entries',list);dims={len(x.get('vector',[])) for x in entries}
  if len(dims)!=1 or 0 in dims:raise AtomicError('all vectors need one nonzero dimension')
  ids=[x.get('id') for x in entries]
  if None in ids or len(ids)!=len(set(ids)):raise AtomicError('entry ids must be unique')
  r={'index_manifest':{'count':len(entries),'dimensions':next(iter(dims)),'kinds':sorted(set(x.get('kind') for x in entries)),'model_versions':sorted(set(x.get('model') for x in entries))},'entries':entries,'tenant_partition_required':True,'index_built':False,'source':SOURCES['retrieval']}
 elif row=='8.5':
  q=need(d,'query_vector',list);entries=need(d,'entries',list);k=int(d.get('k',5));hits=sorted([{'id':x['id'],'kind':x.get('kind'),'score':cos(q,x['vector']),'metadata':x.get('metadata',{})} for x in entries],key=lambda x:x['score'],reverse=True)[:k];r={'query_results':hits,'minimum_score':d.get('minimum_score',.75),'usable_memory':[x for x in hits if x['score']>=float(d.get('minimum_score',.75))],'retrieval_before_action':True,'retrieval_does_not_authorize_action':True,'source':SOURCES['retrieval']}
 elif row=='8.6':
  opts=need(d,'options',list);signals=need(d,'preference_signals',list);scores=[]
  for o in opts:
   matched=[s for s in signals if s.get('attribute') in o.get('attributes',{}) and o['attributes'][s['attribute']]==s.get('preferred_value')];scores.append({'option_id':o['id'],'score':sum(float(x.get('confidence',0)) for x in matched),'signal_ids':[x.get('id') for x in matched]})
  scores.sort(key=lambda x:x['score'],reverse=True);margin=scores[0]['score']-(scores[1]['score'] if len(scores)>1 else 0);threshold=float(d.get('confidence_margin',.5));r={'ranked':scores,'default_option_id':scores[0]['option_id'] if margin>=threshold else None,'uncertain':margin<threshold,'ask_user':margin<threshold,'no_external_effect':True}
 elif row=='9.1':
  start=datetime.fromisoformat(need(d,'start_at',str));weeks=int(d.get('weeks',8));
  if weeks<1 or weeks>52:raise AtomicError('weeks must be 1-52')
  r={'occurrences':[(start+timedelta(days=7*i)).isoformat() for i in range(weeks)],'timezone':d.get('timezone'),'duration_minutes':int(d.get('duration_minutes',20)),'schedule_created':False}
 elif row=='9.2':
  acts=need(d,'actions',list);r={'review_items':[{'action_id':x.get('id'),'completed_at':x.get('completed_at'),'goal':x.get('goal'),'outcome':x.get('outcome'),'evidence':x.get('evidence'),'reviewable':bool(x.get('completed_at') and x.get('outcome'))} for x in acts],'only_completed':True}
 elif row=='9.3':
  labels=need(d,'labels',list);allowed={'good','bad','unclear'}
  if any(x.get('label') not in allowed for x in labels):raise AtomicError('label must be good, bad, or unclear')
  r={'labels':labels,'ordinal_scale_forbidden':True,'unclear_preserved_not_forced':True}
 elif row=='9.4':
  reviews=need(d,'reviews',list);signals=[]
  for x in reviews:
   if x.get('label') not in {'good','bad','unclear'} or not x.get('note'):raise AtomicError('each review needs valid label and note')
   signals.append({'action_id':x.get('action_id'),'target':1 if x['label']=='good' else 0 if x['label']=='bad' else None,'note':x['note'],'eligible_for_pairwise_training':x['label']!='unclear'})
  r={'training_signals':signals,'unclear_excluded_from_binary_target':True,'owner_review_is_authoritative_for_this_dataset_only':True}
 elif row=='9.5':
  pairs=need(d,'preference_pairs',list)
  if len(pairs)<2:raise AtomicError('at least two preference pairs required')
  bad=[x for x in pairs if not x.get('chosen_id') or not x.get('rejected_id') or x['chosen_id']==x['rejected_id']]
  if bad:raise AtomicError('valid chosen/rejected pairs required')
  r={'proposal':{'objective':'pairwise preference ranking','train_count':math.floor(len(pairs)*.8),'holdout_count':len(pairs)-math.floor(len(pairs)*.8),'features':d.get('features',[]),'baseline':d.get('baseline'),'metrics':['pairwise accuracy','calibration','slice accuracy'],'overfitting_controls':['held-out evaluation','regularization','small-model capacity','owner review']},'training_executed':False,'behavior_changed':False,'source':SOURCES['reward']}
 elif row=='9.6':
  points=need(d,'evaluations',list);pts=sorted(points,key=lambda x:x['at']);vals=[float(x['alignment_score']) for x in pts]
  if any(not 0<=x<=1 for x in vals):raise AtomicError('alignment_score must be [0,1]')
  n=len(vals);slope=0 if n<2 else (vals[-1]-vals[0])/(n-1);r={'series':pts,'mean':sum(vals)/n,'trend_per_evaluation':slope,'direction':'improving' if slope>.01 else 'declining' if slope<-.01 else 'flat','sample_count':n,'causality_not_inferred':True}
 elif row=='10.1':
  ms=need(d,'metrics',list);out=[]
  for m in ms:
   vals=[float(x) for x in m.get('values',[])]
   if not vals:raise AtomicError('each metric needs values')
   out.append({'name':m['name'],'latest':vals[-1],'mean':sum(vals)/len(vals),'change':vals[-1]-vals[0],'target':m.get('target'),'unit':m.get('unit')})
  r={'metrics':out,'measurement_window':d.get('measurement_window'),'self_report_not_ground_truth':True}
 elif row in {'10.2','10.3'}:
  current=need(d,'current',str);proposal=need(d,'proposal',str);evidence=need(d,'evidence',list);tests=need(d,'evaluation_plan',list)
  r={'change_type':'prompt' if row=='10.2' else 'algorithm','current_hash':hashlib.sha256(current.encode()).hexdigest(),'proposal':proposal,'rationale':d.get('rationale'),'evidence':evidence,'evaluation_plan':tests,'risk_assessment':d.get('risk_assessment',[]),'rollback':d.get('rollback'),'review_state':'awaiting_exact_review','applied':False,'self_modification_forbidden_without_review':True}
 elif row=='11.1':
  cases=need(d,'cases',list)
  if len({x.get('domain') for x in cases})<2:raise AtomicError('cases from at least two domains required')
  shared=set(cases[0].get('relations',[]))
  for x in cases[1:]:shared&=set(x.get('relations',[]))
  r={'domains':[x.get('domain') for x in cases],'abstract_pattern':{'shared_relations':sorted(shared),'roles':d.get('roles',[]),'boundary_conditions':d.get('boundary_conditions',[])},'pattern_strength':'candidate' if shared else 'unsupported','surface_terms_removed':True}
 elif row=='11.2':
  pat=need(d,'pattern',dict);target=need(d,'target_domain',dict);mapping=need(d,'mapping',list);required=set(pat.get('roles',[]));mapped={x.get('pattern_role') for x in mapping};r={'target_domain':target.get('name'),'mapping':mapping,'unmapped_roles':sorted(required-mapped),'candidate_prediction':d.get('candidate_prediction'),'falsification_test':d.get('falsification_test'),'transfer_validated':False,'ready_for_test':required<=mapped and bool(d.get('falsification_test'))}
 elif row=='13.1':
  claims=need(d,'claims',list);rows=[]
  for x in claims:
   evidence=float(x.get('evidence_coverage',0));fresh=float(x.get('freshness',0));agreement=float(x.get('source_agreement',0));score=max(0,min(1,.5*evidence+.25*fresh+.25*agreement));rows.append({'claim_id':x.get('id'),'knowledge_score':score,'boundary':'known' if score>=.8 else 'partial' if score>=.5 else 'unknown','missing':x.get('missing',[])})
  r={'boundaries':rows,'thresholds':{'known':.8,'partial':.5},'knowledge_score_is_heuristic':True}
 elif row=='13.2':
  claim=need(d,'claim',str);b=need(d,'boundary',dict);score=float(b.get('knowledge_score',0));threshold=float(d.get('claim_threshold',.8));r={'claim':claim,'flagged':score<threshold,'knowledge_score':score,'threshold':threshold,'required_language':'uncertain / needs verification' if score<threshold else 'supported by current evidence','block_action_driving_claim':score<threshold and bool(d.get('action_driving'))}
 else:
  challenge=float(need(d,'challenge'));skill=float(need(d,'skill'))
  if not 0<=challenge<=10 or not 0<=skill<=10:raise AtomicError('challenge and skill must be [0,10]')
  gap=challenge-skill;state='flow_candidate' if abs(gap)<=1 and min(challenge,skill)>=4 else 'anxiety_risk' if gap>1 else 'boredom_risk' if gap<-1 else 'low_activation';r={'challenge':challenge,'skill':skill,'gap':gap,'state':state,'adjustment':'reduce challenge or add scaffolding' if gap>1 else 'increase challenge' if gap<-1 else 'preserve conditions','self_report_required':True,'not_a_diagnosis':True,'source':SOURCES['flow']}
 return {'atomic_row_id':row,'concept':ROWS[row],'result':r,'effects_performed':[],'boundary':'Analysis/proposal only. No collection beyond supplied consented records, no model training, no self-modification, and no schedule/deletion mutation is claimed.'}
