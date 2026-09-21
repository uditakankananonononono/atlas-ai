"""Reviewable cognitive and learning designs for audit rows 860-909."""
from __future__ import annotations
import re,math
from typing import Any
ROWS=dict(enumerate('''Historical Thinking|Critical Thinking|Creative Thinking|Lateral Thinking|Divergent Thinking|Convergent Thinking|Associative Thinking|Reframing|Perspective Shifting|Paradigm Shifting|Concept Formation|Concept Mapping|Mind Mapping|Knowledge Organization|Taxonomy Creation|Ontology Development|Semantic Networks|Schema Development|Mental Model Construction|Model Updating|Belief Revision|Theory Change|Conceptual Change|Learning by Teaching|Learning by Doing|Learning by Observing|Learning by Imitating|Learning by Trial and Error|Learning by Insight|Learning by Association|Classical Conditioning|Operant Conditioning|Observational Learning|Social Learning|Vicarious Learning|Experiential Learning|Reflective Practice|Action Learning|Project-Based Learning|Problem-Based Learning|Inquiry-Based Learning|Discovery Learning|Guided Discovery|Direct Instruction|Explicit Instruction|Implicit Learning|Incidental Learning|Intentional Learning|Formal Learning|Informal Learning'''.split('|'),860))
class CognitiveLearningError(ValueError):pass
def slug(s):return re.sub('[^a-z0-9]+','_',s.lower()).strip('_')
KEYS={i:slug(n) for i,n in ROWS.items()}
STAGES={
860:['source','contextualize','corroborate','continuity_change','causal_claim'],861:['claim','evidence','assumptions','alternatives','judgment'],862:['prepare','incubate','ideate','elaborate','evaluate'],863:['dominant_pattern','provocation','random_entry','movement','candidate'],864:['prompt','fluency','flexibility','originality','defer_judgment'],865:['criteria','screen','compare','select_for_review'],866:['seed','retrieve_associations','remote_connection','explain_link'],867:['current_frame','alternative_frame','changed_implications'],868:['stakeholders','situated_perspectives','agreements','differences','unknowns'],869:['current_paradigm','anomalies','alternative_paradigm','predictions','transition_costs'],870:['examples','non_examples','attributes','rule','boundary_cases'],871:['concepts','typed_links','cross_links','propositions'],872:['central_topic','branches','subbranches','cross_links'],873:['items','facets','grouping_rules','retrieval_paths'],874:['scope','terms','hierarchy','definitions','polyhierarchy_review'],875:['scope','classes','relations','constraints','competency_questions'],876:['nodes','typed_edges','paths','unsupported_edges'],877:['prior_schema','new_information','assimilation','accommodation'],878:['purpose','entities','relationships','assumptions','predictions'],879:['prior_model','evidence','prediction_error','revised_model'],880:['prior_beliefs','evidence','reliability','conflicts','revised_confidence'],881:['current_theory','anomalies','rivals','comparative_fit','research_needed'],882:['initial_conception','elicitation','discrepant_evidence','reconstruction','transfer_check'],883:['topic','learner_explanation','audience_questions','knowledge_gaps','revision'],884:['objective','authentic_task','attempt','feedback','next_attempt'],885:['model','attention_cues','observations','inference_check'],886:['model','target_sequence','guided_rehearsal','fidelity_check','adaptation'],887:['goal','attempts','outcomes','error_pattern','next_experiment'],888:['impasse','representation','restructuring_prompt','insight','verification'],889:['cues','associations','strength','context','retrieval_test'],890:['neutral_stimulus','unconditioned_stimulus','pairings','conditioned_response','extinction_plan'],891:['target_behavior','antecedent','consequence','schedule','ethical_review'],892:['model','attention','retention','reproduction','motivation'],893:['community','participation','interaction','shared_artifacts','identity_safety'],894:['model_outcome','observer_inference','similarity_limits','direct_practice'],895:['concrete_experience','reflective_observation','abstract_conceptualization','active_experimentation'],896:['experience','description','feelings','evaluation','analysis','action_plan'],897:['real_problem','set_members','questions','action','reflection'],898:['driving_question','milestones','inquiry','critique_revision','public_product'],899:['ill_structured_problem','knowns','unknowns','self_directed_inquiry','solution','debrief'],900:['question','hypothesis','investigation','evidence','explanation','new_questions'],901:['environment','exploration','pattern','learner_rule','verification'],902:['target','exploration_space','hints','fading','transfer'],903:['objective','review','model','guided_practice','independent_practice','check'],904:['objective','explanation','think_aloud','guided_practice','feedback','independent_practice'],905:['exposure','patterns','performance_change','awareness_check','alternative_explanations'],906:['primary_activity','unplanned_learning','evidence','reflection','transfer'],907:['goal','strategy','practice','monitoring','evaluation'],908:['provider','curriculum','schedule','assessment','credential_boundary'],909:['setting','activity','community','self_direction','evidence_of_learning']}
FAMILY={**{i:'thinking' for i in range(860,870)},**{i:'knowledge_representation' for i in range(870,879)},**{i:'model_and_belief_change' for i in range(879,883)},**{i:'learning_mechanism' for i in range(883,896)},**{i:'practice_and_pedagogy' for i in range(896,910)}}
def _need(p,k):
 v=p.get(k)
 if v in (None,[],{}):raise CognitiveLearningError(f'{k} is required')
 return v
