"""Enhanced ESAI-parity tools: evidence-grounded, explainable, student-owned."""
from __future__ import annotations
from typing import Any

def _tokens(*values)->set[str]:
 text=' '.join(str(x) for value in values for x in (value if isinstance(value,list) else [value])).lower()
 return {x.strip('.,:;!?()[]') for x in text.split() if len(x)>2}

def opportunity_match(track:str,profile:dict,opportunities:list[dict])->dict:
 if track not in {'college','career'}:raise ValueError('track must be college or career')
 identity=_tokens(profile.get('values',[]),profile.get('strengths',[]),profile.get('skills',[]),profile.get('interests',[]),profile.get('goals',[]));rows=[]
 for o in opportunities:
  required=[x for x in o.get('required_fields',[]) if x not in profile];overlap=sorted(identity&_tokens(o.get('themes',[]),o.get('skills',[]),o.get('programs',[])));deadline=o.get('deadline');source=o.get('official_url')
  if not source:raise ValueError('every opportunity needs official_url')
  rows.append({'id':o.get('id'),'name':o.get('name'),'score':None if required else round(len(overlap)/max(1,len(identity)),3),'matched_student_evidence':overlap,'missing_eligibility_facts':required,'deadline':deadline,'official_url':source,'status':'needs_information' if required else 'candidate'})
 return {'track':track,'matches':sorted(rows,key=lambda x:(x['status']!='candidate',-(x['score'] or 0),str(x['name']))),'not_an_admission_or_hiring_prediction':True,'enhancement':'explains evidence, missing eligibility facts, deadlines and official provenance rather than emitting an opaque match'}

def personal_stat(profile:dict,records:list[dict])->dict:
 verified=[r for r in records if r.get('source') and r.get('verified') is True];unknown=[r for r in records if not r.get('source') or r.get('verified') is not True]
 numeric={}
 for r in verified:
  if isinstance(r.get('value'),(int,float)):numeric.setdefault(r.get('metric'),[]).append(float(r['value']))
 return {'verified_metrics':{k:{'latest':v[-1],'count':len(v),'minimum':min(v),'maximum':max(v)} for k,v in numeric.items()},'verified_records':verified,'excluded_unverified_records':unknown,'profile_context':profile,'boundary':'Descriptive student-owned record only; no invented values, admission probability or comparison to undisclosed applicants.'}

def scholarship_guide(profile:dict,scholarships:list[dict])->dict:
 return opportunity_match('college',profile,[{**x,'programs':x.get('themes',[])} for x in scholarships])|{'guide_type':'scholarship','financial_need_private_by_default':True}

def loci_tool(context:dict,evidence:list[dict])->dict:
 required=['school','decision','submitted_application_summary'];missing=[x for x in required if not context.get(x)];updates=[x for x in evidence if x.get('occurred_after_submission') and x.get('source')]
 return {'status':'needs_input' if missing else 'ready_for_student_draft','missing_context':missing,'eligible_updates':updates,'excluded_updates':[x for x in evidence if x not in updates],'outline':[{'purpose':'continued interest','student_supplies':'specific truthful reason'},{'purpose':'material updates','student_evidence_ids':[x.get('id') for x in updates]},{'purpose':'fit and close','student_supplies':'own wording'}],'generated_letter_prose':None,'boundary':'Student authors every sentence. No invented achievements, pressure tactics, guaranteed enrollment claim or automatic submission.'}

def interview_prep(opportunity:dict,brand:dict,questions:list[dict])->dict:
 evidence=brand.get('evidence',[]);sessions=[]
 for q in questions:
  tags=set(q.get('evidence_tags',[]));matches=[e for e in evidence if tags&set(e.get('tags',[]))];sessions.append({'question':q.get('question'),'competency':q.get('competency'),'evidence_options':matches,'follow_ups':q.get('follow_ups',[]),'student_response':None,'rubric':q.get('rubric',[])})
 return {'opportunity':opportunity,'practice_turns':sessions,'answer_prose_generated':False,'enhancement':'evidence retrieval, follow-up depth and explicit rubric while keeping answers student-authored'}

def career_narrative(kind:str,opportunity:dict,brand:dict,student_facts:list[dict])->dict:
 themes=_tokens(opportunity.get('themes',[]),opportunity.get('skills',[]));supported=[x for x in student_facts if themes&_tokens(x.get('description',''),x.get('tags',[])) and x.get('source')]
 base={'kind':kind,'positioning':{'target':opportunity.get('name'),'matched_evidence':supported,'brand_values':brand.get('values',[]),'brand_strengths':brand.get('strengths',[])},'unsupported_facts':[x for x in student_facts if x not in supported],'student_review_required':True}
 if kind=='resume':base['sections']=[{'name':'summary','evidence_ids':[x.get('id') for x in supported]},{'name':'experience','evidence_ids':[x.get('id') for x in supported]}];base['generated_resume_prose']=None
 elif kind=='cover_letter':base['outline']=['student opening','evidence-backed fit','student close'];base['generated_letter_prose']=None
 elif kind=='linkedin_headline':base['headline_building_blocks']={'role':opportunity.get('role'),'strengths':brand.get('strengths',[]),'proof_tags':sorted({t for x in supported for t in x.get('tags',[])})};base['generated_headline']=None
 else:raise ValueError('unsupported career narrative kind')
 return base

