"""Deterministic AI-system design and evaluation primitives for rows 1910-1959.

These methods evaluate caller-supplied model artifacts, traces, scores and policy
facts. They do not train opaque models, synthesize deceptive media, or execute
agent actions. Results retain evidence, assumptions, and explicit limitations.
"""
from __future__ import annotations
import math,re
NAMES=['large_language_models','multimodal_ai','vision_language_models','text_to_image_generation','text_to_video_generation','text_to_3d_generation','text_to_audio_generation','music_generation','voice_cloning','deepfakes','ai_art','ai_writing','ai_coding','ai_agents','autonomous_agents','multi_agent_systems','agent_communication','agent_coordination','agent_negotiation','agent_learning','reinforcement_learning_from_human_feedback','constitutional_ai','ai_alignment','ai_safety','ai_ethics','explainable_ai','interpretable_ai','fair_ai','responsible_ai','trustworthy_ai','ai_governance','ai_regulation','ai_policy','ai_standards','ai_auditing','ai_certification','ai_testing','ai_verification','ai_validation','ai_assurance','foundation_models','pre_trained_models','fine_tuning','transfer_learning','few_shot_learning','zero_shot_learning','in_context_learning','prompt_engineering','chain_of_thought','tree_of_thought']
ROWS={n:1910+i for i,n in enumerate(NAMES)}
SUMMARIES={n:n.replace('_',' ').title() for n in NAMES}
INPUTS={n:['documented caller-supplied artifacts, evidence, scores, or traces'] for n in NAMES}
def _f(x,n):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError(f'{n} must be finite')
 return float(x)
def _v(d,k,n=1):
 x=d.get(k)
 if not isinstance(x,list) or len(x)<n:raise ValueError(f'{k} needs at least {n} values')
 return [_f(v,k) for v in x]
def _aligned(*xs):
 if len({len(x) for x in xs})!=1:raise ValueError('aligned arrays required')