def _source(p):
 src=_need(p,'sources')
 if any(not s.get('source_id') or not s.get('observed_at') for s in src):raise CognitiveLearningError('each source requires source_id and observed_at')
 return src
def _typed_map(row,p,stages):
 supplied=p['inputs'];artifacts=[]
 for stage in stages:
  value=supplied.get(stage)
  artifacts.append({'stage':stage,'status':'supplied' if value not in (None,[],{}) else 'evidence_gap','content':value})
 return artifacts

def _number(value,name,lo=None,hi=None):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise CognitiveLearningError(f'{name} must be a finite number')
 value=float(value)
 if lo is not None and value<lo or hi is not None and value>hi:raise CognitiveLearningError(f'{name} must be in [{lo}, {hi}]')
 return value

def _score(inputs,key,default=.5):return _number(inputs.get(key,default),key,0,1)
def _items(inputs,key):
 value=_need(inputs,key)
 if not isinstance(value,list) or not value:raise CognitiveLearningError(f'{key} must be a non-empty list')
 return value

def _operation(row, x):
 """One transparent, deterministic cognitive/learning operation per ledger row."""
 if row==860:
  dated=sorted(_items(x,'events'),key=lambda e:e['year']);return {'chronology':[e['event'] for e in dated],'continuities':x.get('continuities',[]),'changes':x.get('changes',[])}
 if row==861:
  q=_score(x,'evidence_quality');a=_score(x,'assumption_risk');return {'argument_score':round(q*(1-a),4),'verdict':'supported' if q*(1-a)>=.6 else 'revise'}
 if row==862:return {'novelty_score':round(1-len(set(x.get('ideas',[])) & set(x.get('known_ideas',[])))/max(1,len(set(x.get('ideas',[])))),4),'ideas':list(dict.fromkeys(x.get('ideas',[])))}
 if row==863:return {'provocation':f"What if {x['dominant_pattern']} were reversed?",'indirect_candidate':x['candidate']}
 if row==864:
  ideas=list(dict.fromkeys(_items(x,'ideas')));cats={i.get('category') for i in ideas if isinstance(i,dict)};return {'fluency':len(ideas),'flexibility':len(cats),'ideas':ideas}
 if row==865:
  opts=_items(x,'options');w=x.get('weights',{});rank=sorted(({'option':o['name'],'score':round(sum(_number(o['scores'][k],k,0,1)*_number(v,k,0,1) for k,v in w.items()),4)} for o in opts),key=lambda z:z['score'],reverse=True);return {'ranking':rank,'selected':rank[0]['option']}
 if row==866:return {'association_path':[x['seed'],*x.get('bridges',[]),x['target']],'remote_distance':len(x.get('bridges',[]))+1}
 if row==867:return {'old_frame':x['current_frame'],'new_frame':x['alternative_frame'],'implication_delta':list(set(x.get('new_implications',[]))-set(x.get('old_implications',[])))}
 if row==868:return {'perspectives':[{'stakeholder':p['stakeholder'],'priority':p['priority']} for p in _items(x,'perspectives')],'unresolved':x.get('unknowns',[])}
 if row==869:return {'anomaly_coverage':round(len(set(x.get('explained_anomalies',[])) & set(x.get('anomalies',[])))/max(1,len(x.get('anomalies',[]))),4),'transition_cost':_score(x,'transition_cost')}
 if row==870:
  examples=_items(x,'examples');attrs=set(examples[0]['attributes']);[attrs.intersection_update(e['attributes']) for e in examples[1:]];return {'defining_attributes':sorted(attrs),'category_rule':' AND '.join(sorted(attrs))}
 if row==871:return {'nodes':sorted(set(x.get('concepts',[]))),'edges':x.get('typed_links',[]),'cross_link_count':sum(e.get('cross_link',False) for e in x.get('typed_links',[]))}
 if row==872:return {'root':x['central_topic'],'branches':x.get('branches',[]),'radial_depth':max([b.get('depth',1) for b in x.get('branches',[])],default=0)}
 if row==873:return {'groups':x.get('groups',{}),'retrieval_index':{item:g for g,items in x.get('groups',{}).items() for item in items}}
 if row==874:return {'parent_by_term':{e['term']:e.get('parent') for e in x.get('terms',[])},'roots':[e['term'] for e in x.get('terms',[]) if not e.get('parent')]}
 if row==875:return {'classes':x.get('classes',[]),'relations':x.get('relations',[]),'constraint_violations':[c for c in x.get('constraints',[]) if not c.get('satisfied')]}
 if row==876:return {'adjacency':{n:[e['to'] for e in x.get('typed_edges',[]) if e['from']==n] for n in x.get('nodes',[])},'edge_types':sorted({e['type'] for e in x.get('typed_edges',[])})}
 if row==877:return {'assimilated':x.get('compatible_information',[]),'accommodated':x.get('schema_changes',[]),'schema_version':int(x.get('prior_version',0))+1}
 if row==878:return {'entities':x.get('entities',[]),'predictions':x.get('predictions',[]),'assumptions_to_test':x.get('assumptions',[])}
 if row==879:
  predicted=_number(x['predicted'],'predicted');observed=_number(x['observed'],'observed');rate=_number(x.get('learning_rate',.5),'learning_rate',0,1);err=observed-predicted;return {'prediction_error':err,'revised_estimate':predicted+rate*err,'transition':'prior_model->evidence_checked->revised_model'}
 if row==880:
  prior=_score(x,'prior_confidence');reliability=_score(x,'evidence_reliability');support=_number(x.get('evidence_direction',1),'evidence_direction',-1,1);posterior=max(0,min(1,prior+reliability*support*(1-prior if support>=0 else prior)));return {'prior_confidence':prior,'revised_confidence':round(posterior,4),'revision':posterior-prior}
 if row==881:return {'comparative_fit':{t:round(sum(map(float,s))/len(s),4) for t,s in x.get('theory_scores',{}).items()},'preferred_theory':max(x.get('theory_scores',{}),key=lambda t:sum(x['theory_scores'][t]))}
 if row==882:return {'initial_conception':x['initial_conception'],'reconstructed_conception':x['reconstructed_conception'],'transfer_accuracy':_score(x,'transfer_accuracy')}
 if row==883:return {'explanation_gaps':x.get('audience_questions',[]),'teach_back_revision':x.get('revised_explanation'),'comprehension_gain':_score(x,'post_score')-_score(x,'pre_score')}
 if row==884:return {'attempt_delta':_score(x,'later_score')-_score(x,'first_score'),'next_task':x.get('next_attempt')}
 if row==885:return {'observed_steps':x.get('observations',[]),'inference_confidence':_score(x,'inference_confidence'),'check_required':_score(x,'inference_confidence')<.8}
 if row==886:return {'fidelity':_score(x,'matched_steps'),'adaptations':x.get('adaptations',[]),'sequence':x.get('target_sequence',[])}
 if row==887:
  attempts=_items(x,'attempts');best=max(attempts,key=lambda a:a['score']);return {'best_attempt':best['id'],'error_reduction':attempts[-1]['score']-attempts[0]['score'],'next_experiment':x.get('next_experiment')}
 if row==888:return {'impasse_restructured_as':x.get('new_representation'),'insight':x.get('insight'),'verified':bool(x.get('verification'))}
 if row==889:
  old=_score(x,'association_strength');rate=_number(x.get('learning_rate',.2),'learning_rate',0,1);outcome=_number(x.get('outcome',1),'outcome',0,1);return {'prior_strength':old,'updated_strength':round(old+rate*(outcome-old),4),'prediction_error':outcome-old}
 if row==890:
  strength=_score(x,'strength');rate=_number(x.get('learning_rate',.2),'learning_rate',0,1);us=_number(x.get('unconditioned_response',1),'unconditioned_response',0,1);return {'conditioned_strength':round(strength+rate*(us-strength),4),'prediction_error':us-strength,'transition':'neutral->paired->conditioned'}
 if row==891:
  q=_score(x,'behavior_probability');reward=_number(x.get('consequence',1),'consequence',-1,1);alpha=_number(x.get('learning_rate',.2),'learning_rate',0,1);return {'prior_probability':q,'updated_probability':max(0,min(1,q+alpha*reward*(1-q if reward>=0 else q))),'schedule':x.get('schedule')}
 if row==892:return {'attention':_score(x,'attention'),'retention':_score(x,'retention'),'reproduction_readiness':round(_score(x,'attention')*_score(x,'retention')*_score(x,'motivation'),4)}
 if row==893:return {'participation_change':_score(x,'later_participation')-_score(x,'initial_participation'),'shared_artifacts':x.get('shared_artifacts',[]),'identity_safety':_score(x,'identity_safety')}
 if row==894:return {'vicarious_value':round(_score(x,'model_outcome')*_score(x,'observer_similarity'),4),'similarity_limits':x.get('similarity_limits',[]),'direct_practice_needed':True}
 if row==895:return {'cycle':['concrete_experience','reflective_observation','abstract_conceptualization','active_experimentation'],'next_experiment':x.get('active_experimentation')}
 if row==896:return {'lesson':x.get('analysis'),'action_plan':x.get('action_plan'),'reflection_depth':len(x.get('evidence_considered',[]))}
 if row==897:return {'problem':x.get('real_problem'),'question_count':len(x.get('questions',[])),'action':x.get('action'),'reflection':x.get('reflection')}
 if row==898:return {'milestone_progress':round(sum(bool(m.get('done')) for m in x.get('milestones',[]))/max(1,len(x.get('milestones',[]))),4),'revision_count':int(x.get('revision_count',0)),'product':x.get('public_product')}
 if row==899:return {'knowns':x.get('knowns',[]),'learning_issues':x.get('unknowns',[]),'solution_score':_score(x,'solution_score'),'debrief':x.get('debrief')}
 if row==900:return {'hypothesis':x.get('hypothesis'),'evidence_balance':sum(_number(e['weight'],'weight',-1,1) for e in x.get('evidence',[])),'new_questions':x.get('new_questions',[])}
 if row==901:return {'discovered_rule':x.get('learner_rule'),'verification_score':_score(x,'verification_score'),'exploration_count':len(x.get('explorations',[]))}
 if row==902:return {'hint_level':int(_number(x.get('hint_level',1),'hint_level',0,5)),'faded_to':int(_number(x.get('faded_to',0),'faded_to',0,5)),'transfer_score':_score(x,'transfer_score')}
 if row==903:return {'instruction_sequence':['review','model','guided_practice','independent_practice','check'],'mastery':_score(x,'check_score'),'reteach':_score(x,'check_score')<.8}
 if row==904:return {'clarity_check':_score(x,'clarity_score'),'guided_accuracy':_score(x,'guided_accuracy'),'independent_accuracy':_score(x,'independent_accuracy'),'feedback':x.get('feedback')}
 if row==905:return {'performance_change':_score(x,'post_exposure')-_score(x,'pre_exposure'),'awareness':_score(x,'awareness'),'implicit_evidence':_score(x,'awareness')<.5}
 if row==906:return {'incidental_gain':_score(x,'post_score')-_score(x,'pre_score'),'unplanned_learning':x.get('unplanned_learning'),'transfer':x.get('transfer')}
 if row==907:return {'goal_progress':_score(x,'current_score')-_score(x,'baseline_score'),'strategy':x.get('strategy'),'monitoring_points':x.get('monitoring',[])}
 if row==908:return {'curriculum_progress':round(sum(bool(u.get('complete')) for u in x.get('units',[]))/max(1,len(x.get('units',[]))),4),'assessment_score':_score(x,'assessment_score'),'credential_awarded':False}
 if row==909:return {'daily_learning_evidence':x.get('evidence_of_learning',[]),'self_direction':_score(x,'self_direction'),'community':x.get('community')}
 raise CognitiveLearningError('unsupported capability')

