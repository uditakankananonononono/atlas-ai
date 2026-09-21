"""Atomic executive-function concepts 70-92, evidence-driven and non-autonomous."""
from __future__ import annotations
from datetime import date,timedelta
from math import exp
from typing import Any
ROWS=['17.2','19.1','19.2','19.3','20.1','20.2','21.1','21.2','22.1','22.2','27.1','27.2','32.1','32.2','33.1','33.2','36.1','36.2','46.1','46.2','47.1','47.2','50.1']
NAMES=['Flow-preserving work restructuring','Bias detection in system reasoning','Bias detection in user-supplied inputs','Bias mitigation/correction recommendation','Fast time-critical intuition candidate','Slow-reasoning validation of intuition','Concurrent competing world-model storage','Evidence-based world-model update','Sub-goal/terminal-value conflict detection','Goal-hierarchy restructuring proposal','Planning-depth adaptation to uncertainty','Planning-depth adaptation to time available','Belief formation-time tracking','Periodic belief-review scheduling','Knowledge staleness prediction','Knowledge refresh scheduling','Fleeting-idea capture','Captured-idea development workflow','Multiple plausible future generation','Strategy generation for each plausible future','Project-failure pre-mortem scenario','Backward failure-prevention plan','Feedback-loop recognition']
FEATURES=dict(zip(ROWS,NAMES));SOURCES={'bias':'https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.Sp.1270.pdf','scenario':'https://sloanreview.mit.edu/article/using-scenario-planning-to-reshape-strategy/','premortem':'https://homepages.se.edu/cvonbergen/files/2013/01/Performing-a-Project-Premortem.pdf','spacing':'https://pmc.ncbi.nlm.nih.gov/articles/PMC6410796/'}
class AtomicError(ValueError):pass
def _base(r,d):
 if r not in FEATURES:raise AtomicError('atomic_row_id must be assigned')
 return {'atomic_row_id':r,'concept':FEATURES[r],'inputs_used':sorted(d),'assumptions':d.get('assumptions',[]),'review_required':True}
