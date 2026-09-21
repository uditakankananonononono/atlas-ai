"""Strong, bounded workflows for additional atomic concepts 1.1-3.1.

Design references: NIH rigor/reproducibility and data-management guidance; official
application requirements; NIST AI RMF human oversight/provenance; retrieval practice
using explicit embeddings. External signup/submission remains a reviewable proposal.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from math import sqrt
from urllib.parse import urlparse
import re
from typing import Any,Callable
class AtomicConceptError(ValueError):pass
ROWS={'1.1':'Research-project creation workflow','1.2':'Bioinformatics-project creation workflow','1.3':'Computer-science-project creation workflow','1.4':'Source-grounded summer-program application structuring','1.5':'Source-grounded competition application structuring','1.6':'Essay opportunity workflow','1.7':'Debate opportunity workflow','1.8':'Model United Nations opportunity workflow','1.9':'Olympiad opportunity workflow','1.10':'Hackathon opportunity workflow','1.11':'Official-source device and tool discovery','1.12':'Named-tool comparison for Instinct/Grok Bots/Replit/Astra-class products','1.13':'Resilient fallback selection when the preferred path fails','1.14':'Exact-review signup proposal without automatic submission','1.15':'Factual owner-voice humanization without detection evasion','1.16':'Broad public advice retrieval with provenance','1.17':'Careful advice-to-plan implementation and verification','2.1':'Decision capture with one-line owner reason','2.2':'Persistent decision journal storage','2.3':'Decision-note vector embedding','2.4':'Similarity retrieval over past decisions','2.5':'Recommendation adaptation from retrieved owner decisions','3.1':'Original-output and owner-correction pair capture'}
RESEARCH={'nih_rigor':'https://grants.nih.gov/policy/reproducibility/index.htm','nih_dms':'https://grants.nih.gov/policy-and-compliance/policy-topics/sharing-policies/dms/writing-dms-plan','common_app':'https://www.commonapp.org/apply/first-year-students/','mit_essays':'https://mitadmissions.org/apply/firstyear/essays-activities-academics/','nist_ai_rmf':'https://www.nist.gov/itl/ai-risk-management-framework'}
def capabilities():return [{'atomic_row_id':k,'requirement':v} for k,v in ROWS.items()]
def need(d,k,t):
 v=d.get(k)
 if not isinstance(v,t) or (t in (str,list,dict) and not v):raise AtomicConceptError(f'{k} must be non-empty {t.__name__}')
 return v
def sources(d):
 xs=need(d,'sources',list);out=[]
 for i,x in enumerate(xs):
  if not isinstance(x,dict) or not x.get('title') or not isinstance(x.get('url'),str) or urlparse(x['url']).scheme not in {'http','https'}:raise AtomicConceptError(f'sources[{i}] needs title and http(s) url')
  out.append({'id':x.get('id',f's{i+1}'),'title':x['title'],'url':x['url'],'official':bool(x.get('official',False)),'observed_at':x.get('observed_at')})
 return out
def project(kind,d):
 question=need(d,'question',str);evidence=sources(d);base={'kind':kind,'question':question,'hypothesis_or_objective':d.get('hypothesis_or_objective'),'background_sources':evidence,'milestones':['protocol review','pilot','data collection or build','analysis/evaluation','reproducible release'],'acceptance_tests':need(d,'acceptance_tests',list),'risk_register':d.get('risks',[]),'provenance_manifest':True,'claims_not_completion':True}
 if kind=='general':base['rigor']={'controls':d.get('controls',[]),'blinding_or_bias_reduction':d.get('bias_reduction',[]),'sample_size_or_coverage_rationale':d.get('coverage_rationale'),'analysis_plan_preregistered':bool(d.get('preregister')),'reference':RESEARCH['nih_rigor']};base['data_management']={'formats':d.get('formats',[]),'metadata':d.get('metadata'),'access':d.get('access'),'retention':d.get('retention'),'reference':RESEARCH['nih_dms']}
 if kind=='bioinformatics':base['workflow']={'input_accessions':need(d,'input_accessions',list),'reference_build':need(d,'reference_build',str),'environment_lock':d.get('environment_lock'),'quality_control':['raw QC','adapter/contamination check','mapping or assembly QC','sample identity'],'pipeline_stages':need(d,'pipeline_stages',list),'workflow_engine':d.get('workflow_engine','Nextflow or Snakemake'),'containers':d.get('containers',[]),'statistical_design':d.get('statistical_design'),'privacy_and_consent':d.get('privacy_and_consent'),'FAIR_outputs':True};base['prohibit']=['invented biological samples','unlicensed clinical data','unreported reference build']
 if kind=='computer_science':base['engineering']={'users_and_use_cases':d.get('users_and_use_cases',[]),'architecture_decisions':d.get('architecture_decisions',[]),'interfaces':d.get('interfaces',[]),'threat_model':d.get('threat_model'),'test_pyramid':['unit','integration','end-to-end'],'benchmark':d.get('benchmark'),'reproducible_build':True,'deployment_is_unproven_until_observed':True}
 return base
def application(kind,d):
 reqs=need(d,'requirements',list);owner=need(d,'owner_sources',list);oid={x.get('id') for x in owner};matrix=[]
 for r in reqs:
  ids=r.get('owner_source_ids',[]);matrix.append({'requirement':r.get('name'),'official_text':r.get('official_text'),'source_url':r.get('source_url'),'owner_source_ids':ids,'grounded':bool(ids) and set(ids)<=oid,'draft_status':'ready_for_owner_draft' if ids and set(ids)<=oid else 'blocked_missing_owner_evidence'})
 return {'application_type':kind,'requirements_matrix':matrix,'official_source_required':True,'owner_source_count':len(owner),'unsupported_requirements':[x['requirement'] for x in matrix if not x['grounded']],'submission_state':'not_submitted','reference':RESEARCH['common_app'],'boundary':'Never invent owner experiences, fit, awards, or activity details.'}
def opportunity(kind,d):
 listings=need(d,'listings',list);eligible=[]
 for x in listings:
  missing=[k for k in ('title','official_url','deadline','eligibility') if not x.get(k)]
  eligible.append({'title':x.get('title'),'official_url':x.get('official_url'),'deadline':x.get('deadline'),'eligibility':x.get('eligibility'),'verified_complete':not missing,'missing_fields':missing,'workflow':{'essay':['prompt parse','source-grounded outline','draft','fact check'], 'debate':['motion research','claim-evidence-warrant cases','rebuttal drills'], 'model_united_nations':['country policy brief','committee rules','position paper','resolution clauses'], 'olympiad':['syllabus map','diagnostic','deliberate practice','mock exam'], 'hackathon':['rules and judging matrix','team roles','MVP scope','demo and submission checklist']}[kind]})
 return {'kind':kind,'opportunities':eligible,'auto_signup':False,'exact_review_required':True}
def tool_discovery(d,comparison=False):
 xs=sources(d);products=need(d,'products',list);by={s['id']:s for s in xs};rows=[]
 for p in products:
  claims=[]
  for c in p.get('claims',[]):claims.append({**c,'source_resolved':c.get('source_id') in by,'status':'verified_from_cited_source' if c.get('source_id') in by else 'unverified'})
  rows.append({'name':p.get('name'),'category':p.get('category'),'claims':claims,'pricing_as_observed':p.get('pricing'),'privacy':p.get('privacy'),'availability':p.get('availability'),'fit_score':p.get('fit_score'),'official_sources_only':all(by.get(c.get('source_id'),{}).get('official') for c in p.get('claims',[])) if p.get('claims') else False})
 return {'mode':'named_comparison' if comparison else 'official_discovery','products':rows,'ranked_names':[x['name'] for x in sorted(rows,key=lambda z:-(z.get('fit_score') or 0))],'as_of_required':True,'no_claim_without_citation':True}
def fallback(d):
 paths=need(d,'paths',list);usable=[]
 for p in paths:
  blockers=set(p.get('blockers',[]));requirements=set(p.get('requirements',[]));available=set(d.get('available_capabilities',[]));usable.append({**p,'feasible':not blockers and requirements<=available,'missing_capabilities':sorted(requirements-available)})
 choice=next((x for x in sorted(usable,key=lambda z:(z.get('priority',999),z.get('cost',0))) if x['feasible']),None)
 return {'evaluated_paths':usable,'selected':choice,'outcome':'selected_fallback' if choice else 'blocked_no_honest_path','never_bypass_security_or_terms':True}
def signup(d):
 fields=need(d,'fields',dict);recipient=need(d,'destination',str)
 return {'destination':recipient,'exact_fields':fields,'attachments':d.get('attachments',[]),'fees_or_credits':d.get('fees_or_credits'),'deadline':d.get('deadline'),'review_hash':sha256(repr(sorted(fields.items())).encode()).hexdigest(),'state':'awaiting_exact_owner_review','submitted':False,'action_after_review_only':True}
def humanize(d):
 text=need(d,'text',str);facts=need(d,'owner_facts',list);unsupported=[f for f in d.get('claims',[]) if f not in facts]
 return {'text':text,'owner_voice_evidence':d.get('voice_samples',[]),'facts':facts,'unsupported_claims':unsupported,'ready':not unsupported,'detection_evasion':False,'editing_goals':['clarity','specificity','natural owner voice'],'reference':RESEARCH['nist_ai_rmf']}
def advice(d):
 src=sources(d);claims=[]
 for c in need(d,'claims',list):
  support=[s for s in c.get('source_ids',[]) if s in {x['id'] for x in src}];claims.append({**c,'supported_by':support,'status':'supported' if support else 'unsupported'})
 return {'sources':src,'claims':claims,'contradictions':d.get('contradictions',[]),'source_diversity':len({urlparse(x['url']).netloc for x in src}),'retrieved_not_implemented':True}
def plan(d):
 adv=need(d,'advice',list);steps=[]
 for i,a in enumerate(adv):steps.append({'id':f's{i+1}','advice':a.get('claim'),'action':a.get('action'),'evidence':a.get('evidence'),'acceptance_test':a.get('acceptance_test'),'rollback':a.get('rollback'),'status':'proposed'})
 if any(not s['acceptance_test'] for s in steps):raise AtomicConceptError('every plan step needs an acceptance_test')
 return {'steps':steps,'verification_order':[x['id'] for x in steps],'external_effects_executed':False}
def execute_atomic(row,d):
 if row not in ROWS:raise AtomicConceptError(f'unknown atomic row {row}')
 if row=='1.1':out=project('general',d)
 elif row=='1.2':out=project('bioinformatics',d)
 elif row=='1.3':out=project('computer_science',d)
 elif row=='1.4':out=application('summer_program',d)
 elif row=='1.5':out=application('competition',d)
 elif row in {'1.6','1.7','1.8','1.9','1.10'}:out=opportunity({'1.6':'essay','1.7':'debate','1.8':'model_united_nations','1.9':'olympiad','1.10':'hackathon'}[row],d)
 elif row=='1.11':out=tool_discovery(d)
 elif row=='1.12':out=tool_discovery(d,True)
 elif row=='1.13':out=fallback(d)
 elif row=='1.14':out=signup(d)
 elif row=='1.15':out=humanize(d)
 elif row=='1.16':out=advice(d)
 elif row=='1.17':out=plan(d)
 else:raise AtomicConceptError('journal concept requires tenant DecisionJournal')
 return {'atomic_row_id':row,'requirement':ROWS[row],'result':out,'external_effects':[],'strongest_honest_boundary':'Artifacts and proposals are real; external completion, infrastructure scale, and deployment remain unproven until observed.'}
def _cos(a,b):
 if len(a)!=len(b) or not a:raise AtomicConceptError('embedding dimensions must match and be nonempty')
 n=sqrt(sum(x*x for x in a))*sqrt(sum(x*x for x in b));return sum(x*y for x,y in zip(a,b))/n if n else 0
class DecisionJournal:
 def __init__(self,embed:Callable[[str],list[float]]):self.embed=embed;self.decisions=[];self.corrections=[]
 def capture(self,tenant,decision,reason,context=''):
  if not tenant or not decision.strip() or not reason.strip() or '\n' in reason:raise AtomicConceptError('tenant, decision and one-line reason required')
  note=f'{decision}\nReason: {reason}\nContext: {context}';vec=self.embed(note)
  if not vec:raise AtomicConceptError('embedding failed')
  rec={'id':sha256((tenant+'|'+note).encode()).hexdigest()[:24],'tenant_id':tenant,'decision':decision,'reason':reason,'context':context,'embedding':vec,'persistent_record':True};self.decisions.append(rec);return rec
 def retrieve(self,tenant,query,k=5):
  q=self.embed(query);hits=[{'id':x['id'],'decision':x['decision'],'reason':x['reason'],'similarity':_cos(q,x['embedding'])} for x in self.decisions if x['tenant_id']==tenant];return sorted(hits,key=lambda x:-x['similarity'])[:k]
 def adapt(self,tenant,proposal,query):
  hits=self.retrieve(tenant,query);return {'proposal':proposal,'retrieved_owner_decisions':hits,'adaptation_instruction':'Use reasons as evidence of prior preference, not a permanent rule; current owner intent wins.','owner_review_required':True,'claimed_owner_preference':False}
 def correction(self,tenant,original,corrected,context=''):
  if not original.strip() or not corrected.strip() or original==corrected:raise AtomicConceptError('distinct original and correction required')
  rec={'id':sha256((tenant+'|'+original+'|'+corrected).encode()).hexdigest()[:24],'tenant_id':tenant,'original':original,'correction':corrected,'context':context,'embedding':self.embed(original+' '+context),'few_shot_example':True};self.corrections.append(rec);return rec
