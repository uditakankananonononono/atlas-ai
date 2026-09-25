"""Deterministic luxury-venture analytical tools. Real math and rules, no model calls, no invented data."""
from __future__ import annotations
from pydantic import BaseModel,Field,field_validator

class PriceSensitivityIn(BaseModel):
 too_cheap:list[float]=Field(min_length=4);bargain:list[float]=Field(min_length=4);expensive:list[float]=Field(min_length=4);too_expensive:list[float]=Field(min_length=4)
 @field_validator('*')
 @classmethod
 def positive(cls,v):
  if any(x<=0 for x in v):raise ValueError('prices must be positive')
  return v

def _cdf(points,sorted_prices,reverse=False):
 n=len(points);out=[]
 for p in sorted_prices:
  share=sum(1 for x in points if x<=p)/n
  out.append(1-share if reverse else share)
 return out
def _cross(p,a,b):
 for i in range(1,len(p)):
  d0,d1=a[i-1]-b[i-1],a[i]-b[i]
  if d0==0:return p[i-1]
  if d0*d1<=0 and d1!=d0:return round(p[i-1]+(p[i]-p[i-1])*d0/(d0-d1),2)
 return None

def price_sensitivity(data:PriceSensitivityIn)->dict:
 """Van Westendorp price sensitivity meter from real respondent price arrays."""
 grid=sorted(set(data.too_cheap+data.bargain+data.expensive+data.too_expensive))
 tc=_cdf(data.too_cheap,grid,reverse=True);bg=_cdf(data.bargain,grid,reverse=True);ex=_cdf(data.expensive,grid);te=_cdf(data.too_expensive,grid)
 pmc=_cross(grid,tc,ex)          # too cheap meets expensive
 pme=_cross(grid,te,bg)          # too expensive meets bargain
 opp=_cross(grid,tc,te)          # too cheap meets too expensive
 idp=_cross(grid,bg,ex)          # bargain meets expensive
 return {'respondents':len(data.too_cheap),'point_of_marginal_cheapness':pmc,'point_of_marginal_expensiveness':pme,'optimal_price_point':opp,'indifference_price_point':idp,'acceptable_range':[x for x in (pmc,pme) if x is not None],'method':'Van Westendorp price sensitivity meter on supplied respondent arrays','caveat':'Results describe only the supplied respondents; recruit qualified buyers before pricing.'}

class MarketSizingIn(BaseModel):
 market_name:str=Field(min_length=2,max_length=200);total_addressable:float=Field(gt=0);served_share:float=Field(gt=0,le=1);obtainable_share:float=Field(gt=0,le=1);currency:str=Field(default='USD',max_length=8);source_refs:list[str]=Field(min_length=1,max_length=20)

def market_sizing(data:MarketSizingIn)->dict:
 sam=round(data.total_addressable*data.served_share,2);som=round(sam*data.obtainable_share,2)
 return {'market':data.market_name,'currency':data.currency,'tam':data.total_addressable,'sam':sam,'som':som,'source_refs':data.source_refs,'caveat':'Shares are caller assumptions; only the arithmetic is computed here. Cite the named sources when presenting.'}

VALIDATION_METHODS=(
 {'method':'Structured problem interviews','cost':0,'evidence_strength':0.9,'needs':['qualified respondents'],'rule':'Five non-leading interviews; count independent top-two problem rankings.'},
 {'method':'Public-community listening','cost':0,'evidence_strength':0.6,'needs':['public forums'],'rule':'Collect verbatims from public owner/guest communities; log URL per verbatim.'},
 {'method':'Concierge smoke test','cost':0,'evidence_strength':0.8,'needs':['owner approval','named pilot users'],'rule':'Deliver the service manually to a handful of consented users; measure repeat requests.'},
 {'method':'Landing-page expression of interest','cost':0,'evidence_strength':0.5,'needs':['owner approval before publishing'],'rule':'Count qualified sign-ups against a stated hypothesis; no paid traffic.'},
 {'method':'Comparable-case analysis','cost':0,'evidence_strength':0.4,'needs':['cited public cases'],'rule':'Document three cited analogues; record where the analogy breaks.'},
)
def select_validation_methods(constraints:list[str])->dict:
 ranked=sorted(VALIDATION_METHODS,key=lambda m:-m['evidence_strength'])
 return {'constraints':constraints,'methods':ranked,'recommended':ranked[0]['method'],'all_zero_cost':True,'note':'Everything external-facing requires explicit owner approval before contact or publication.'}

def interview_script(customer_job:str,constraints:list[str])->dict:
 rules=['Ask about past behavior, not hypotheticals.','Do not mention the solution.','Stop if the participant has not experienced the problem.']
 questions=[f'Tell me about the last time you needed to: {customer_job}','What did you do first? What happened next?','What did that cost you - time, money, or frustration?','What have you already tried, and why did it fall short?','If you could change one thing about that experience, what would it be?']
 return {'rules':rules,'questions':questions,'constraints_honored':constraints,'qualified_exit':'Thank and end the interview if the problem is not experienced.','cost':0}

def pitch_outline(concept:dict,brief_sector:str)->dict:
 lines=[f"# {concept['name']} - outline",'','1. Problem and customer job',f"   - {concept['customer_job']}",'2. Concept promise',f"   - {concept['promise']}",'3. Evidence (cite each source id)',*[f"   - {ref}" for ref in concept['evidence_refs']],'4. Scorecard',*[f"   - {k}: {v}" for k,v in concept['scores'].items()],'5. $0 validation plan and success metric','6. Claim limits',*[f"   - {x}" for x in concept['prohibited_claims']]]
 return {'markdown':'\n'.join(lines),'sector':brief_sector,'review_status':'pending','external_action_started':False}

