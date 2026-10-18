"""Auditable learning-strategy and reasoning workbench (ledger 810-859)."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from math import exp,log
import re
from typing import Any
from .scientific_protocol import check as scientific_check
from .design_algorithms import design as design_check,algorithm as algorithm_run
from .claim_integration import check as claim_integration
from .qualitative_systems import qualitative as qualitative_graph,stock_flow
from .analogy_cases import analogy as checked_analogy,reuse as checked_case
from .near_far_transfer import compare as near_far_compare
from .activation_transfer import activate,transfer as checked_transfer
from .anchored_assessment import assess as anchored_assess
from .objective_plan import plan as objective_plan
from .regulated_learning import cycle as regulated_cycle
from .arithmetic_work import work as arithmetic_work
from .representation_practice import dual_pack,example_pack
from .explanation_practice import practice as explanation_practice
from .learning_calibration import calibrate_attempts
from .spaced_review import schedule_reviews
from .support_progression import progress_support
from .keyed_assessment import assess
from .progress_measurement import measure_progress
from .graph_transduction import transduce
from .boolean_induction import induce
from .interleaved_practice import interleave
from .spatial_constraints import solve_spatial
from .temporal_network import temporal
from .finite_model_reasoning import models
from .fuzzy_inference import infer
from .horn_inference import forward
from .measured_learning import recall_practice, deliberate_practice
from .defeasible_reasoning import default_inference, abductive_search
from .formal_reasoning import argument_validity, causal_effect, counterfactual
class LearningReasoningError(ValueError):pass
ROWS={810:'Spaced Repetition',811:'Interleaving',812:'Retrieval Practice',813:'Elaborative Interrogation',814:'Self-Explanation',815:'Dual Coding',816:'Concrete Examples',817:'Worked Examples',818:'Problem Solving',819:'Deliberate Practice',820:'Chunking',821:'Scaffolding',822:'Fading',823:'Metacognition',824:'Self-Regulated Learning',825:'Goal Setting',826:'Progress Monitoring',827:'Self-Assessment',828:'Peer Assessment',829:'Formative Assessment',830:'Summative Assessment',831:'Diagnostic Assessment',832:'Prior Knowledge Activation',833:'Transfer',834:'Near Transfer',835:'Far Transfer',836:'Analogical Reasoning',837:'Case-Based Reasoning',838:'Rule-Based Reasoning',839:'Model-Based Reasoning',840:'Qualitative Reasoning',841:'Quantitative Reasoning',842:'Spatial Reasoning',843:'Temporal Reasoning',844:'Causal Reasoning',845:'Counterfactual Reasoning',846:'Probabilistic Reasoning',847:'Fuzzy Logic',848:'Default Reasoning',849:'Non-Monotonic Reasoning',850:'Abductive Reasoning',851:'Inductive Reasoning',852:'Deductive Reasoning',853:'Transductive Reasoning',854:'Dialectical Reasoning',855:'Integrative Thinking',856:'Systems Thinking',857:'Design Thinking',858:'Computational Thinking',859:'Scientific Thinking'}
def slug(x):return re.sub(r'[^a-z0-9]+','_',x.lower()).strip('_')
KEYS={slug(v):k for k,v in ROWS.items()}
EXECUTED_ROWS={810,811,812,813,814,815,816,817,818,819,820,821,822,823,824,825,826,827,828,829,830,831,832,833,834,835,836,837,838,839,840,854,855,856,857,858,859,841,842,843,844,845,846,847,848,849,850,851,852,853}
SCAFFOLD_ROWS=set(ROWS)-EXECUTED_ROWS
FAMILY={**{i:'learning' for i in range(810,833)},**{i:'transfer' for i in range(833,838)},**{i:'reasoning' for i in range(838,856)},**{i:'inquiry' for i in range(856,860)}}
def capabilities():return [{'row_id':i,'key':slug(n),'name':n,'family':FAMILY[i],'execution_kind':'restricted_computation' if i in EXECUTED_ROWS else 'planning_scaffold'} for i,n in ROWS.items()]
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
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==811:
  try:out.update(interleave(p))
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==812:
  try:out['recall']=recall_practice(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==813:
  try:out['prompts']=[f'Why is {x} true, and under what conditions?' for x in p.get('claims',[objective])]
  except TypeError as exc:raise LearningReasoningError(f'claims must be an iterable of claim texts: {exc}')from exc
 if row==814:out['self_explanation_prompts']=['What principle applies?','Why is this step valid?','How does it connect to the goal?','What remains uncertain?']
 if row in (813,814):
  try:out['explanation_practice']=explanation_practice('elaborative_interrogation' if row==813 else 'self_explanation',p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (815,816):
  try:out['representation_pack' if row==815 else 'example_pack']=(dual_pack if row==815 else example_pack)(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (817,818):
  try:out['arithmetic_work']=arithmetic_work('worked_examples' if row==817 else 'problem_solving',p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==819:
  try:out['practice_plan']=deliberate_practice(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (820,825):
  try:out['objective_plan']=objective_plan(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (821,822):
  try:out.update(progress_support(p))
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==823:
  try:out['calibration']=calibrate_attempts(req(p,'attempts',list))
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
  out['calibration_required']=True
  out['scope']='Measured strategy calibration, not full metacognition'
 if row==824:
  try:out['regulated_cycle']=regulated_cycle(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==826:
  try:out['progress']=measure_progress(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (827,828):
  try:out['rubric_assessment']=anchored_assess('self' if row==827 else 'peer',p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (829,830,831):
  try:out['assessment_design']=assess(row,p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==832:
  try:out['activation']=activate(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 return out
def transfer(row,p):
 if row in (836,837):
  try:return {'analogy_check' if row==836 else 'case_reuse':(checked_analogy if row==836 else checked_case)(p)}
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (834,835):
  try:return {'near_far_transfer':near_far_compare('near_transfer' if row==834 else 'far_transfer',p)}
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==833:
  try:return {'transfer_evidence':checked_transfer(p)}
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 source=req(p,'source_case',dict);target=req(p,'target_case',dict);sf=set(source.get('features',[]));tf=set(target.get('features',[]));shared=sorted(sf&tf);diff=sorted(sf^tf);out={'source_case':source,'target_case':target,'shared_features':shared,'differing_features':diff}
 if row in (833,834,835):out['transfer_type']='near' if row==834 else 'far' if row==835 else p.get('transfer_type','unspecified');out['bridge_prompts']=['What deep structure is shared?','What changes in the target?','When would the source rule fail?'];out['requires_independent_target_performance']=True
 if row==836:out['analogy']={'correspondences':p.get('correspondences',[]),'surface_similarity_is_insufficient':True,'candidate_inferences':p.get('candidate_inferences',[]),'validate_in_target':True}
 if row==837:out['case_reasoning_cycle']=['retrieve by relevant features','reuse/adapt','revise against target evidence','retain with outcome'];out['adaptation_notes']=p.get('adaptation_notes',[])
 return out
def reasoning(row,p):
 premises=p.get('premises',[]);out={'premises':premises,'assumptions':p.get('assumptions',[]),'uncertainties':p.get('uncertainties',[]),'conclusion_status':'candidate until checked'}
 if row==838:
  try:out.update(forward(p))
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==839:
  try:out['model']=models(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==840:
  try:out['qualitative_graph']=qualitative_graph(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==841:
  vals=req(p,'values',list)
  try:nums=[float(x) for x in vals]
  except (TypeError,OverflowError) as exc:raise LearningReasoningError(f'values must contain only real numbers: {exc}')from exc
  out['quantitative']={'count':len(nums),'sum':sum(nums),'mean':sum(nums)/len(nums),'range':max(nums)-min(nums),'units':p.get('units'),'significant_digits_not_invented':True}
 if row==842:
  try:out['spatial']=solve_spatial(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==843:
  try:out['temporal']=temporal(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==844:
  try:out['causal']=causal_effect(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==845:
  try:out['counterfactual']=counterfactual(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==846:
  try:prior=float(p.get('prior',.5));likelihood=float(p.get('likelihood_given_h',.5));alt=float(p.get('likelihood_given_not_h',.5))
  except (TypeError,OverflowError) as exc:raise LearningReasoningError(f'prior and likelihoods must be real numbers: {exc}')from exc
  den=prior*likelihood+(1-prior)*alt
  if not all(0<=x<=1 for x in (prior,likelihood,alt)) or not den:raise LearningReasoningError('invalid probabilities')
  out['bayes']={'prior':prior,'posterior':prior*likelihood/den,'likelihoods':[likelihood,alt],'status':'supplied_probability_bayes_calculation','assumptions_verified':False,'real_world_truth_verified':False}
 if row==847:
  try:out['fuzzy']=infer(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (848,849):
  try:out['defaults']=default_inference(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==850:
  try:out['abduction']=abductive_search(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==851:
  try:out['induction']=induce(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==852:
  try:out['deduction']=argument_validity(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==853:
  try:out['transduction']=transduce(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (854,855):
  try:out['dialectic_check'if row==854 else 'integration_check']=claim_integration('dialectical_reasoning'if row==854 else 'integrative_thinking',p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 return out
def inquiry(row,p):
 problem=req(p,'problem',str);out={'problem':problem,'evidence':p.get('evidence',[]),'iteration_required':True}
 if row==856:
  try:out['stock_flow_simulation']=stock_flow(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row in (857,858):
  try:out['design_check'if row==857 else 'algorithm_run']=(design_check if row==857 else algorithm_run)(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 if row==859:
  try:out['scientific_check']=scientific_check(p)
  except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError) as exc:raise LearningReasoningError(str(exc)) from exc
 return out
def execute(method,payload):
 try:return _execute(method,payload)
 except LearningReasoningError:raise
 # hostile caller dunders may raise RuntimeError or arbitrary custom exception
 # classes at dispatch-level leaves (source fields, tenant_id, resource_refs,
 # units, values.N, completeness scan); code every Exception (never
 # BaseException) through the same LearningReasoningError envelope
 except Exception as exc:raise LearningReasoningError(str(exc)) from exc
def _execute(method,payload):
 if not isinstance(payload,dict):raise LearningReasoningError('payload must be an object')
 tenant=str(payload.get('tenant_id','default')).strip() if isinstance(payload,dict) else ''
 if not tenant:raise LearningReasoningError('tenant_id must not be empty')
 refs=payload.get('resource_refs',[])
 if not isinstance(refs,list):raise LearningReasoningError('resource_refs must be a list of objects')
 for ref in refs:
  if not isinstance(ref,dict):raise LearningReasoningError('resource_refs entries must be objects')
  if str(ref.get('tenant_id','')).strip()!=tenant:raise LearningReasoningError('cross-tenant resource reference rejected')
 key=slug(method);row=KEYS.get(key)
 if row is None:raise LearningReasoningError(f'unknown method: {method}')
 if not isinstance(payload,dict):raise LearningReasoningError('payload must be an object')
 source=src(payload);family=FAMILY[row];result={'learning':learning,'transfer':transfer,'reasoning':reasoning,'inquiry':inquiry}[family](row,payload)
 completeness=sum(v not in (None,[],{}) for v in payload.values())/max(1,len(payload));uncertainties=result.get('uncertainties',payload.get('uncertainties',[]))
 return {'tenant_id':tenant,'row_id':row,'capability':ROWS[row],'family':family,'source':source,'result':result,'evaluation':{'input_completeness':round(completeness,3),'uncertainty_count':len(uncertainties),'status':'restricted_computation' if row in EXECUTED_ROWS else 'planning_scaffold_only','capability_executed':row in EXECUTED_ROWS,'input_completeness_is_not_validity':True,'independent_verification_required':True},'uncertainty':{'calibration':'caller evidence and domain review required','drivers':list(uncertainties)},'boundary':('Restricted computation on supplied inputs only; no full capability or independent truth claim.' if row in EXECUTED_ROWS else 'Planning scaffold only: capability named above was not executed. Static prompts/copied caller fields do not demonstrate learning, reasoning or model output. Input nonemptiness is not evidence validity.')}