def execute(row:int,payload:dict[str,Any])->dict[str,Any]:
 if row not in ROWS:raise CognitiveLearningError('unsupported capability')
 tenant=_need(payload,'tenant_id');actor=_need(payload,'actor_id')
 refs=payload.get('references',[])
 if any(r.get('tenant_id')!=tenant or r.get('actor_id') not in (None,actor) for r in refs):raise CognitiveLearningError('cross-tenant or cross-actor reference denied')
 sources=_source(payload);inputs=_need(payload,'inputs')
 if not isinstance(inputs,dict):raise CognitiveLearningError('inputs must be an object')
 stages=STAGES[row];artifacts=_typed_map(row,payload,stages)
 if row==860 and not any(s.get('kind') in ('primary','secondary') for s in sources):raise CognitiveLearningError('historical thinking requires source kind primary or secondary')
 if row in (871,875,876):
  edges=inputs[{871:'typed_links',875:'relations',876:'typed_edges'}[row]]
  if edges and any(not e.get('type') for e in edges):raise CognitiveLearningError('knowledge edges require relation type')
 if row in (890,891) and not payload.get('ethical_review',False):raise CognitiveLearningError('conditioning design requires ethical_review=true')
 if row==908 and inputs.get('credential_boundary') is True:raise CognitiveLearningError('credential_boundary must describe limits, not claim a credential')
 result=_operation(row,inputs);gaps=[x['stage'] for x in artifacts if x['status']=='evidence_gap']
 return {'row_id':row,'capability':ROWS[row],'key':KEYS[row],'family':FAMILY[row],'scope':{'tenant_id':tenant,'actor_id':actor},'mechanism':KEYS[row],'result':result,'workflow':artifacts,'complete':not gaps,'evidence_gaps':gaps,'sources':sources,'learner_agency':{'opt_out':payload.get('opt_out',True),'goals':payload.get('learner_goals',[]),'access_needs':payload.get('access_needs',[])},'assessment':{'criteria':payload.get('criteria',[]),'results':payload.get('results',[]),'grade_or_credential_awarded':False},'status':'draft_for_learner_and_educator_review','actions_taken':[],'boundary':'Learning support only. No hidden-state inference, credentials, enrollment, external effects, or education-record changes.'}
def capabilities():return [{'row_id':i,'key':KEYS[i],'name':ROWS[i],'family':FAMILY[i],'stages':STAGES[i]} for i in ROWS]
