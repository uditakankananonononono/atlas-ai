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
