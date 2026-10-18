"""Deterministic, input-grounded marketing workbench for feature rows 401-426."""
from __future__ import annotations
from typing import Any, Callable

def _n(d,k,default=0.0):
 try:return float(d.get(k,default))
 except (TypeError,ValueError):raise ValueError(f"{k} must be numeric")
def _ratio(a,b):return a/b if b else None
def _base(d):
 facts=d.get('facts') or {}; goals=d.get('goals') or []
 return facts,goals

def segmentation(d):
 f,_=_base(d); groups=f.get('segment_metrics',[]); total=sum(_n(x,'customers') for x in groups)
 return {'segments':[dict(x,share=_ratio(_n(x,'customers'),total)) for x in groups],'sizing_notes':{'observed_customers':total,'coverage_requires_market_total':True},'data_gaps':[] if groups else ['segment_metrics']}
def targeting(d):
 f,_=_base(d); seg=f.get('segments',[]); scored=[]
 for x in seg: scored.append(dict(x,target_score=_n(x,'size')*_n(x,'conversion_rate')*_n(x,'margin')/max(_n(x,'cac',1),.01)))
 scored.sort(key=lambda x:x['target_score'],reverse=True);return {'selected_segments':scored[:max(1,int(f.get('select_count',1)))],'rationale':'score = size * conversion * margin / CAC','rejected_segments':scored[max(1,int(f.get('select_count',1))):]}
def positioning(d):
 # Row 403 rebuilt: delegate to the deterministic positioning engine
 # with code-enforced honesty guards (statement from provided facts via
 # disclosed template, every differentiator evidence-grounded). See
 # marketing_positioning.py.
 from .marketing_positioning import build_positioning
 return build_positioning(d)
 return {'statement':f.get('statement','TO BE PROVIDED'),'category':f.get('category','TO BE PROVIDED'),'differentiators':proven,'reasons_to_believe':[x['evidence'] for x in proven]}
def brand_architecture(d):
 # Row 404 rebuilt: delegate to the deterministic architecture engine
 # with code-enforced honesty guards (no invented entities, disclosed
 # structure inference, flagged dangling refs). See
 # marketing_brand_architecture.py.
 from .marketing_brand_architecture import build_brand_architecture
 return build_brand_architecture(d)
 return {'structure':structure,'entities':entities,'relationships':[{'parent':e.get('parent'),'child':e.get('name')} for e in entities if e.get('parent')],'migration_notes':f.get('migration_notes',[]),'orphan_count':sum(not e.get('parent') for e in entities[1:])}
def brand_voice(d):
 # Row 405 rebuilt: delegate to the deterministic voice engine with
 # code-enforced honesty guards (no invented values or examples,
 # disclosed flex templates). See marketing_brand_voice.py.
 from .marketing_brand_voice import build_brand_voice
 return build_brand_voice(d)
 return {'voice_attributes':attrs,'tone_by_context':f.get('tone_by_context',{}),'do_examples':[a.get('do') for a in attrs if a.get('do')],'dont_examples':[a.get('dont') for a in attrs if a.get('dont')],'example_coverage':_ratio(sum(bool(a.get('do')) and bool(a.get('dont')) for a in attrs),len(attrs))}
def messaging(d):
 # Row 406 rebuilt: delegate to the deterministic framework engine with
 # code-enforced honesty guards (proof only from provided facts,
 # disclosed templates, no invented segments). See
 # marketing_messaging_framework.py.
 from .marketing_messaging_framework import build_messaging_framework
 return build_messaging_framework(d)
 return {'core_message':f.get('core_message','TO BE PROVIDED'),'pillars':pillars,'proof_points':[p for x in pillars for p in x.get('proof_points',[])],'audience_variants':f.get('audience_variants',[]),'proof_coverage':_ratio(sum(bool(x.get('proof_points')) for x in pillars),len(pillars))}
def copywriting(d):return {'copy':'TO BE PROVIDED','headline_options':[],'call_to_action':'TO BE PROVIDED'}
def content_strategy(d):
 # Row 408 rebuilt: delegate to the deterministic strategy engine with
 # code-enforced honesty guards (formats/metrics only from provided
 # data, disclosed cadence default). See marketing_content_strategy.py.
 from .marketing_content_strategy import build_content_strategy
 return build_content_strategy(d)
 return {'pillars':f.get('pillars',[]),'formats':sorted({x.get('format') for x in pieces if x.get('format')}),'cadence':f.get('cadence',{}),'measurement':{'impressions':total,'engagement_rate':_ratio(sum(_n(x,'engagements') for x in pieces),total)}}