def run(r:str,d:dict[str,Any])->dict[str,Any]:
 o=_base(r,d)
 if r=='17.2':
  tasks=d.get('tasks',[]);skill=float(d.get('skill',0));
  if not tasks or not 0<=skill<=10:raise AtomicError('tasks and skill [0,10] required')
  ranked=sorted(({**x,'challenge_gap':abs(float(x['challenge'])-skill)} for x in tasks),key=lambda x:x['challenge_gap']);o['result']={'sequence':[x['id'] for x in ranked],'next_task':ranked[0]['id'],'protected_block_minutes':min(90,max(25,int(d.get('available_minutes',50)))),'interruptions_batched':True}
 elif r in ('19.1','19.2'):
  claims=d.get('claims',[])
  if not claims:raise AtomicError('claims required')
  flags=[]
  for c in claims:
   reasons=[]
   if c.get('considered_alternatives',0)==0:reasons.append('confirmation-risk')
   if c.get('base_rate') is None:reasons.append('base-rate-omission')
   if c.get('sample_size',0)<d.get('minimum_sample',30):reasons.append('small-sample-risk')
   flags.append({'claim_id':c.get('id'),'signals':reasons,'not_a_bias_diagnosis':True})
  o['result']={'scope':'system_reasoning' if r=='19.1' else 'user_input','flags':flags,'source_url':SOURCES['bias']}
 elif r=='19.3':
  flags=d.get('flags',[])
  if not flags:raise AtomicError('flags required')
  map={'confirmation-risk':'actively seek disconfirming evidence','base-rate-omission':'add a relevant reference class','small-sample-risk':'collect more data or widen uncertainty'};o['result']={'recommendations':[{'signal':x,'correction':map.get(x,'independent review')} for x in flags],'automatic_rewrite':False,'source_url':SOURCES['bias']}
 elif r in ('20.1','20.2'):
  opts=d.get('options',[])
  if len(opts)<2:raise AtomicError('at least two options required')
  fast=sorted(opts,key=lambda x:(-float(x.get('salience',0)),x['id']))[0]
  if r=='20.1':o['result']={'candidate':fast['id'],'basis':'salience heuristic','confidence':'unvalidated','must_validate':True}
  else:
   criteria=d.get('criteria',[])
   if not criteria:raise AtomicError('criteria required')
   scores={x['id']:sum(float(x.get('scores',{}).get(c['id'],0))*float(c.get('weight',1)) for c in criteria) for x in opts};best=max(scores,key=scores.get);o['result']={'intuition_candidate':fast['id'],'analytic_scores':scores,'validated_choice':best,'intuition_confirmed':best==fast['id']}
 elif r in ('21.1','21.2'):
  models=d.get('models',[])
  if len(models)<2:raise AtomicError('competing models required')
  if r=='21.1':o['result']={'models':[{'id':m['id'],'prior':float(m['prior']),'falsifier':m.get('falsifier')} for m in models],'normalized':abs(sum(float(m['prior']) for m in models)-1)<1e-9}
  else:
   ev=d.get('evidence',{});lik=ev.get('likelihood_by_model',{});raw={m['id']:float(m['prior'])*float(lik.get(m['id'],0)) for m in models};z=sum(raw.values())
   if z<=0:raise AtomicError('evidence has zero support under every model')
   o['result']={'posteriors':{k:v/z for k,v in raw.items()},'evidence_id':ev.get('id'),'winner':max(raw,key=raw.get),'models_retained':True}
 elif r in ('22.1','22.2'):
  values=d.get('terminal_values',[]);goals=d.get('subgoals',[])
  if not values or not goals:raise AtomicError('terminal_values and subgoals required')
  conflicts=[{'subgoal_id':g['id'],'value_ids':sorted(set(g.get('violates',[]))&set(values))} for g in goals if set(g.get('violates',[]))&set(values)]
  if r=='22.1':o['result']={'conflicts':conflicts,'terminal_values_immutable_by_engine':True}
  else:o['result']={'proposal':[{'replace':x['subgoal_id'],'with':next((g.get('alternative') for g in goals if g['id']==x['subgoal_id']),None),'preserves_values':not bool(x['value_ids'])} for x in conflicts],'applied':False}
 elif r in ('27.1','27.2'):
  u=float(d.get('uncertainty',-1));minutes=int(d.get('minutes',-1))
  if not 0<=u<=1 or minutes<=0:raise AtomicError('uncertainty [0,1] and positive minutes required')
  depth=max(1,min(10,round((1-u)*8+minutes/30)));o['result']={'planning_depth':depth,'uncertainty':u,'minutes':minutes,'policy':'shallower under uncertainty/time pressure; add checkpoints' if r=='27.1' else 'fit depth to available deliberation window','checkpoint_required':u>.5}
 elif r in ('32.1','32.2','33.1','33.2'):
  beliefs=d.get('beliefs',[]);today=date.fromisoformat(d.get('today'))
  if not beliefs:raise AtomicError('beliefs required')
  rows=[]
  for b in beliefs:
   formed=date.fromisoformat(b['formed_at']);vol=float(b.get('volatility',.2));conf=float(b.get('confidence',.5));interval=max(1,round(180*(1-vol)*(0.5+conf)));review=formed+timedelta(days=interval);stale=1-exp(-max(0,(today-formed).days)*max(vol,.01)/180);rows.append({'id':b['id'],'formed_at':str(formed),'predicted_staleness':round(stale,4),'review_on':str(review),'overdue':today>=review})
  o['result']={'beliefs':rows,'schedule_generated':r in ('32.2','33.2'),'model':'volatility/confidence interval heuristic','source_url':SOURCES['spacing']}
 elif r in ('36.1','36.2'):
  text=str(d.get('idea','')).strip()
  if len(text)<3:raise AtomicError('nontrivial idea required')
  capture={'idea':text,'captured_at':d.get('captured_at'),'context':d.get('context'),'open_questions':d.get('open_questions',[])}
  o['result']=capture if r=='36.1' else {**capture,'development':{'claim':d.get('claim'),'smallest_test':d.get('smallest_test'),'next_action':d.get('next_action'),'status':'draft'}}
 elif r in ('46.1','46.2'):
  drivers=d.get('drivers',[])
  if len(drivers)<2 or any(len(x.get('states',[]))<2 for x in drivers[:2]):raise AtomicError('two drivers with at least two states required')
  scenarios=[]
  for a in drivers[0]['states']:
   for b in drivers[1]['states']:
    scenarios.append({'id':f'{a}-{b}','conditions':{drivers[0]['id']:a,drivers[1]['id']:b},'plausibility':'not_probability'})
  o['result']={'scenarios':scenarios,'source_url':SOURCES['scenario']} if r=='46.1' else {'strategies':[{'scenario_id':s['id'],'no_regret':d.get('no_regret_actions',[]),'contingent':d.get('contingent_actions',{}).get(s['id'],[]),'trigger':d.get('triggers',{}).get(s['id'])} for s in scenarios],'source_url':SOURCES['scenario']}
 elif r in ('47.1','47.2'):
  failure=d.get('failure_story');causes=d.get('causes',[])
  if not failure or not causes:raise AtomicError('failure_story and causes required')
  if r=='47.1':o['result']={'assumed_failure':failure,'causes':causes,'prospective_hindsight':True,'source_url':SOURCES['premortem']}
  else:o['result']={'preventions':[{'cause_id':c['id'],'leading_indicator':c.get('leading_indicator'),'mitigation':c.get('mitigation'),'owner':c.get('owner'),'due':c.get('due'),'status':'proposed'} for c in causes],'applied':False,'source_url':SOURCES['premortem']}
 else:
  nodes=d.get('nodes',[]);edges=d.get('edges',[])
  if not nodes or not edges:raise AtomicError('nodes and signed causal edges required')
  adj={n:[] for n in nodes}
  for e in edges:
   if e.get('sign') not in (-1,1) or e.get('from') not in adj or e.get('to') not in adj:raise AtomicError('valid signed edges required')
   adj[e['from']].append(e)
  loops=[]
  for start in nodes:
   for e in adj[start]:
    for back in adj[e['to']]:
     if back['to']==start:loops.append({'nodes':[start,e['to'],start],'polarity':'reinforcing' if e['sign']*back['sign']>0 else 'balancing','delay_present':bool(e.get('delay') or back.get('delay'))})
  o['result']={'loops':loops,'emergent_behavior_not_proven':True}
 return o
