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
 return {'feature_id':fid,'concept':FEATURES[fid],'brief':d['brief'],'decision_owner':d['decision_owner'],'assumptions':d.get('assumptions',[]),'unknowns':d.get('unknowns',[]),'review_required':True,'evaluation':{'acceptance_criteria':d.get('acceptance_criteria',[]),'verification_plan':d.get('verification_plan',[]),'affected_people_review':d.get('affected_people_review',[])},'uncertainty':{'level':'not_quantified','drivers':['prototype not executed','participant and context variation','open unknowns'],'release_or_safety_claimed':False},'disclaimer':DISCLAIMER}
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

def _distinctive(fid:int,d:dict[str,Any],o:dict[str,Any])->dict[str,Any]:
 """Attach the method-specific decision instrument for each design discipline."""
 if fid==333:
  disp=float(d.get('displacement_kg',0));vol=float(d.get('hull_volume_m3',0));o['marine_stability']={'displacement_kg':disp,'buoyancy_margin_kg':vol*1000-disp,'positive_margin':vol*1000>disp}
 elif fid==334:
  ages=d.get('age_range',[0,0]);parts=d.get('parts',[]);o['toy_safety']={'age_range':ages,'small_part_count':sum(float(x.get('diameter_mm',99))<31.7 for x in parts),'play_cycle_count':len(d.get('play_cycles',[]))}
 elif fid==335:o['game_system']={'core_loop_minutes':d.get('core_loop_minutes'),'verbs':d.get('player_verbs',[]),'loop_to_goal_links':d.get('loop_to_goal_links',[])}
 elif fid==336:o['level_flow']={'critical_path':d.get('critical_path',[]),'optional_nodes':d.get('optional_nodes',[]),'checkpoint_gap_max':max(d.get('checkpoint_gaps_minutes',[0]))}
 elif fid==337:o['puzzle_model']={'givens':d.get('givens',[]),'inference_steps':d.get('inference_steps',[]),'solution_count':d.get('solution_count'),'unique_solution':d.get('solution_count')==1}
 elif fid==338:o['mechanic_model']={'inputs':d.get('inputs',[]),'state_changes':d.get('state_changes',[]),'feedback_latency_ms':d.get('feedback_latency_ms'),'counterplay':d.get('counterplay',[])}
 elif fid==339:o['economy_model']={'source_total':sum(float(x.get('amount',0)) for x in d.get('economy',{}).get('sources',[])),'sink_total':sum(float(x.get('amount',0)) for x in d.get('economy',{}).get('sinks',[])),'inflation_controls':d.get('inflation_controls',[])}
 elif fid==340:o['narrative_graph']={'beats':d.get('beats',[]),'choice_consequences':d.get('choice_consequences',[]),'unresolved_threads':d.get('unresolved_threads',[])}
 elif fid==341:o['quest_graph']={'prerequisites':d.get('prerequisites',{}),'rewards':d.get('rewards',{}),'failure_recovery':d.get('failure_recovery',[])}
 elif fid==342:o['difficulty_curve']={'target':d.get('target_success_rates',[]),'observed':[x.get('completion_rate') for x in d.get('playtests',[])],'adaptive_bounds':d.get('adaptive_bounds')}
 elif fid==343:o['experience_journey']={'moments':d.get('moments',[]),'emotion_samples':d.get('emotion_samples',[]),'friction_points':d.get('friction_points',[])}
 elif fid==344:o['accessibility_audit']={'modalities':d.get('modalities',[]),'wcag_checks':d.get('wcag_checks',[]),'assistive_tech_tests':d.get('assistive_tech_tests',[])}
 elif fid==345:o['localization_qa']={'locale_count':len(d.get('locales',[])),'expansion_budget_percent':d.get('expansion_budget_percent'),'pseudo_localization':bool(d.get('pseudo_localization'))}
 elif fid==346:o['transcreation_matrix']={'source_intent':d.get('source_intent'),'locale_variants':d.get('locale_variants',[]),'back_translation_checks':d.get('back_translation_checks',[])}
 elif fid==347:o['cultural_adaptation']={'context_inventory':d.get('cultural_contexts',[]),'community_reviewers':d.get('community_reviewers',[]),'adaptation_decisions':d.get('adaptation_decisions',[])}
 elif fid==348:o['sensitivity_register']={'findings':d.get('sensitivity_findings',[]),'represented_reviewer_count':len(d.get('represented_reviewers',[])),'unresolved_count':sum(x.get('status')!='resolved' for x in d.get('sensitivity_findings',[]))}
 elif fid==349:o['inclusion_matrix']={'excluded_scenarios':d.get('excluded_scenarios',[]),'need_coverage_ratio':sum(x['status']!='gap' for x in o['coverage'])/len(o['coverage']) if o['coverage'] else None}
 elif fid==350:o['universal_principles']={'equitable_use':d.get('equitable_use',[]),'tolerance_for_error':d.get('tolerance_for_error',[]),'low_effort':d.get('low_effort',[])}
 elif fid==351:o['participation_plan']={'power_map':d.get('power_map',[]),'decision_rights':d.get('decision_rights',[]),'compensation':d.get('consent_and_compensation',{})}
 elif fid==352:o['codesign_trace']={'participant_ideas':d.get('participant_ideas',[]),'adopted':d.get('adopted_ideas',[]),'rejection_reasons':d.get('rejection_reasons',{})}
 elif fid==353:o['design_thinking_cycle']={'empathy_evidence':d.get('evidence',[]),'problem_statement':d.get('problem_statement'),'prototype_plan':d.get('prototype_plan',[]),'test_learning':d.get('test_learning',[])}
 elif fid==354:o['sprint_board']={'days':d.get('sprint_days',[]),'decider':d.get('decider'),'prototype_scope':d.get('prototype_plan',[]),'test_participants':d.get('test_participants',[])}
 elif fid==355:o['speculative_scenarios']={'signals':d.get('signals',[]),'axes':d.get('uncertainty_axes',[]),'scenarios':d.get('future_scenarios',[]),'not_forecast':True}
 elif fid==356:o['critical_provocation']={'assumption_challenged':d.get('assumption_challenged'),'artifact':d.get('provocation'),'discussion_questions':d.get('discussion_questions',[])}
 elif fid==357:o['adversarial_review']={'abuse_cases':d.get('critique_or_abuse_cases',[]),'threat_actors':d.get('threat_actors',[]),'mitigations':d.get('mitigations',[]),'authorization_required':True}
 elif fid==358:o['transition_portfolio']={'horizons':d.get('horizons',[]),'pathways':d.get('transition_pathways',[]),'lock_in_risks':d.get('lock_in_risks',[]),'leading_indicators':d.get('leading_indicators',[])}
 elif fid==359:
  bp=d.get('service_blueprint',[]);o['service_blueprint_analysis']={'steps':bp,'handoff_count':sum(bool(x.get('handoff')) for x in bp),'frontstage_backstage_gaps':[x.get('id') for x in bp if not x.get('frontstage') or not x.get('backstage')]}
 o['method_engine']=FEATURES[fid].lower().replace(' ','_');return o

_original_design_support=design_support_333_359
def design_support_333_359(fid:int,data:dict[str,Any])->dict[str,Any]:
 return _distinctive(fid,data,_original_design_support(fid,data))