def editorial(d):return {'entries':[],'themes':[]}
def seo(d):
 f,_=_base(d); pages=f.get('pages',[])
 scored=[dict(x,seo_score=sum(bool(x.get(k)) for k in ('title','meta','h1','canonical'))/4) for x in pages]
 return {'on_page':scored,'content_gaps':[x.get('url') for x in scored if x['seo_score']<1],'priorities':sorted(scored,key=lambda x:x['seo_score'])}
def keywords(d):
 # Row 411 rebuilt: delegate to the deterministic expansion engine with
 # code-enforced honesty guards (no fabricated metrics, rule-based intent,
 # no external effects). See marketing_keyword_research.py.
 from .marketing_keyword_research import research_keywords
 return research_keywords(d)
def links(d):
 # Row 412 rebuilt: delegate to the deterministic outreach engine with
 # code-enforced honesty guards (never invents prospects or metrics,
 # disclosed angle rule table, drafts never sent). See
 # marketing_link_building.py.
 from .marketing_link_building import build_outreach
 return build_outreach(d)
def technical_seo(d):
 f,_=_base(d); urls=f.get('urls',[]); findings=[]
 for x in urls:
  if int(x.get('status',200))>=400:findings.append({'url':x.get('url'),'issue':'http_error','severity':'high'})
  if _n(x,'lcp_ms')>2500:findings.append({'url':x.get('url'),'issue':'slow_lcp','severity':'medium'})
 return {'findings':findings,'fixes':[{'issue':x['issue'],'verify_after_change':True} for x in findings],'checklist':['status<400','LCP<=2500ms'],'error_rate':_ratio(len(findings),len(urls))}
def local_seo(d):
 f,_=_base(d); loc=f.get('locations',[])
 return {'profile_recommendations':[{'location':x.get('name'),'missing':[k for k in ('address','phone','hours','category') if not x.get(k)]} for x in loc],'citations':f.get('citation_sources',[]),'review_plan':{'requested':_n(f,'review_requests'),'received':_n(f,'reviews_received'),'conversion':_ratio(_n(f,'reviews_received'),_n(f,'review_requests'))}}
def content_marketing(d):
 f,_=_base(d); pieces=f.get('pieces',[])
 return {'funnel_map':{s:[x.get('title') for x in pieces if x.get('stage')==s] for s in ('awareness','consideration','conversion','retention')},'pieces':pieces,'distribution':f.get('distribution',[]),'measurement':{'pipeline_value':sum(_n(x,'pipeline_value') for x in pieces),'cost_per_lead':_ratio(sum(_n(x,'cost') for x in pieces),sum(_n(x,'leads') for x in pieces))}}
def thought(d):
 # Row 416 rebuilt: delegate to the deterministic theme/outline engine
 # with code-enforced honesty guards (no invented areas or evidence,
 # disclosed angle templates). See marketing_thought_leadership.py.
 from .marketing_thought_leadership import build_thought_leadership
 return build_thought_leadership(d)
 return {'themes':themes,'outlines':[{'theme':x,'evidence_slots':f.get('evidence',{}).get(x,[]),'evidence_gap':not bool(f.get('evidence',{}).get(x))} for x in themes],'channels':f.get('channels',[])}
def pr(d):
 # Row 417 rebuilt: delegate to the deterministic PR engine with
 # code-enforced honesty guards (draft-only release, no invented quotes
 # or dates, disclosed review checklist). See
 # marketing_public_relations.py.
 from .marketing_public_relations import build_public_relations
 return build_public_relations(d)
def media(d):
 # Row 418 rebuilt: delegate to the deterministic pitch engine with
 # code-enforced honesty guards (never invents journalists/outlets,
 # disclosed mechanical tailoring, drafts never sent). See
 # marketing_media_relations.py.
 from .marketing_media_relations import build_media_relations
 return build_media_relations(d)
def crisis(d):
 f,_=_base(d); scenarios=f.get('scenarios',[])
 return {'scenarios':scenarios,'holding_statements':[{'scenario':x.get('name'),'draft':x.get('known_facts','TO BE PROVIDED'),'approved':False} for x in scenarios],'escalation_map':f.get('roles',[]),'response_templates':[],'max_severity':max([_n(x,'severity') for x in scenarios] or [0])}
