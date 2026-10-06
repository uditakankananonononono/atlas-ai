"""Auditable learning-strategy and reasoning workbench (ledger 810-859)."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from math import exp,log
import re
from typing import Any
from .learning_calibration import calibrate_attempts
from .spaced_review import schedule_reviews
from .support_progression import progress_support
from .keyed_assessment import assess
from .progress_measurement import measure_progress
from .measured_learning import recall_practice, deliberate_practice
from .defeasible_reasoning import default_inference, abductive_search
from .formal_reasoning import argument_validity, causal_effect, counterfactual
class LearningReasoningError(ValueError):pass
ROWS={810:'Spaced Repetition',811:'Interleaving',812:'Retrieval Practice',813:'Elaborative Interrogation',814:'Self-Explanation',815:'Dual Coding',816:'Concrete Examples',817:'Worked Examples',818:'Problem Solving',819:'Deliberate Practice',820:'Chunking',821:'Scaffolding',822:'Fading',823:'Metacognition',824:'Self-Regulated Learning',825:'Goal Setting',826:'Progress Monitoring',827:'Self-Assessment',828:'Peer Assessment',829:'Formative Assessment',830:'Summative Assessment',831:'Diagnostic Assessment',832:'Prior Knowledge Activation',833:'Transfer',834:'Near Transfer',835:'Far Transfer',836:'Analogical Reasoning',837:'Case-Based Reasoning',838:'Rule-Based Reasoning',839:'Model-Based Reasoning',840:'Qualitative Reasoning',841:'Quantitative Reasoning',842:'Spatial Reasoning',843:'Temporal Reasoning',844:'Causal Reasoning',845:'Counterfactual Reasoning',846:'Probabilistic Reasoning',847:'Fuzzy Logic',848:'Default Reasoning',849:'Non-Monotonic Reasoning',850:'Abductive Reasoning',851:'Inductive Reasoning',852:'Deductive Reasoning',853:'Transductive Reasoning',854:'Dialectical Reasoning',855:'Integrative Thinking',856:'Systems Thinking',857:'Design Thinking',858:'Computational Thinking',859:'Scientific Thinking'}
def slug(x):return re.sub(r'[^a-z0-9]+','_',x.lower()).strip('_')
KEYS={slug(v):k for k,v in ROWS.items()}
FAMILY={**{i:'learning' for i in range(810,833)},**{i:'transfer' for i in range(833,838)},**{i:'reasoning' for i in range(838,856)},**{i:'inquiry' for i in range(856,860)}}
def capabilities():return [{'row_id':i,'key':slug(n),'name':n,'family':FAMILY[i]} for i,n in ROWS.items()]
def req(p,k,t):
 v=p.get(k)
 if not isinstance(v,t) or (t in (str,list,dict) and not v):raise LearningReasoningError(f'{k} must be a non-empty {t.__name__}')
 return v
def src(p):
 s=req(p,'source',dict)
 if not s.get('title') or not isinstance(s.get('url'),str) or not s['url'].startswith(('http://','https://')):raise LearningReasoningError('source needs title and http(s) url')
 return {'title':s['title'],'url':s['url']}
def learning(row,p):
 objective=req(p,'objective',str);out={'objective':objective,'learner_control':True,'feedback_is_actionable':True}
 if row==810:
  try:out.update(schedule_reviews(p))
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==811:
  skills=req(p,'skills',list);blocks=int(p.get('blocks',len(skills)*2));out['sequence']=[skills[(i+(i//len(skills)))%len(skills)] for i in range(blocks)];out['avoids_same_skill_runs']=len(set(skills))>1
 if row==812:
  try:out['recall']=recall_practice(p)
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==813:out['prompts']=[f'Why is {x} true, and under what conditions?' for x in p.get('claims',[objective])]
 if row==814:out['self_explanation_prompts']=['What principle applies?','Why is this step valid?','How does it connect to the goal?','What remains uncertain?']
 if row==815:out['representations']={'verbal':p.get('verbal'),'visual':p.get('visual'),'mapping_required':True,'decorative_visuals_rejected':True}
 if row==816:out['examples']=[{'example':x,'feature_to_notice':x.get('feature') if isinstance(x,dict) else None,'boundary_case':bool(x.get('boundary_case')) if isinstance(x,dict) else False} for x in req(p,'examples',list)]
 if row==817:out['worked_example']={'problem':p.get('problem'),'steps':p.get('steps',[]),'rationales':p.get('rationales',[]),'self_explanation_at_each_step':True,'completion_problem_next':True}
 if row==818:out['problem_cycle']=['represent problem','identify constraints','generate strategies','execute','verify','reflect']
 if row==819:
  try:out['practice_plan']=deliberate_practice(p)
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==820:out['chunks']=[{'label':c.get('label'),'elements':c.get('elements',[]),'organizing_principle':c.get('principle')} for c in req(p,'chunks',list)]
 if row in (821,822):
  try:out.update(progress_support(p))
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==823:
  try:out['calibration']=calibrate_attempts(req(p,'attempts',list))
  except ValueError as exc:raise LearningReasoningError(str(exc)) from exc
  out['calibration_required']=True
  out['scope']='Measured strategy calibration, not full metacognition'
 if row==824:out['srl_cycle']=['forethought','performance monitoring','self-reflection'];out['choice_of_strategy']=p.get('strategy')
 if row==825:
  goal=req(p,'goal',dict);out['goal']={'specific':goal.get('specific'),'metric':goal.get('metric'),'target':goal.get('target'),'deadline':goal.get('deadline'),'feasibility_evidence':goal.get('feasibility_evidence'),'implementation_intention':goal.get('if_then')}
 if row==826:
  try:out['progress']=measure_progress(p)
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (827,828):
  criteria=req(p,'criteria',list);ratings=req(p,'ratings',dict);out['assessment']=[{'criterion':c,'rating':ratings.get(c),'evidence':p.get('evidence',{}).get(c),'missing_evidence':not bool(p.get('evidence',{}).get(c))} for c in criteria];out['bias_check']=('compare self-rating to artifact/rubric' if row==827 else 'anonymous where practical; train/calibrate raters; author can respond')
 if row in (829,830,831):
  try:out['assessment_design']=assess(row,p)
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==832:out['activation']=['quick prediction','concept map or free recall','surface relevant experience','flag misconceptions without grading']
 return out
def transfer(row,p):
 source=req(p,'source_case',dict);target=req(p,'target_case',dict);sf=set(source.get('features',[]));tf=set(target.get('features',[]));shared=sorted(sf&tf);diff=sorted(sf^tf);out={'source_case':source,'target_case':target,'shared_features':shared,'differing_features':diff}
 if row in (833,834,835):out['transfer_type']='near' if row==834 else 'far' if row==835 else p.get('transfer_type','unspecified');out['bridge_prompts']=['What deep structure is shared?','What changes in the target?','When would the source rule fail?'];out['requires_independent_target_performance']=True
 if row==836:out['analogy']={'correspondences':p.get('correspondences',[]),'surface_similarity_is_insufficient':True,'candidate_inferences':p.get('candidate_inferences',[]),'validate_in_target':True}
 if row==837:out['case_reasoning_cycle']=['retrieve by relevant features','reuse/adapt','revise against target evidence','retain with outcome'];out['adaptation_notes']=p.get('adaptation_notes',[])
 return out
def reasoning(row,p):
 premises=p.get('premises',[]);out={'premises':premises,'assumptions':p.get('assumptions',[]),'uncertainties':p.get('uncertainties',[]),'conclusion_status':'candidate until checked'}
 if row==838:
  rules=req(p,'rules',list);facts=set(map(str,p.get('facts',[])));derived=[]
  changed=True
  while changed:
   changed=False
   for r in rules:
    if set(map(str,r.get('if',[])))<=facts and str(r.get('then')) not in facts:facts.add(str(r['then']));derived.append({'rule':r.get('id'),'fact':str(r['then'])});changed=True
  out['rule_trace']=derived;out['facts']=sorted(facts)
 if row==839:out['model']={'entities':p.get('entities',[]),'relations':p.get('relations',[]),'constraints':p.get('constraints',[]),'predictions':p.get('predictions',[]),'validation_observations':p.get('validation_observations',[])}
 if row==840:out['qualitative_states']={'variables':p.get('variables',{}),'landmarks':p.get('landmarks',{}),'influences':p.get('influences',[]),'ambiguous_successors_preserved':True}
 if row==841:
  vals=req(p,'values',list);nums=[float(x) for x in vals];out['quantitative']={'count':len(nums),'sum':sum(nums),'mean':sum(nums)/len(nums),'range':max(nums)-min(nums),'units':p.get('units'),'significant_digits_not_invented':True}
 if row==842:out['spatial']={'objects':p.get('objects',[]),'relations':p.get('relations',[]),'frame_of_reference':p.get('frame_of_reference','must be specified'),'scale':p.get('scale'),'diagram_recommended':True}
 if row==843:
  events=req(p,'events',list);out['temporal']={'ordered':sorted(events,key=lambda x:x['time']),'relations':p.get('relations',[]),'timezone':p.get('timezone'),'uncertain_intervals_preserved':True}
 if row==844:
  try:out['causal']=causal_effect(p)
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==845:
  try:out['counterfactual']=counterfactual(p)
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==846:
  prior=float(p.get('prior',.5));likelihood=float(p.get('likelihood_given_h',.5));alt=float(p.get('likelihood_given_not_h',.5));den=prior*likelihood+(1-prior)*alt
  if not all(0<=x<=1 for x in (prior,likelihood,alt)) or not den:raise LearningReasoningError('invalid probabilities')
  out['bayes']={'prior':prior,'posterior':prior*likelihood/den,'likelihoods':[likelihood,alt]}
 if row==847:
  memberships=req(p,'memberships',dict)
  if not all(0<=float(v)<=1 for v in memberships.values()):raise LearningReasoningError('memberships must be in [0,1]')
  out['fuzzy']={'memberships':memberships,'and':min(map(float,memberships.values())),'or':max(map(float,memberships.values())),'not':{k:1-float(v) for k,v in memberships.items()}}
 if row in (848,849):
  try:out['defaults']=default_inference(p)
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==850:
  try:out['abduction']=abductive_search(p)
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==851:out['induction']={'observations':p.get('observations',[]),'pattern':p.get('pattern'),'sample_scope':p.get('sample_scope'),'exceptions':p.get('exceptions',[]),'generalization_strength':p.get('strength','uncalibrated')}
 if row==852:
  try:out['deduction']=argument_validity(p)
  except (ValueError,KeyError,TypeError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==853:out['transduction']={'source_instance':p.get('source_instance'),'target_instance':p.get('target_instance'),'local_similarity':p.get('local_similarity'),'scope':'target instance only; no population rule'}
 if row==854:out['dialectic']={'thesis':p.get('thesis'),'antithesis':p.get('antithesis'),'tensions':p.get('tensions',[]),'synthesis':p.get('synthesis'),'synthesis_must_preserve_unresolved_conflict':True}
 if row==855:out['integration']={'frames':p.get('frames',[]),'salient_tensions':p.get('tensions',[]),'shared_values':p.get('shared_values',[]),'novel_resolution':p.get('resolution'),'tradeoffs_visible':True}
 return out
def inquiry(row,p):
 problem=req(p,'problem',str);out={'problem':problem,'evidence':p.get('evidence',[]),'iteration_required':True}
 if row==856:out['system']={'boundary':p.get('boundary'),'elements':p.get('elements',[]),'connections':p.get('connections',[]),'stocks':p.get('stocks',[]),'flows':p.get('flows',[]),'feedback_loops':p.get('feedback_loops',[]),'delays':p.get('delays',[]),'unintended_consequences':p.get('unintended_consequences',[])}
 if row==857:out['design_cycle']=['empathize without claiming mind-reading','define need','diverge ideas','prototype','test with participants','iterate'];out['constraints']=p.get('constraints',[])
 if row==858:out['computational']={'decomposition':p.get('decomposition',[]),'patterns':p.get('patterns',[]),'abstraction':p.get('abstraction'),'algorithm':p.get('algorithm',[]),'test_cases':p.get('test_cases',[]),'complexity':p.get('complexity'),'automation_boundary':p.get('automation_boundary')}
 if row==859:out['science']={'question':p.get('question'),'hypothesis':p.get('hypothesis'),'prediction':p.get('prediction'),'design':p.get('design'),'controls':p.get('controls',[]),'measurements':p.get('measurements',[]),'analysis_plan':p.get('analysis_plan'),'falsification_condition':p.get('falsification_condition'),'replication_and_open_materials':True}
 return out
def execute(method,payload):
 if not isinstance(payload,dict):raise LearningReasoningError('payload must be an object')
 tenant=str(payload.get('tenant_id','default')).strip() if isinstance(payload,dict) else ''
 if not tenant:raise LearningReasoningError('tenant_id must not be empty')
 for ref in payload.get('resource_refs',[]):
  if str(ref.get('tenant_id','')).strip()!=tenant:raise LearningReasoningError('cross-tenant resource reference rejected')
 key=slug(method);row=KEYS.get(key)
 if row is None:raise LearningReasoningError(f'unknown method: {method}')
 if not isinstance(payload,dict):raise LearningReasoningError('payload must be an object')
 source=src(payload);family=FAMILY[row];result={'learning':learning,'transfer':transfer,'reasoning':reasoning,'inquiry':inquiry}[family](row,payload)
 completeness=sum(v not in (None,[],{}) for v in payload.values())/max(1,len(payload));uncertainties=result.get('uncertainties',payload.get('uncertainties',[]))
 return {'tenant_id':tenant,'row_id':row,'capability':ROWS[row],'family':family,'source':source,'result':result,'evaluation':{'input_completeness':round(completeness,3),'uncertainty_count':len(uncertainties),'status':'reviewable' if completeness>=.5 else 'insufficient_evidence','independent_verification_required':True},'uncertainty':{'calibration':'caller evidence and domain review required','drivers':list(uncertainties)},'boundary':'Decision support only. Preserve premises, evidence, assumptions, uncertainty, alternatives, learner agency, and qualified human review.'}
