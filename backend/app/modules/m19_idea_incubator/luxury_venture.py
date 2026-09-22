"""Evidence-grounded luxury venture concept studio.

Produces review-only concept and validation packages from caller supplied public evidence.
It does not claim brand affiliation, contact a brand, publish, sell, or spend money.
"""
from __future__ import annotations
from pydantic import BaseModel,Field,field_validator
from typing import Literal

class Source(BaseModel):
 source_id:str=Field(min_length=1,max_length=120)
 url:str=Field(pattern=r'^https?://',max_length=2000)
 title:str=Field(min_length=1,max_length=300)
 observed_at:str=Field(min_length=10,max_length=40)
 finding:str=Field(min_length=10,max_length=2000)

class Signal(BaseModel):
 signal_id:str=Field(min_length=1,max_length=120)
 statement:str=Field(min_length=10,max_length=1000)
 source_ids:list[str]=Field(min_length=1,max_length=20)
 importance:float=Field(ge=0,le=1)

class Capability(BaseModel):
 capability_id:str=Field(min_length=1,max_length=120)
 description:str=Field(min_length=5,max_length=500)
 readiness:float=Field(ge=0,le=1)

class VentureBrief(BaseModel):
 brand_or_segment:str=Field(min_length=2,max_length=200)
 sector:Literal['automotive','character_ip','hotel','luxury_hospitality','fashion','jewelry','other']
 customer_job:str=Field(min_length=10,max_length=1000)
 constraints:list[str]=Field(min_length=1,max_length=30)
 sources:list[Source]=Field(min_length=2,max_length=50)
 signals:list[Signal]=Field(min_length=2,max_length=50)
 capabilities:list[Capability]=Field(min_length=1,max_length=30)

 @field_validator('brand_or_segment','customer_job')
 @classmethod
 def strip_text(cls,v):
  if not v.strip():raise ValueError('must not be blank')
  return v.strip()

ANGLES=(
 ('guest_or_owner_intelligence','A private, consented concierge that remembers preferences and explains every recommendation.'),
 ('operations_quality','A staff decision tool that detects service gaps from supplied operational evidence before they affect the experience.'),
 ('provenance_storytelling','A provenance experience that turns verified craft, place, and product records into a customer-facing narrative.'),
)

def _score(angle:int,brief:VentureBrief)->dict:
 evidence=round(100*sum(s.importance for s in brief.signals)/len(brief.signals),1)
 readiness=round(100*sum(c.readiness for c in brief.capabilities)/len(brief.capabilities),1)
 # Explicit, reproducible heuristics. Scores are prioritization aids, not market facts.
 fit=round(min(100,55+5*len(brief.constraints)+angle*3),1)
 differentiation=round(min(100,62+len(brief.sources)*2-angle*2),1)
 effort=round(max(0,100-readiness+angle*7),1)
 risk=round(min(100,25+5*len(brief.constraints)+angle*4),1)
 total=round(.25*evidence+.2*readiness+.2*fit+.15*differentiation+.1*(100-effort)+.1*(100-risk),1)
 return {'desirability_evidence':evidence,'feasibility':readiness,'brand_fit':fit,'differentiation':differentiation,'implementation_effort':effort,'risk':risk,'weighted_total':total}

def build_luxury_venture(brief:VentureBrief)->dict:
 source_ids={s.source_id for s in brief.sources}
 if len(source_ids)!=len(brief.sources):raise ValueError('source_id values must be unique')
 unknown=sorted({x for s in brief.signals for x in s.source_ids}-source_ids)
 if unknown:raise ValueError('signals cite unknown source_ids: '+', '.join(unknown))
 cited=sorted({x for s in brief.signals for x in s.source_ids})
 concepts=[]
 for i,(key,promise) in enumerate(ANGLES):
  scores=_score(i,brief)
  concepts.append({'concept_id':key,'name':key.replace('_',' ').title(),'promise':promise,
   'customer_job':brief.customer_job,'evidence_refs':cited,'capability_refs':[c.capability_id for c in brief.capabilities],
   'scores':scores,'assumptions':['brand stakeholder has not validated this concept','customer willingness to pay is unknown'],
   'prohibited_claims':['brand affiliation or endorsement','validated demand','guaranteed revenue or outcome']})
 concepts.sort(key=lambda x:(-x['scores']['weighted_total'],x['concept_id']))
 winner=concepts[0]
 experiment={'concept_id':winner['concept_id'],'budget_limit':0,'method':'Five structured problem interviews using a review-approved, non-leading script','success_metric':'At least 3 of 5 qualified participants independently rank the problem among their top two','external_action_started':False,'requires_approval_before_contact':True}
 pitch={'status':'review_only','brand_or_segment':brief.brand_or_segment,'problem':brief.customer_job,'recommended_concept_id':winner['concept_id'],'evidence_refs':winner['evidence_refs'],'next_proof':experiment['success_metric'],'claim_limits':winner['prohibited_claims']}
 return {'brand_or_segment':brief.brand_or_segment,'sector':brief.sector,'concepts':concepts,'recommended_concept_id':winner['concept_id'],'validation_experiment':experiment,'pitch_brief':pitch,'side_effects':[],'boundary':'Concept research and packaging only. No affiliation claim, outreach, publication, sale, contract, purchase, or spend occurs. Review current public sources and obtain explicit approval before any external action.'}