def social(d):
 # Row 420 rebuilt: delegate to the deterministic strategy engine with
 # code-enforced honesty guards (roles from provided data or disclosed
 # archetypes, observed KPIs only from provided figures). See
 # marketing_social_strategy.py.
 from .marketing_social_strategy import build_social_strategy
 return build_social_strategy(d)
 return {'platform_roles':channels,'content_mix':f.get('content_mix',{}),'cadence':f.get('cadence',{}),'kpis':{'engagement_rate':_ratio(_n(f,'engagements'),_n(f,'impressions')),'conversion_rate':_ratio(_n(f,'conversions'),_n(f,'clicks'))}}
def community(d):
 f,_=_base(d); tickets=f.get('interactions',[])
 return {'engagement_playbook':f.get('playbook',[]),'moderation_guidelines':f.get('rules',[]),'response_templates':f.get('templates',[]),'escalation':[x for x in tickets if x.get('severity') in ('high','critical')],'median_response_minutes':sorted([_n(x,'response_minutes') for x in tickets])[len(tickets)//2] if tickets else None}
def influencer(d):
 c=d.get('contacts') or [];f,_=_base(d); cand=f.get('candidates',[]); allowed=[x for x in cand if x.get('name') in c]
 for x in allowed:x['estimated_cpe']=_ratio(_n(x,'cost'),_n(x,'expected_engagements'))
 return {'candidates':allowed,'briefs':f.get('briefs',[]),'outreach_drafts':[],'disclosure_rules':['clear and conspicuous sponsorship disclosure'],'candidate_count':len(allowed)}
def affiliate(d):
 f,_=_base(d); revenue=_n(f,'revenue');commission=_n(f,'commission');cost=_n(f,'platform_cost')
 return {'program_terms':f.get('terms',{}),'commission_options':f.get('commission_options',[]),'recruitment_draft':'TO BE PROVIDED','compliance_notes':['disclosure required','exclude self-referrals'],'roi':_ratio(revenue-commission-cost,commission+cost)}
def referral(d):
 f,_=_base(d); invites=_n(f,'invites');refs=_n(f,'qualified_referrals');cost=_n(f,'reward_cost');margin=_n(f,'referred_margin')
 return {'mechanics':f.get('mechanics',{}),'incentive_options':f.get('incentive_options',[]),'share_copy':f.get('share_copy',[]),'fraud_guards':['self-referral','duplicate identity','velocity cap'],'invite_conversion':_ratio(refs,invites),'program_roi':_ratio(margin-cost,cost)}
def email(d):
 f,_=_base(d); sent=_n(f,'sent');deliv=_n(f,'delivered');opens=_n(f,'unique_opens');clicks=_n(f,'unique_clicks');conv=_n(f,'conversions')
 return {'sequence':f.get('sequence',[]),'subject_lines':f.get('subject_lines',[]),'send_notes':{'draft_only':True},'metrics':{'delivery_rate':_ratio(deliv,sent),'open_rate':_ratio(opens,deliv),'click_to_open_rate':_ratio(clicks,opens),'conversion_rate':_ratio(conv,clicks)}}
def automation(d):
 f,_=_base(d); flows=f.get('workflows',[])
 analyzed=[]
 for x in flows: analyzed.append(dict(x,estimated_incremental_value=_n(x,'eligible')*_n(x,'incremental_conversion')*_n(x,'value_per_conversion')-_n(x,'run_cost')))
 return {'workflows':analyzed,'triggers':[x.get('trigger') for x in flows],'personalization':f.get('personalization',[]),'guardrails':['consent','frequency cap','unsubscribe','human activation'],'total_estimated_incremental_value':sum(x['estimated_incremental_value'] for x in analyzed)}

ENGINES:dict[str,Callable[[dict],dict]]={'segmentation':segmentation,'targeting':targeting,'positioning':positioning,'brand-architecture':brand_architecture,'brand-voice':brand_voice,'messaging-framework':messaging,'copywriting':copywriting,'content-strategy':content_strategy,'editorial-calendar':editorial,'seo-optimization':seo,'keyword-research':keywords,'link-building':links,'technical-seo':technical_seo,'local-seo':local_seo,'content-marketing':content_marketing,'thought-leadership':thought,'public-relations':pr,'media-relations':media,'crisis-communication':crisis,'social-media-strategy':social,'community-management':community,'influencer-marketing':influencer,'affiliate-marketing':affiliate,'referral-program':referral,'email-marketing':email,'marketing-automation':automation}
def compute(slug:str,data:dict)->dict:
 if slug not in ENGINES:raise ValueError(f'unknown marketing engine: {slug}')
 return ENGINES[slug](data)