def follow_up_plan(subject:str,days:list[int]|None=None)->dict:
 days=days or [3,7,14]
 steps=[{'day':d,'channel':'same thread','goal':g,'status':'draft_requires_owner_approval'} for d,g in zip(days,['Share one new cited evidence point, restate the ask','Ask a single yes/no question about problem relevance','Close politely; record the outcome in the ledger'])]
 return {'subject':subject,'steps':steps,'sent':False,'boundary':'Planning only. Nothing is scheduled or sent.'}

def objection_sheet(concept:dict)->dict:
 rows=[{'objection':'Demand is unproven','response':'Correct. The $0 validation experiment exists to test it: '+concept['promise'],'evidence_refs':concept['evidence_refs']},{'objection':'Brand fit risk','response':'Brand-fit score '+str(concept['scores']['brand_fit'])+'/100 from explicit constraints; no affiliation is claimed.','evidence_refs':concept['evidence_refs']},{'objection':'Why you?','response':'Capability readiness '+str(concept['scores']['feasibility'])+'/100 with named capability refs.','evidence_refs':concept['capability_refs']}]
 return {'objections':rows,'review_status':'pending'}

def kpi_sheet(concept:dict)->dict:
 metrics=[{'metric':'Problem-confirmation rate','formula':'qualified confirmations / qualified interviews','target':'>= 0.6'},{'metric':'Repeat-request rate (concierge test)','formula':'users requesting again / pilot users','target':'>= 0.5'},{'metric':'Evidence coverage','formula':'cited sources / claims made','target':'>= 1.0'}]
 return {'concept_id':concept['concept_id'],'metrics':metrics,'note':'Targets are defaults to review, not promises.'}

def positioning_map(price_band:float,heritage:float,peers:list[dict])->dict:
 def q(p,h):return ('icon' if h>=3 else 'entrant')+' / '+('high luxury' if p>=3 else 'accessible')
 for x in peers+[{'name':'self','price_band':price_band,'heritage':heritage}]:
  if not (1<=x['price_band']<=5 and 1<=x['heritage']<=5):raise ValueError('bands must be 1-5')
 return {'axes':{'x':'price band 1-5','y':'heritage/craft 1-5'},'self':{'price_band':price_band,'heritage':heritage,'quadrant':q(price_band,heritage)},'peers':[dict(p,quadrant=q(p['price_band'],p['heritage'])) for p in peers],'caveat':'Positions are caller judgments on explicit scales, not market facts.'}

def explain_scorecard(scores:dict)->dict:
 weights={'desirability_evidence':.25,'feasibility':.2,'brand_fit':.2,'differentiation':.15,'implementation_effort':-.1,'risk':-.1}
 lines=[{'factor':k,'value':scores[k],'weight':w,'contribution':round(abs(w)*(100-scores[k]) if w<0 else w*scores[k],2)} for k,w in weights.items() if k in scores]
 return {'factors':lines,'weighted_total':scores.get('weighted_total'),'reproducible':'Weights are fixed in the venture scorer; contributions shown for review.'}

SECTOR_PRESETS={
 'automotive':{'constraints':['scarcity','dealer experience','brand tone'],'capabilities':[{'capability_id':'owner-provenance-ledger','description':'Verified vehicle history and craft records','readiness':.7}]},
 'luxury_hospitality':{'constraints':['consent','privacy','service tone'],'capabilities':[{'capability_id':'consented-preference-ledger','description':'Guest preferences with revocation','readiness':.8}]},
 'fashion':{'constraints':['season calendar','channel control'],'capabilities':[{'capability_id':'drop-intelligence','description':'Drop timing and sell-through evidence tracker','readiness':.6}]},
 'jewelry':{'constraints':['provenance law','certification'],'capabilities':[{'capability_id':'stone-provenance','description':'Certification and origin record display','readiness':.6}]},
 'character_ip':{'constraints':['license terms','brand voice'],'capabilities':[{'capability_id':'fan-engagement-consent','description':'Opt-in fan personalization','readiness':.6}]},
 'hotel':{'constraints':['consent','privacy'],'capabilities':[{'capability_id':'service-gap-detection','description':'Operations signal review for staff','readiness':.6}]},
 'other':{'constraints':['brand tone'],'capabilities':[{'capability_id':'evidence-pack','description':'Cited concept packaging','readiness':.7}]},
}
def sector_presets()->dict:return {'sectors':SECTOR_PRESETS,'note':'Starting points to edit, not defaults silently applied.'}

def digest(pack:dict)->dict:
 lines=[f"# Luxury intelligence digest - {pack.get('brand_or_segment','')}",f"Collected {pack.get('collected_on','')} - all sources free",'','## Evidence']
 for s in pack.get('sources',[]):lines.append(f"- **{s['title']}** ({s['source_id']})\n  {s['finding'][:240]}\n  {s['url']}")
 lines+=['','## Fetch report']+[f"- {r['source']}: {r['status']}" for r in pack.get('fetch_report',[])]
 return {'markdown':'\n'.join(lines),'evidence_items':len(pack.get('sources',[])),'review_required':pack.get('review_required','')}
