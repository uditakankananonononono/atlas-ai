"""Grounded education support for owner feature rows 1460-1509."""
from math import exp,sqrt
from statistics import mean
import re
FEATURES=dict(enumerate('''Engagement Detection|Dropout Prediction|Performance Prediction|Recommendation Systems|Content Recommendation|Peer Recommendation|Path Recommendation|Automated Essay Scoring|Automated Feedback|Formative Assessment|Summative Assessment|Diagnostic Assessment|Authentic Assessment|Performance Assessment|Portfolio Assessment|Self-Assessment|Peer Assessment|Assessment for Learning|Assessment as Learning|Assessment of Learning|Standards-Based Grading|Competency-Based Education|Mastery Learning|Precision Teaching|Direct Instruction|Explicit Instruction|Systematic Instruction|Scripted Instruction|Programmed Instruction|Computer-Assisted Instruction|Intelligent Tutoring Systems|Dialogue-Based Tutoring|Socratic Tutoring|Metacognitive Tutoring|Motivational Tutoring|Emotional Support|Social-Emotional Learning|Character Education|Citizenship Education|Global Competence|Cultural Competence|Intercultural Education|Multicultural Education|Inclusive Education|Special Education|Gifted Education|Remedial Education|Compensatory Education|Bilingual Education|Language Learning'''.split('|'),1460))
def finite_number(value,label):
 try: number=float(value)
 except (TypeError,ValueError): raise ValueError(label+' must be numeric')
 if number != number or number in (float('inf'),float('-inf')): raise ValueError(label+' must be finite')
 return number
def need(d,*ks):
 m=[k for k in ks if d.get(k) in (None,[],{})]
 if m:raise ValueError('missing required inputs: '+', '.join(m))

DIRECT_IDENTIFIERS={"learner_id","student_id","pupil_id","email","phone","full_name"}
def reject_direct_identifiers(value,path="data"):
 if isinstance(value,dict):
  for k,v in value.items():
   if k.lower() in DIRECT_IDENTIFIERS: raise ValueError(f"direct learner identifier prohibited; direct learner identifiers are not accepted: {path}.{k}")
   reject_direct_identifiers(v,f"{path}.{k}")
 elif isinstance(value,list):
  for n,v in enumerate(value):reject_direct_identifiers(v,f"{path}[{n}]")

def number(value,label,low=None,high=None,positive=False):
 if isinstance(value,bool) or not isinstance(value,(int,float)):raise ValueError(f"{label} must be numeric")
 x=float(value)
 if positive and x<=0:raise ValueError(f"{label} must be positive")
 if low is not None and x<low or high is not None and x>high:raise ValueError(f"{label} out of range")
 return x
def analytics(i,d):
 if i==1460:
  need(d,'signals'); vs=[(number(x.get('value'),'signal value',0,1),number(x.get('weight',1),'signal weight',positive=True)) for x in d['signals']]
  if any(v<0 or v>1 or w<=0 for v,w in vs):raise ValueError('signals must be [0,1] with positive weights')
  s=sum(v*w for v,w in vs)/sum(w for _,w in vs);return {'engagement_score':round(s,4),'band':'high' if s>=.7 else 'medium' if s>=.4 else 'low','interpretation':'descriptive signal, not attention or intent'}
 need(d,'features','coefficients');x=d['features'];c=d['coefficients'];missing=set(c)-set(x)-{'intercept'}
 if missing:raise ValueError('missing model features: '+', '.join(sorted(missing)))
 y=float(c.get('intercept',0))+sum(float(c[k])*float(x[k]) for k in c if k!='intercept')
 return {'dropout_risk_probability':round(1/(1+exp(-y)),4),'intervention_decision':'human_review_required','model_version':d.get('model_version')} if i==1461 else {'predicted_performance':round(y,4),'unit':d.get('unit','model units'),'prediction_only':True}