def _rate(xs):return sum(bool(x) for x in xs)/len(xs) if xs else None
def _tokens(s):return re.findall(r"[A-Za-z0-9']+",str(s).lower())
def _base(m,d,p):return {'method':m,'feature_row':ROWS[m],'inputs':{'data':d,'params':p},'assumptions':[],'method_limits':[]}
def run(method,data,params=None,seed=0):
 if method not in ROWS:raise ValueError(f'unsupported AI systems method {method}')
 p=params or {};o=_base(method,data,p);a=o['assumptions'];lim=o['method_limits'];out={}
 if method=='large_language_models':
  logp=_v(data,'token_log_probabilities');n=len(logp);loss=-sum(logp)/n;out={'token_count':n,'negative_log_likelihood':loss,'perplexity':math.exp(min(loss,700)),'context_utilization':n/_f(data.get('context_window',n),'context_window')};a+=['Token log probabilities use one tokenizer and evaluation corpus.']
 elif method=='multimodal_ai':
  mods=data.get('modalities');scores=_v(data,'modality_scores');weights=_v(data,'weights');
  if not isinstance(mods,list):raise ValueError('modalities required')
  _aligned(mods,scores,weights);z=sum(weights)
  if z<=0:raise ValueError('positive weight total required')
  out={'modalities':mods,'fused_score':sum(s*w for s,w in zip(scores,weights))/z,'weakest_modality':mods[min(range(len(scores)),key=scores.__getitem__)],'coverage':len(set(mods))}
 elif method=='vision_language_models':
  images=data.get('image_ids');captions=data.get('captions');similarities=_v(data,'similarities')
  if not isinstance(images,list) or not isinstance(captions,list):raise ValueError('image_ids and captions required')
  _aligned(images,captions,similarities);th=_f(p.get('threshold',.5),'threshold');out={'pair_count':len(images),'mean_alignment':sum(similarities)/len(similarities),'grounded_pairs':sum(s>=th for s in similarities),'grounding_rate':sum(s>=th for s in similarities)/len(similarities)}
 elif method in {'text_to_image_generation','text_to_video_generation','text_to_3d_generation','text_to_audio_generation','music_generation','ai_art'}:
  prompt=set(_tokens(data.get('prompt','')));artifact=set(_tokens(data.get('artifact_description','')));overlap=len(prompt&artifact)/len(prompt) if prompt else 0;quality=_v(data,'quality_scores');out={'prompt_adherence':overlap,'mean_quality':sum(quality)/len(quality),'minimum_quality':min(quality),'provenance_present':bool(data.get('provenance')),'watermark_present':bool(data.get('watermark'))};lim+=['Metadata/text evaluation cannot establish perceptual quality, copyright status, or real-world safety.']
 elif method in {'voice_cloning','deepfakes'}:
  consent=bool(data.get('consent_verified'));provenance=bool(data.get('provenance'));watermark=bool(data.get('watermark'));similarity=_f(data.get('identity_similarity',0),'identity_similarity');authorized=consent and provenance and watermark;out={'identity_similarity':similarity,'consent_verified':consent,'provenance_present':provenance,'watermark_present':watermark,'release_allowed':authorized,'risk_flags':[x for x,v in [('missing_consent',consent),('missing_provenance',provenance),('missing_watermark',watermark)] if not v]};lim+=['No media is generated; identity similarity never substitutes for consent.']
 elif method=='ai_writing':
  text=str(data.get('text',''));sources=data.get('sources',[]);claims=data.get('claims',[]);words=_tokens(text);sent=max(1,len(re.findall(r'[.!?]+',text)));out={'word_count':len(words),'sentence_count':sent,'average_words_per_sentence':len(words)/sent,'citation_coverage':min(1,len(sources)/len(claims)) if claims else 1,'duplicate_word_ratio':1-len(set(words))/len(words) if words else 0}
 elif method=='ai_coding':
  passed=_v(data,'tests_passed');total=_v(data,'tests_total');_aligned(passed,total)
  if any(t<0 or q<0 or q>t for q,t in zip(passed,total)):raise ValueError('invalid test counts')
  out={'suites':len(total),'tests_passed':sum(passed),'tests_total':sum(total),'pass_rate':sum(passed)/sum(total) if sum(total) else None,'static_analysis_issues':int(data.get('static_analysis_issues',0)),'dependency_scan_clean':bool(data.get('dependency_scan_clean',False))}
 elif method in {'ai_agents','autonomous_agents'}:
  steps=data.get('steps')
  if not isinstance(steps,list) or not steps:raise ValueError('steps required')
  approved=sum(bool(s.get('approved')) for s in steps if s.get('irreversible'));blocked=sum(bool(s.get('blocked')) for s in steps);out={'step_count':len(steps),'irreversible_steps':sum(bool(s.get('irreversible')) for s in steps),'approved_irreversible_steps':approved,'blocked_steps':blocked,'goal_completed':bool(data.get('goal_completed')),'safe_to_execute':all(not s.get('irreversible') or s.get('approved') for s in steps)};a+=['Step metadata truthfully marks irreversible effects and approval state.']
 elif method=='multi_agent_systems':
  agents=data.get('agents');edges=data.get('delegations')
  if not isinstance(agents,list) or not isinstance(edges,list):raise ValueError('agents and delegations required')
  known=set(agents);invalid=[e for e in edges if e.get('from') not in known or e.get('to') not in known];out={'agent_count':len(known),'delegation_count':len(edges),'invalid_delegations':invalid,'connected_agents':sorted({v for e in edges for v in (e.get('from'),e.get('to')) if v in known})}
 elif method=='agent_communication':
  msgs=data.get('messages')
  if not isinstance(msgs,list) or not msgs:raise ValueError('messages required')
  required={'sender','recipient','type','correlation_id'};valid=[required<=set(m) for m in msgs];out={'message_count':len(msgs),'schema_valid_rate':_rate(valid),'unmatched_replies':sum(m.get('type')=='reply' and not m.get('in_reply_to') for m in msgs),'correlation_ids':len({m.get('correlation_id') for m in msgs})}
 elif method=='agent_coordination':
  tasks=data.get('tasks')
  if not isinstance(tasks,list) or not tasks:raise ValueError('tasks required')
  owners=[t.get('owner') for t in tasks];deps={t.get('id'):set(t.get('depends_on',[])) for t in tasks};known=set(deps);out={'task_count':len(tasks),'unowned_tasks':sum(not x for x in owners),'unknown_dependencies':sorted({d for ds in deps.values() for d in ds if d not in known}),'ready_tasks':[i for i,ds in deps.items() if not ds]}
 elif method=='agent_negotiation':
  offers=data.get('offers');utilities=_v(data,'utilities')
  if not isinstance(offers,list):raise ValueError('offers required')
  _aligned(offers,utilities);reservation=_f(p.get('reservation_utility',0),'reservation');feasible=[(i,u) for i,u in enumerate(utilities) if u>=reservation];best=max(feasible,key=lambda z:z[1]) if feasible else None;out={'agreement_possible':best is not None,'selected_offer':offers[best[0]] if best else None,'selected_utility':best[1] if best else None,'concession_count':sum(utilities[i]<utilities[i-1] for i in range(1,len(utilities)))}
 elif method=='agent_learning':
  before=_v(data,'before_scores');after=_v(data,'after_scores');_aligned(before,after);gains=[b-a for a,b in zip(before,after)];out={'mean_gain':sum(gains)/len(gains),'improved_fraction':sum(x>0 for x in gains)/len(gains),'regressions':[i for i,x in enumerate(gains) if x<0]}
 elif method=='reinforcement_learning_from_human_feedback':
  chosen=_v(data,'chosen_rewards');rejected=_v(data,'rejected_rewards');_aligned(chosen,rejected);m=[a-b for a,b in zip(chosen,rejected)];out={'preference_accuracy':sum(x>0 for x in m)/len(m),'mean_reward_margin':sum(m)/len(m),'ties':sum(x==0 for x in m)};a+=['Reward scores are held-out and aligned to human preference pairs.']
 elif method=='constitutional_ai':
  principles=data.get('principles');critiques=data.get('critiques');revisions=data.get('revisions')
  if not all(isinstance(x,list) for x in (principles,critiques,revisions)):raise ValueError('principles, critiques, revisions required')
  out={'principle_count':len(principles),'critique_count':len(critiques),'revision_count':len(revisions),'coverage':min(1,len(critiques)/len(principles)) if principles else None,'revision_followthrough':min(1,len(revisions)/len(critiques)) if critiques else None}
 elif method=='ai_alignment':
  intended=_v(data,'intended_scores');observed=_v(data,'observed_scores');_aligned(intended,observed);err=[abs(a-b) for a,b in zip(intended,observed)];tol=_f(p.get('tolerance',.1),'tolerance');out={'mean_objective_gap':sum(err)/len(err),'within_tolerance_rate':sum(x<=tol for x in err)/len(err),'misaligned_cases':[i for i,x in enumerate(err) if x>tol]}
 elif method=='ai_safety':
  severity=_v(data,'hazard_severity');likelihood=_v(data,'hazard_likelihood');detect=_v(data,'detectability');_aligned(severity,likelihood,detect);risk=[s*l*d for s,l,d in zip(severity,likelihood,detect)];threshold=_f(p.get('threshold',1),'threshold');out={'risk_priority_numbers':risk,'total_risk':sum(risk),'unacceptable_hazards':[i for i,x in enumerate(risk) if x>threshold]}
 elif method=='ai_ethics':
  principles=data.get('principles');evidence=data.get('evidence')
  if not isinstance(principles,list) or not isinstance(evidence,dict):raise ValueError('principles and evidence required')
  covered=[x for x in principles if bool(evidence.get(x))];out={'principle_count':len(principles),'covered_principles':covered,'coverage':len(covered)/len(principles) if principles else None,'gaps':[x for x in principles if x not in covered]}
 elif method in {'explainable_ai','interpretable_ai'}:
  importance=_v(data,'feature_importance');names=data.get('feature_names')
  if not isinstance(names,list):raise ValueError('feature_names required')
  _aligned(importance,names);total=sum(abs(x) for x in importance);rank=sorted(zip(names,importance),key=lambda z:abs(z[1]),reverse=True);out={'ranked_features':[{'feature':n,'importance':v,'share':abs(v)/total if total else 0} for n,v in rank],'top_feature':rank[0][0],'sparsity':sum(x==0 for x in importance)/len(importance)};lim+=['Feature attribution describes this explanation method, not causality.']
 elif method=='fair_ai':
  groups=data.get('groups');selected=data.get('selected');positive=data.get('positive_labels')
  if not all(isinstance(x,list) for x in (groups,selected,positive)):raise ValueError('groups, selected, positive_labels required')
  _aligned(groups,selected,positive);stats={}
  for g in sorted(set(groups),key=str):
   ids=[i for i,x in enumerate(groups) if x==g];sel=sum(bool(selected[i]) for i in ids)/len(ids);pos=[i for i in ids if positive[i]];tpr=sum(bool(selected[i]) for i in pos)/len(pos) if pos else None;stats[str(g)]={'n':len(ids),'selection_rate':sel,'true_positive_rate':tpr}
  rates=[x['selection_rate'] for x in stats.values()];out={'group_metrics':stats,'demographic_parity_difference':max(rates)-min(rates),'selection_rate_ratio':min(rates)/max(rates) if max(rates)>0 else None}
 elif method in {'responsible_ai','trustworthy_ai'}:
  dims=data.get('dimensions');scores=_v(data,'scores');weights=_v(data,'weights')
  if not isinstance(dims,list):raise ValueError('dimensions required')
  _aligned(dims,scores,weights);z=sum(weights);out={'dimension_scores':dict(zip(dims,scores)),'weighted_score':sum(s*w for s,w in zip(scores,weights))/z,'weakest_dimension':dims[min(range(len(scores)),key=scores.__getitem__)],'all_thresholds_met':all(s>=_f(p.get('threshold',.7),'threshold') for s in scores)}
 elif method in {'ai_governance','ai_regulation','ai_policy','ai_standards','ai_certification'}:
  requirements=data.get('requirements');evidence=data.get('evidence')
  if not isinstance(requirements,list) or not isinstance(evidence,dict):raise ValueError('requirements and evidence required')
  met=[r for r in requirements if bool(evidence.get(r))];out={'requirements':len(requirements),'met':len(met),'compliance_rate':len(met)/len(requirements) if requirements else None,'met_requirements':met,'gaps':[r for r in requirements if r not in met],'decision':'ready_for_review' if len(met)==len(requirements) else 'evidence_incomplete'};lim+=['Checklist is not a legal opinion, regulator decision, or accredited certification.']
 elif method=='ai_auditing':
  controls=data.get('controls')
  if not isinstance(controls,list) or not controls:raise ValueError('controls required')
  exceptions=[c for c in controls if c.get('result')!='pass'];out={'controls_tested':len(controls),'passed':len(controls)-len(exceptions),'exceptions':exceptions,'pass_rate':1-len(exceptions)/len(controls),'evidence_complete':all(c.get('evidence') for c in controls)}
 elif method in {'ai_testing','ai_verification','ai_validation','ai_assurance'}:
  expected=data.get('expected');actual=data.get('actual')
  if not isinstance(expected,list) or not isinstance(actual,list):raise ValueError('expected and actual required')
  _aligned(expected,actual);matches=[a==b for a,b in zip(expected,actual)];critical=data.get('critical_indices',[]);out={'cases':len(matches),'passed':sum(matches),'pass_rate':_rate(matches),'failures':[i for i,x in enumerate(matches) if not x],'critical_failures':[i for i in critical if i<len(matches) and not matches[i]],'assurance_ready':all(matches) and bool(data.get('independent_evidence',False))}
 elif method in {'foundation_models','pre_trained_models'}:
  tasks=data.get('tasks');scores=_v(data,'scores');baseline=_v(data,'baselines')
  if not isinstance(tasks,list):raise ValueError('tasks required')
  _aligned(tasks,scores,baseline);out={'task_count':len(tasks),'task_scores':dict(zip(tasks,scores)),'mean_score':sum(scores)/len(scores),'mean_gain_over_baseline':sum(a-b for a,b in zip(scores,baseline))/len(scores),'tasks_below_baseline':[tasks[i] for i,(a,b) in enumerate(zip(scores,baseline)) if a<b]}
 elif method=='fine_tuning':
  before=_v(data,'before_scores');after=_v(data,'after_scores');_aligned(before,after);retained=_v(data,'retained_base_scores');_aligned(before,retained);out={'mean_task_gain':sum(b-a for a,b in zip(before,after))/len(before),'base_retention_ratio':sum(retained)/sum(before) if sum(before) else None,'regressed_tasks':[i for i,(a,b) in enumerate(zip(before,after)) if b<a]}
 elif method=='transfer_learning':
  scratch=_v(data,'scratch_scores');transfer=_v(data,'transfer_scores');scratch_n=_v(data,'scratch_examples');transfer_n=_v(data,'transfer_examples');_aligned(scratch,transfer,scratch_n,transfer_n);out={'mean_performance_gain':sum(t-s for s,t in zip(scratch,transfer))/len(scratch),'mean_sample_efficiency_ratio':sum(s/t for s,t in zip(scratch_n,transfer_n))/len(scratch_n),'positive_transfer_rate':sum(t>s for s,t in zip(scratch,transfer))/len(scratch)}
 elif method in {'few_shot_learning','zero_shot_learning','in_context_learning'}:
  predictions=data.get('predictions');targets=data.get('targets')
  if not isinstance(predictions,list) or not isinstance(targets,list):raise ValueError('predictions and targets required')
  _aligned(predictions,targets);shots=int(data.get('shots',0));expected=0 if method=='zero_shot_learning' else shots
  if method=='zero_shot_learning' and shots!=0:raise ValueError('zero-shot evaluation requires shots=0')
  out={'shots':shots,'accuracy':sum(a==b for a,b in zip(predictions,targets))/len(targets),'examples':len(targets),'expected_shot_regime':expected,'prompt_tokens':int(data.get('prompt_tokens',0))}
 elif method=='prompt_engineering':
  variants=data.get('variants');scores=_v(data,'scores');tokens=_v(data,'token_counts')
  if not isinstance(variants,list):raise ValueError('variants required')
  _aligned(variants,scores,tokens);penalty=_f(p.get('token_penalty',0),'token_penalty');utility=[s-penalty*t for s,t in zip(scores,tokens)];i=max(range(len(utility)),key=utility.__getitem__);out={'selected_variant':variants[i],'selected_index':i,'utilities':utility,'score':scores[i],'token_count':tokens[i]};a+=['Evaluation set is held out from prompt iteration.']
 elif method=='chain_of_thought':
  steps=data.get('steps');final=data.get('final_answer');expected=data.get('expected_answer')
  if not isinstance(steps,list) or not steps:raise ValueError('steps required')
  out={'step_count':len(steps),'all_steps_have_claims':all(bool(str(x).strip()) for x in steps),'final_correct':final==expected,'verified_steps':sum(bool(x) for x in data.get('step_verifications',[False]*len(steps))),'trace_exposed':bool(p.get('return_trace',False))};lim+=['Correct final answers do not prove hidden reasoning faithfulness; private reasoning need not be exposed.']
 elif method=='tree_of_thought':
  nodes=data.get('nodes')
  if not isinstance(nodes,list) or not nodes:raise ValueError('nodes required')
  by={n['id']:n for n in nodes if 'id' in n};valid=[n for n in nodes if n.get('parent') is None or n.get('parent') in by];leaves=[n for n in valid if not any(x.get('parent')==n.get('id') for x in valid)];best=max(leaves,key=lambda n:_f(n.get('score',0),'score'));out={'node_count':len(nodes),'valid_node_count':len(valid),'leaf_count':len(leaves),'best_leaf_id':best['id'],'best_score':best.get('score',0),'best_path':_path(best,by)}
 else:raise AssertionError(method)
 o['output']=out;return o
def _path(node,by):
 path=[];seen=set()
 while node and node.get('id') not in seen:
  seen.add(node.get('id'));path.append(node.get('id'));node=by.get(node.get('parent'))
 return list(reversed(path))