class PitchPackageRequest(BaseModel):
 brief:VentureBrief
 concept_id:str|None=None

def build_pitch_package(request:PitchPackageRequest)->dict:
 studio=build_luxury_venture(request.brief)
 concept_id=request.concept_id or studio['recommended_concept_id']
 matches=[x for x in studio['concepts'] if x['concept_id']==concept_id]
 if not matches:raise ValueError('concept_id is not present in this studio result')
 c=matches[0];experiment=studio['validation_experiment']
 markdown='\n'.join([
  f"# {c['name']} - review-only venture brief",'',
  f"**Target:** {request.brief.brand_or_segment}",f"**Customer job:** {c['customer_job']}",'',
  '## Concept',c['promise'],'','## Evidence',*[f"- {ref}" for ref in c['evidence_refs']],'',
  '## Scorecard',*[f"- {k.replace('_',' ').title()}: {v}" for k,v in c['scores'].items()],'',
  '## Cheapest next proof',experiment['method'],f"Success: {experiment['success_metric']}",'',
  '## Claim limits',*[f"- {x}" for x in c['prohibited_claims']],'',
  '> Draft for owner review. No brand affiliation, outreach, sale, publication, contract, or spend has occurred.'
 ])
 return {'concept_id':concept_id,'filename':concept_id+'-review-brief.md','media_type':'text/markdown','markdown':markdown,'evidence_refs':c['evidence_refs'],'review_status':'pending','external_action_started':False}

class OutreachPreview(BaseModel):
 concept_id:str
 recipient_organization:str=Field(min_length=2,max_length=200)
 recipient_role:str=Field(min_length=2,max_length=200)
 channel:Literal['email','contact_form','introduction']
 subject:str=Field(min_length=3,max_length=200)
 body:str=Field(min_length=20,max_length=5000)
 evidence_refs:list[str]=Field(min_length=1,max_length=50)

def validate_outreach_preview(data:OutreachPreview,package:dict)->dict:
 if data.concept_id!=package['concept_id']:raise ValueError('concept_id does not match pitch package')
 unknown=sorted(set(data.evidence_refs)-set(package['evidence_refs']))
 if unknown:raise ValueError('outreach cites evidence absent from pitch package: '+', '.join(unknown))
 banned=('partnered with','official partner','guaranteed','validated demand','endorsed by')
 found=[x for x in banned if x in (data.subject+' '+data.body).lower()]
 if found:raise ValueError('unsupported external claim: '+', '.join(found))
 return {'concept_id':data.concept_id,'recipient_organization':data.recipient_organization,'recipient_role':data.recipient_role,'channel':data.channel,'subject':data.subject,'body':data.body,'evidence_refs':data.evidence_refs,'status':'pending_approval','sent':False,'boundary':'Approval request only. This endpoint does not send or submit the message.'}

class VentureOutcome(BaseModel):
 status:Literal['succeeded','failed','inconclusive']
 observed_value:float
 target:float
 learnings:str=Field(min_length=10,max_length=5000)
 source_refs:list[str]=Field(min_length=1,max_length=50)

def summarize_outcome(data:VentureOutcome)->dict:
 met=data.observed_value>=data.target
 if data.status=='succeeded' and not met:raise ValueError('succeeded conflicts with observed_value below target')
 if data.status=='failed' and met:raise ValueError('failed conflicts with observed_value meeting target')
 return {'status':data.status,'observed_value':data.observed_value,'target':data.target,'target_met':met,'learnings':data.learnings,'source_refs':data.source_refs,'promotion_recommendation':'advance_to_owner_review' if data.status=='succeeded' else 'revise_or_stop' if data.status=='failed' else 'collect_more_evidence','automatic_promotion':False}