def recommend(i,d):
 if i==1463:
  need(d,'learner_vector','candidates');a=d['learner_vector']
  def sim(b):
   if len(a)!=len(b) or not a:raise ValueError('vectors must align')
   z=sqrt(sum(x*x for x in a)*sum(x*x for x in b));return 0 if not z else sum(x*y for x,y in zip(a,b))/z
  return {'ranked_recommendations':sorted(({'id':c['id'],'score':round(sim(c['vector']),4)} for c in d['candidates']),key=lambda x:(-x['score'],x['id'])),'selected':False}
 if i==1464:
  need(d,'learner_tags','content');t=set(d['learner_tags']);r=[{'id':c['id'],'matched_tags':sorted(t&set(c.get('tags',[]))),'score':len(t&set(c.get('tags',[])))/len(t)} for c in d['content']];return {'ranked_content':sorted(r,key=lambda x:(-x['score'],x['id'])),'filter_bubble_review':True}
 if i==1465:
  need(d,'learner','peers');m=d['learner'];r=[]
  for p in d['peers']:
   shared=set(m.get('interests',[]))&set(p.get('interests',[]));helped=set(m.get('seeking',[]))&set(p.get('can_help_with',[]));r.append({'id':p['id'],'shared_interests':sorted(shared),'complementary_skills':sorted(helped),'score':len(shared)+2*len(helped)})
  return {'ranked_peers':sorted(r,key=lambda x:(-x['score'],x['id'])),'contacted':False,'consent_required':True}
 need(d,'completed','nodes');done=set(d['completed']);available=[{'id':n['id'],'priority':n.get('priority',0)} for n in d['nodes'] if n['id'] not in done and set(n.get('prerequisites',[]))<=done];return {'next_nodes':sorted(available,key=lambda x:(-x['priority'],x['id'])),'path_changed':False}
def writing(i,d):
 if i==1467:
  need(d,'rubric','ratings');rows=[];num=den=0
  for r in d['rubric']:
   if r['id'] not in d['ratings']:raise ValueError('missing rubric rating')
   s=finite_number(d['ratings'][r['id']],'rubric rating');mx=finite_number(r['max_score'],'rubric max_score');w=finite_number(r.get('weight',1),'rubric weight')
   if mx<=0 or w<=0:raise ValueError('rubric max_score and weight must be positive')
   if not 0<=s<=mx:raise ValueError('rubric rating out of range')
   rows.append({'criterion_id':r['id'],'score':s,'max_score':mx});num+=s/mx*w;den+=w
  return {'rubric_results':rows,'normalized_score':round(100*num/den,2),'final_grade_awarded':False,'human_moderation_required':True}
 need(d,'rubric_results');r=[{'criterion_id':x['criterion_id'],'gap':x['target']-x['score'],'feedback':x.get('feedback','Revise evidence for '+x['criterion_id'])} for x in d['rubric_results'] if x['score']<x['target']];return {'prioritized_feedback':sorted(r,key=lambda x:-x['gap']),'revision_owned_by_learner':True}
