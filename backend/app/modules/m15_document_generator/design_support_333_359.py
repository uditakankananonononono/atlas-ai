"""Traceable design-workbench primitives for owner feature rows 333-359."""
from __future__ import annotations
from collections import Counter,defaultdict
from typing import Any
NAMES=["Marine Design","Toy Design","Game Design","Level Design","Puzzle Design","Mechanic Design","Economy Design","Narrative Design","Quest Design","Difficulty Balancing","Player Experience Design","Accessibility Design","Localization","Transcreation","Cultural Adaptation","Sensitivity Review","Inclusive Design","Universal Design","Participatory Design","Co-Design","Design Thinking","Design Sprint","Speculative Design","Critical Design","Adversarial Design","Transition Design","Service Design"]
FEATURES={333+i:n for i,n in enumerate(NAMES)}
PRODUCT={333,334};GAME=set(range(335,344));ACCESS=set(range(344,353));PROCESS=set(range(353,360))
DISCLAIMER="Design decision support only. Validate with domain specialists, affected people, representative users, applicable standards, physical prototypes and measured tests before release."
def _base(fid,d):
 if fid not in FEATURES:raise ValueError('feature_id must be 333-359')
 if not d.get('brief') or not d.get('decision_owner'):raise ValueError('brief and decision_owner are required')
 return {'feature_id':fid,'concept':FEATURES[fid],'brief':d['brief'],'decision_owner':d['decision_owner'],'assumptions':d.get('assumptions',[]),'unknowns':d.get('unknowns',[]),'review_required':True,'disclaimer':DISCLAIMER}
def _product(fid,d):
 o=_base(fid,d);requirements=d.get('requirements',[]);hazards=d.get('hazards',[])
 if not requirements or not hazards:raise ValueError('requirements and hazards are required')
 risks=[]
 for h in hazards:
  severity=int(h.get('severity',0));likelihood=int(h.get('likelihood',0));controls=[c for c in d.get('controls',[]) if h.get('id') in c.get('addresses',[])];risks.append({'hazard_id':h.get('id'),'severity':severity,'likelihood':likelihood,'risk_score':severity*likelihood,'control_ids':[c.get('id') for c in controls],'residual_status':'requires_test'})
 o.update({'requirements':requirements,'risk_register':risks,'controls':d.get('controls',[]),'materials':d.get('materials',[]),'environment_and_use':d.get('environment_and_use',{}),'verification_plan':d.get('verification_plan',[]),'boundary':'Concept and hazard analysis only. It is not naval architecture, stability certification, child-safety certification, manufacturing release or permission for physical use.'});return o
def _game(fid,d):
 o=_base(fid,d);loops=d.get('gameplay_loops',[]);content=d.get('content_nodes',[]);playtests=d.get('playtests',[])
 if not loops or not content:raise ValueError('gameplay_loops and content_nodes are required')
 success=[float(x.get('completion_rate',0)) for x in playtests if 'completion_rate' in x];times=[float(x.get('duration_minutes',0)) for x in playtests if 'duration_minutes' in x]
 economy=d.get('economy',{});sources=sum(float(x.get('amount',0)) for x in economy.get('sources',[]));sinks=sum(float(x.get('amount',0)) for x in economy.get('sinks',[]))
 o.update({'gameplay_loops':loops,'content_nodes':content,'mechanics':d.get('mechanics',[]),'narrative_or_quests':d.get('narrative_or_quests',[]),'balance_metrics':{'mean_completion_rate':sum(success)/len(success) if success else None,'mean_duration_minutes':sum(times)/len(times) if times else None,'currency_net':sources-sinks},'player_segments':d.get('player_segments',[]),'accessibility_options':d.get('accessibility_options',[]),'boundary':'Prototype model, not proof of fun, fairness, learning or accessibility. Designers validate exploits, difficulty, retention pressure, monetization harms, age fit and diverse player experience through consented playtesting.'});return o
def _access(fid,d):
 o=_base(fid,d);participants=d.get('participants',[]);needs=d.get('needs',[]);variants=d.get('variants',[])
 if not participants or not needs or not variants:raise ValueError('participants, needs and variants are required')
 coverage=[]
 for n in needs:
  matches=[v.get('id') for v in variants if n.get('id') in v.get('addresses',[])];coverage.append({'need_id':n.get('id'),'variant_ids':matches,'status':'covered_for_testing' if matches else 'gap'})
 locales=[]
 for loc in d.get('locales',[]):
  missing=[k for k in d.get('required_message_keys',[]) if k not in loc.get('messages',{})];locales.append({'locale':loc.get('locale'),'missing_keys':missing,'status':'incomplete' if missing else 'ready_for_linguist_review'})
 o.update({'participants':participants,'needs':needs,'variants':variants,'coverage':coverage,'locales':locales,'cultural_notes':d.get('cultural_notes',[]),'sensitivity_findings':d.get('sensitivity_findings',[]),'consent_and_compensation':d.get('consent_and_compensation',{}),'decision_log':d.get('decision_log',[]),'boundary':'Inclusive design draft, not a claim of universal access or cultural approval. Disabled users, language experts and represented communities retain authority; participation requires consent, access and fair compensation.'});return o
def _process(fid,d):
 o=_base(fid,d);stakeholders=d.get('stakeholders',[]);evidence=d.get('evidence',[]);ideas=d.get('ideas',[])
 if not stakeholders or not evidence or not ideas:raise ValueError('stakeholders, evidence and ideas are required')
 scores=[]
 criteria=d.get('criteria',[])
 for idea in ideas:
  values=idea.get('scores',{});missing=[c.get('id') for c in criteria if c.get('id') not in values];scores.append({'idea_id':idea.get('id'),'scores':values,'missing_criteria':missing,'weighted_score':None if missing else sum(float(values[c['id']])*float(c.get('weight',1)) for c in criteria)})
 o.update({'stakeholders':stakeholders,'evidence':evidence,'ideas':scores,'criteria':criteria,'prototype_plan':d.get('prototype_plan',[]),'tests':d.get('tests',[]),'future_scenarios':d.get('future_scenarios',[]),'critique_or_abuse_cases':d.get('critique_or_abuse_cases',[]),'transition_pathways':d.get('transition_pathways',[]),'service_blueprint':d.get('service_blueprint',[]),'boundary':'Facilitation and comparison aid only. A sprint is not validation; speculative, critical and adversarial concepts are not forecasts or attack authorization. Stakeholders approve framing, tests, decisions and transition/service changes.'});return o
def design_support_333_359(fid:int,data:dict[str,Any])->dict[str,Any]:
 if fid in PRODUCT:return _product(fid,data)
 if fid in GAME:return _game(fid,data)
 if fid in ACCESS:return _access(fid,data)
 if fid in PROCESS:return _process(fid,data)
 raise ValueError('feature_id must be 333-359')