def narrative_intelligence(evidence:list[dict],opportunity:dict)->dict:
    if not evidence:raise ValueError('student evidence required')
    themes=_tokens(opportunity.get('themes',[]),opportunity.get('values',[]));arcs=[]
    for e in evidence:
        if not e.get('source'):continue
        overlap=sorted(themes&_tokens(e.get('description',''),e.get('values',[]),e.get('tags',[])))
        arcs.append({'evidence_id':e.get('id'),'matched_opportunity_themes':overlap,'change':e.get('change'),'tension':e.get('tension'),'student_reflection':e.get('reflection'),'unknowns':[k for k in ('change','reflection') if not e.get(k)]})
    return {'evidence_arcs':arcs,'unsupported_evidence':[e for e in evidence if not e.get('source')],'generated_narrative_prose':None,'enhancement':'Traceable opportunity-specific story architecture with unknowns and source evidence, never opaque generated identity or final prose.'}

def college_track(profile:dict)->dict:
    return {'track':'college','identity_evidence_available':bool(profile.get('evidence')),'tools':['college_opportunity_match','story_strategy','supplemental_assistant','essay_suite','common_app_export'],'shared_identity_model':True,'limits':['No admission prediction','No invented activities','Student authors final prose']}

def story_strategy(prompt:str,evidence:list[dict],opportunity:dict)->dict:
    n=narrative_intelligence(evidence,opportunity);return {**n,'prompt':prompt,'strategy':[{'purpose':'specific situation','evidence_ids':[a['evidence_id'] for a in n['evidence_arcs'] if a.get('tension')]},{'purpose':'student action and consequence','evidence_ids':[a['evidence_id'] for a in n['evidence_arcs']]},{'purpose':'reflection connected to opportunity','evidence_ids':[a['evidence_id'] for a in n['evidence_arcs'] if a.get('student_reflection')]}],'student_choice_required':True}

def supplemental_assistant(prompts:list[dict],evidence:list[dict],opportunity:dict)->dict:
    return {'supplements':[{'prompt_id':p.get('id'),'word_limit':p.get('word_limit'),'prompt':p.get('prompt'),'strategy':story_strategy(p.get('prompt',''),evidence,opportunity),'student_draft':None} for p in prompts],'generated_essay_prose':None,'cross_prompt_overlap_warning':'Student must review repeated evidence across supplements.'}

def adapted_brand(brand:dict,opportunity:dict)->dict:
    evidence=brand.get('evidence',[]);themes=_tokens(opportunity.get('themes',[]),opportunity.get('skills',[]),opportunity.get('values',[]));matched=[e for e in evidence if themes&_tokens(e.get('student_response',''),e.get('tags',[]))]
    return {'stable_identity':{'values':brand.get('values',[]),'strengths':brand.get('strengths',[])},'opportunity':opportunity,'relevant_evidence':matched,'excluded_unmatched_evidence':[e for e in evidence if e not in matched],'adaptation_changes_presentation_not_identity':True,'generated_claims':None}

def entitlement_check(plan:str,existing_projects:int)->dict:
    limits={'free':1,'single':1,'unlimited':None}
    if plan not in limits:raise ValueError('unknown entitlement plan')
    limit=limits[plan];allowed=limit is None or existing_projects<limit
    return {'plan':plan,'project_limit':limit,'existing_projects':existing_projects,'can_create':allowed,'reason':None if allowed else 'project_limit_reached','billing_mutation_performed':False}

def common_app_export(profile:dict,activities:list[dict],essays:list[dict])->dict:
    required=['legal_name','graduation_year'];missing=[x for x in required if not profile.get(x)];invalid=[a.get('id') for a in activities if not a.get('student_confirmed') or not a.get('source')]
    return {'status':'needs_review' if missing or invalid else 'ready_for_user_download','missing_profile_fields':missing,'unconfirmed_activity_ids':invalid,'export':{'profile':profile,'activities':activities,'essays':[{'id':e.get('id'),'student_text':e.get('student_text'),'student_confirmed':e.get('student_confirmed')} for e in essays]},'submitted':False,'boundary':'User-reviewed export only. Atlas does not sign in, submit, attest, certify, invent or overwrite Common App data.'}

def essay_suite(prompt:str,evidence:list[dict],student_draft:str|None=None)->dict:
    strategy=story_strategy(prompt,evidence,{})
    return {'topic_and_strategy':strategy,'draft_present':bool(student_draft),'revision_checks':{'claims_with_source':[e.get('id') for e in evidence if e.get('source')],'needs_input':[e.get('id') for e in evidence if not e.get('source')],'clarity_review_available':bool(student_draft)},'generated_final_prose':None,'student_authorship_required':True}

def administrator_visibility(records:list[dict],consent:dict)->dict:
    if consent.get('scope')!='aggregate_engagement' or not consent.get('active'):raise ValueError('active aggregate_engagement consent required')
    groups={}
    for r in records:
        cohort=r.get('cohort','unspecified');g=groups.setdefault(cohort,{'students':set(),'sessions':0,'completed':0});g['students'].add(r.get('student_token'));g['sessions']+=int(r.get('sessions',0));g['completed']+=int(bool(r.get('completed')))
    minimum=int(consent.get('minimum_group_size',5));out=[]
    for cohort,g in groups.items():
        n=len(g['students']);out.append({'cohort':cohort,'student_count':n if n>=minimum else None,'sessions':g['sessions'] if n>=minimum else None,'completion_rate':g['completed']/n if n>=minimum and n else None,'suppressed':n<minimum})
    return {'aggregate_engagement':out,'individual_content_visible':False,'essay_text_visible':False,'identity_profile_visible':False,'consent':consent,'enhancement':'Small-cohort suppression and explicit consent exceed a simple administrator activity dashboard.'}