A={1469:('formative','during learning','adjust instruction'),1470:('summative','end of learning','judge attainment'),1471:('diagnostic','before learning','identify prerequisite patterns'),1472:('authentic','real-world task','apply knowledge'),1473:('performance','demonstration','observe performance'),1474:('portfolio','collection over time','show growth'),1475:('self','reflection','build self-judgment'),1476:('peer','peer review','learn through feedback'),1477:('for_learning','ongoing evidence','adapt teaching'),1478:('as_learning','metacognitive monitoring','self-regulate'),1479:('of_learning','checkpoint','report attainment')}
def assessment(i,d):
 need(d,'objectives','evidence');ids={x['id'] for x in d['objectives']};mapped=[]
 for e in d['evidence']:
  unknown=set(e.get('objective_ids',[]))-ids
  if unknown:raise ValueError('unknown objective ids')
  mapped.append({'evidence_id':e['id'],'objective_ids':e.get('objective_ids',[]),'rubric':e.get('rubric',[])})
 k,t,p=A[i];o={'assessment_type':k,'timing':t,'purpose':p,'evidence_map':mapped,'unassessed_objectives':sorted(ids-{x for e in mapped for x in e['objective_ids']}),'score_or_grade_finalized':False}
 gaps=o['unassessed_objectives']
 if i==1469:o['instructional_adjustments']=[{'objective_id':x,'action':'collect evidence and reteach'} for x in gaps]
 elif i==1470:o['attainment_summary']={'objectives_with_evidence':len(ids)-len(gaps),'total_objectives':len(ids)}
 elif i==1471:o['prerequisite_gaps']=[{'objective_id':x,'diagnostic_follow_up':True} for x in gaps]
 elif i==1472:o['authenticity_review']={'context':d.get('real_world_context'),'audience':d.get('audience'),'constraints':d.get('constraints',[])}
 elif i==1473:o['performance_observations']=[{'evidence_id':x['evidence_id'],'observable':bool(x['rubric'])} for x in mapped]
 elif i==1474:o['portfolio_checkpoints']=d.get('checkpoints',[])
 elif i==1475:o['self_calibration']={'reflection_prompts':d.get('reflection_prompts',['What evidence supports your judgment?']),'teacher_comparison_pending':True}
 elif i==1476:o['peer_moderation']={'anonymous':bool(d.get('anonymous',True)),'teacher_moderation_required':True}
 elif i==1477:o['next_teaching_moves']=[{'objective_id':x,'move':'elicit new evidence'} for x in gaps]
 elif i==1478:o['metacognitive_cycle']={'reflection_prompts':d.get('reflection_prompts',['What evidence supports your judgment?','What will you change?']),'plan_revision_required':True}
 elif i==1479:o['reporting_summary']={'attained_evidence_count':sum(bool(x['objective_ids']) for x in mapped),'teacher_signoff_required':True}
 return o
def progress(i,d):
 if i==1480:
  need(d,'standards','evidence');rows=[]
  for s in d['standards']:
   threshold=number(s.get('threshold'),'standard threshold',0,100);v=[number(x.get('score'),'evidence score',0,100) for x in d['evidence'] if x.get('standard_id')==s['id']];rows.append({'standard_id':s['id'],'level':round(mean(v),2) if v else None,'status':'insufficient_evidence' if not v else 'meets' if mean(v)>=threshold else 'developing'})
  return {'standards':rows,'averaged_into_single_grade':False}
 need(d,'competencies','evidence');ev={x['competency_id']:number(x.get('score'),'competency score',0,1) for x in d['evidence']};rows=[{'competency_id':c['id'],'score':ev.get(c['id'],0),'threshold':number(c.get('mastery_threshold'),'mastery threshold',0,1),'mastered':ev.get(c['id'],0)>=number(c.get('mastery_threshold'),'mastery threshold',0,1)} for c in d['competencies']]
 if i==1481:return {'competency_progress':rows,'advancement_candidates':[x['competency_id'] for x in rows if x['mastered']],'advancement_requires_review':True}
 if i==1482:return {'mastery_status':rows,'reteach':[x['competency_id'] for x in rows if not x['mastered']],'reassessment_required':True}
 need(d,'timed_probes');rates=[number(x.get('correct'),'probe correct',0)/number(x.get('minutes'),'probe minutes',positive=True) for x in d['timed_probes']];return {'frequency_per_minute':rates,'celeration_ratio':None if len(rates)<2 or rates[0]==0 else round(rates[-1]/rates[0],3),'decision':'review teaching' if d.get('aim') and rates[-1]<d['aim'] else 'continue and monitor'}
I={1484:('direct_instruction',['review','model','guided practice','independent practice','check']),1485:('explicit_instruction',['state objective','explain','model think-aloud','guided practice','check understanding','independent practice']),1486:('systematic_instruction',['prerequisite','small step','cumulative review','mastery check']),1487:('scripted_instruction',['teacher cue','expected response','correction','recheck']),1488:('programmed_instruction',['frame','learner response','immediate feedback','branch']),1489:('computer_assisted_instruction',['present','capture response','score','feedback','adapt'])}
def instruction(i,d):
 need(d,'objective','examples');name,phases=I[i]
 base={'instruction_model':name,'objective':d['objective'],'sequence':[{'order':n+1,'phase':p,'requires_educator_review':True} for n,p in enumerate(phases)],'examples':d['examples'],'delivered':False}
 if i==1484:
  checks=d.get('response_checks',[]);base['guided_practice_accuracy']=None if not checks else round(sum(bool(x) for x in checks)/len(checks),3);base['release_to_independent']=bool(checks) and base['guided_practice_accuracy']>=.8
 elif i==1485:
  base['explicit_checks']=[{'misconception':m,'prompt':f'Explain why {m} is not supported by the example.'} for m in d.get('misconceptions',[])]
 elif i==1486:
  steps=d.get('skill_steps',[]);base['cumulative_progression']=[{'step':x,'review':steps[:n]} for n,x in enumerate(steps,1)]
 elif i==1487:
  base['script_deviation_notes_required']=True;base['cue_response_map']=[{'cue':x.get('cue'),'expected_response':x.get('expected_response'),'correction':x.get('correction')} for x in d.get('script_turns',[])]
 elif i==1488:
  base['program_frames']=[{'frame_id':x['id'],'correct_next':x.get('correct_next'),'retry_next':x.get('retry_next')} for x in d.get('frames',[])];base['learner_paced']=True
 else:
  attempts=d.get('attempts',[]);weak=sorted(attempts,key=lambda x:(x.get('score',0),x.get('item_id','')));base['adaptive_next_item']=weak[0].get('item_id') if weak else None;base['attempt_summary']={'count':len(attempts),'mean_score':round(mean([number(x.get('score'),'attempt score',0,1) for x in attempts]),3) if attempts else None}
 return base
def tutor(i,d):
 need(d,'objective','learner_state');s=d['learner_state']
 if i==1490:
  need(d,'knowledge_components');w=min(d['knowledge_components'],key=lambda x:(x['mastery'],x['id']));return {'learner_model':d['knowledge_components'],'next_action':{'type':'worked_example' if w['mastery']<.5 else 'practice','knowledge_component_id':w['id']},'automatic_high_stakes_action':False}
 if i==1491:return {'dialogue_turn':{'response':'ask_clarifying_question','question':d.get('prompt','Can you explain your reasoning?'),'prior_turn_count':len(d.get('dialogue_history',[]))},'answer_revealed':False}
 if i==1492:
  claim=d.get('claim',s.get('answer'));return {'socratic_sequence':[f'What supports {claim}?',f'What challenges {claim}?','How would you revise?'],'claim_under_examination':claim,'direct_answer_withheld':True}
 if i==1493:return {'metacognitive_prompts':[f"Plan for {d.get('strategy','this task')}",f"Monitor with {d.get('success_measure','evidence')}",'What will you try next?'],'self_explanation_required':True}
 return {'goal':s.get('goal'),'autonomy_support':['offer meaningful choice','connect task to learner goal','process-specific encouragement'],'next_step':d.get('small_next_step'),'no_pressure_or_deception':True}
def human(i,d):
 if i==1495:
  need(d,'learner_words');return {'learner_words':d['learner_words'],'response_steps':['acknowledge without diagnosis','ask what support would help','offer trusted-human support'],'urgent_human_help_required':any(d.get('safety',{}).get(x) for x in ('self_harm','harm_to_others','immediate_danger')),'therapy_claimed':False}
 specs={1496:('competency','scenario',['name skill','model','rehearse','reflect','transfer']),1497:('virtue','dilemma',['competing values','consequences and duties','other views','justify']),1498:('civic_question','sources',['verify institutions and rights','compare sourced perspectives','deliberate','lawful participation']),1499:('global_issue','perspectives',['investigate world','recognize perspectives','communicate','responsible action']),1500:('culture','context',['self-awareness','ask rather than assume','adapt','repair']),1501:('cultures','shared_task',['prepare','structured exchange','perspective reflection','co-create','debrief'])}
 if i in specs:
  a,b,steps=specs[i];need(d,a,b);return {a:d[a],b:d[b],'learning_cycle':steps,'position_or_stereotype_imposed':False}
 need(d,'represented_groups','materials');seen={g for m in d['materials'] for g in m.get('groups',[])};return {'representation_audit':{'missing_groups':sorted(set(d['represented_groups'])-seen)},'materials':d['materials'],'single_story_review_required':True}
def inclusion(i,d):
 need(d,'learner_profile','objective');p=d['learner_profile']
 if i==1503:return {'universal_design':{'engagement':d.get('engagement_options',[]),'representation':d.get('representation_options',[]),'action_expression':d.get('expression_options',[])},'barriers':p.get('barriers',[]),'access_not_lower_expectations':True}
 if i==1504:return {'iep_alignment':{'documented_accommodations':p.get('documented_accommodations',[]),'documented_goals':p.get('documented_goals',[])},'candidate_supports':d.get('supports',[]),'eligibility_or_iep_changed':False,'specialist_team_review':True}
 if i==1505:return {'strengths':p.get('strengths',[]),'preassessment':d.get('preassessment',{}),'options':{'acceleration':d.get('acceleration',[]),'enrichment':d.get('enrichment',[]),'complexity':d.get('complexity',[])},'placement_changed':False}
 if i==1506:return {'specific_gaps':p.get('skill_gaps',[]),'reteach_sequence':['model prerequisite','guided practice','corrective feedback','independent check','cumulative review'],'progress_measure':d.get('progress_measure')}
 return {'access_barriers':p.get('access_barriers',[]),'additional_resources':d.get('resources',[]),'same_learning_expectation':True,'deficit_label_avoided':True}
def language(i,d):
 need(d,'target_language','proficiency','objectives')
 if i==1508:
  need(d,'home_language');return {'home_language':d['home_language'],'target_language':d['target_language'],'model':d.get('model','dual-language'),'language_allocation':d.get('language_allocation',{}),'objectives':d['objectives'],'home_language_treated_as_asset':True,'family_review':True}
 need(d,'items');now=d.get('day',0);out=[]
 for x in d['items']:
  q=number(x.get('quality',0),'item quality',0,5);ease=max(1.3,x.get('ease',2.5)+.1-(5-q)*(.08+(5-q)*.02));interval=1 if q<3 else max(1,round(x.get('interval',1)*ease));out.append({'item_id':x['id'],'next_day':now+interval,'interval':interval,'ease':round(ease,2),'needs_relearning':q<3})
 return {'target_language':d['target_language'],'proficiency':d['proficiency'],'objectives':d['objectives'],'spaced_repetition':out,'practice_modes':['comprehensible input','retrieval','interaction','pronunciation feedback','writing feedback'],'proficiency_claimed':False}
def education_support(i,d):
 if i not in FEATURES:raise ValueError('unsupported education feature')
 reject_direct_identifiers(d)
 sources=d.get('sources',[])
 if not sources or any(not x.get('source_id') or not x.get('observed_at') for x in sources):raise ValueError('source_id and observed_at required')
 f=analytics if i<=1462 else recommend if i<=1466 else writing if i<=1468 else assessment if i<=1479 else progress if i<=1483 else instruction if i<=1489 else tutor if i<=1494 else human if i<=1502 else inclusion if i<=1507 else language
 result=f(i,d)
 observed=sorted(k for k,v in result.items() if v not in (None,[],{}))
 return {'feature_id':i,'feature':FEATURES[i],'mechanism_key':re.sub(r'[^a-z0-9]+','_',FEATURES[i].lower()).strip('_'),'result':result,'evaluation':{'observed_outputs':observed,'review_checks':['validity for intended use','bias and subgroup performance','accessibility','learner contestability'],'open_questions':list(d.get('open_questions',[]))},'uncertainty':{'level':'not_quantified','drivers':['caller-supplied evidence','model or rubric validity','missing learner context'],'prediction_is_not_fact':i in range(1460,1467)},'sources':sources,'status':'draft_for_learner_and_qualified_teacher_review','qualified_teacher_review_required':True,'side_effects':[],'boundary':'Education decision support only. Preserve consent, privacy, accessibility and learner agency; do not infer protected traits, diagnose, award credentials, contact people, enroll, grade, punish, or change records without authorized human review.'}
