"""Transparent social-research design and analysis for ledger rows 1710-1759.

All methods preserve provenance and uncertainty. They produce research artifacts, never
claim causal or population conclusions beyond the supplied design and evidence.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from math import ceil, sqrt
import re
from typing import Any

class SocialResearchError(ValueError): pass

ROWS={1710:'Survey Design',1711:'Questionnaire Construction',1712:'Sampling Methods',1713:'Probability Sampling',1714:'Non-Probability Sampling',1715:'Sample Size Determination',1716:'Response Rate Improvement',1717:'Survey Mode Effects',1718:'Interview Design',1719:'Focus Group Design',1720:'Ethnography',1721:'Participant Observation',1722:'Field Research',1723:'Case Study Design',1724:'Comparative Research',1725:'Cross-Cultural Research',1726:'Longitudinal Research',1727:'Panel Studies',1728:'Cohort Studies',1729:'Time Series Analysis',1730:'Content Analysis',1731:'Discourse Analysis',1732:'Conversation Analysis',1733:'Narrative Analysis',1734:'Thematic Analysis',1735:'Grounded Theory',1736:'Phenomenology',1737:'Hermeneutics',1738:'Semiotics',1739:'Structuralism',1740:'Post-Structuralism',1741:'Critical Theory',1742:'Feminist Theory',1743:'Queer Theory',1744:'Critical Race Theory',1745:'Postcolonial Theory',1746:'Actor-Network Theory',1747:'Social Network Analysis',1748:'Organizational Analysis',1749:'Institutional Analysis',1750:'Political Economy',1751:'Public Choice',1752:'Rational Choice',1753:'Game Theory',1754:'Bargaining Theory',1755:'Coalition Theory',1756:'Voting Theory',1757:'Social Choice',1758:'Collective Action',1759:'Social Movements'}
def slug(s:str)->str:return re.sub(r'[^a-z0-9]+','_',s.lower()).strip('_')
KEYS={slug(v):k for k,v in ROWS.items()}
FAMILY={**{i:'survey' for i in range(1710,1720)},**{i:'field' for i in range(1720,1726)},**{i:'longitudinal' for i in range(1726,1730)},**{i:'interpretive' for i in range(1730,1747)},**{i:'systems' for i in range(1747,1760)}}

def capabilities():return [{'row_id':i,'key':slug(n),'name':n,'family':FAMILY[i]} for i,n in ROWS.items()]
def req(p,k,t):
 v=p.get(k)
 if not isinstance(v,t) or (t in (str,list,dict) and not v):raise SocialResearchError(f'{k} must be a non-empty {t.__name__}')
 return v
def source(p):
 s=req(p,'source',dict); title=s.get('title');url=s.get('url')
 if not title or not isinstance(url,str) or not url.startswith(('http://','https://')):raise SocialResearchError('source requires title and http(s) url')
 return {'title':str(title),'url':url}
def ethics(p):
 e=p.get('ethics',{})
 if not isinstance(e,dict):raise SocialResearchError('ethics must be an object')
 return {'consent':bool(e.get('consent',False)),'withdrawal':bool(e.get('withdrawal',False)),'data_minimization':bool(e.get('data_minimization',False)),'risk_review':e.get('risk_review','required before collection')}

def survey(row,p):
 population=req(p,'population',dict); question=str(p.get('research_question','')).strip()
 if not question:raise SocialResearchError('research_question is required')
 out={'research_question':question,'population':population,'ethics':ethics(p)}
 if row in (1710,1711):
  qs=req(p,'questions',list); reviewed=[]
  for i,q in enumerate(qs):
   if isinstance(q,str):q={'text':q,'type':'open'}
   if not isinstance(q,dict) or not q.get('text'):raise SocialResearchError(f'questions[{i}] needs text')
   text=q['text']; flags=[]
   if re.search(r'\b(always|never|everyone|obviously)\b',text,re.I):flags.append('absolute_or_leading_language')
   if re.search(r'\band\b',text,re.I) and q.get('type')!='open':flags.append('possible_double_barrel')
   reviewed.append({'id':q.get('id',f'q{i+1}'),'text':text,'type':q.get('type','open'),'required':bool(q.get('required',False)),'flags':flags,'response_options':q.get('response_options',[])})
  out['questionnaire']=reviewed;out['pilot_plan']=['cognitive interviews','soft launch','item nonresponse review']
 if row in (1712,1713,1714):
  frame=p.get('sampling_frame',[]); method=p.get('method','simple_random' if row==1713 else 'purposive' if row==1714 else 'stratified')
  probability=method in {'simple_random','systematic','stratified','cluster'}
  out['sampling_plan']={'method':method,'probability_sample':probability,'frame_size':len(frame) if isinstance(frame,list) else None,'selection_probability_required':probability,'generalization':('design-based estimates possible with weights and coverage review' if probability else 'analytic transfer only; no population prevalence claim')}
 if row==1715:
  z=float(p.get('z',1.96));margin=float(p.get('margin_error',.05));prop=float(p.get('expected_proportion',.5));deff=float(p.get('design_effect',1));response=float(p.get('expected_response_rate',1))
  if not (0<margin<1 and 0<response<=1 and 0<=prop<=1 and z>0 and deff>=1):raise SocialResearchError('invalid sample-size parameters')
  base=z*z*prop*(1-prop)/(margin*margin); target=ceil(base*deff);out['sample_size']={'completed_needed':target,'invitations_needed':ceil(target/response),'assumptions':{'z':z,'margin_error':margin,'expected_proportion':prop,'design_effect':deff,'response_rate':response}}
 if row==1716:out['response_plan']={'contact_sequence':['prenotice','invitation','nonresponse reminder','final reminder'],'supports':['mobile-friendly','plain language','accessible format'],'prohibited':['coercion','misleading urgency'],'monitor_by_group_without_targeting_protected_traits':True}
 if row==1717:out['mode_effects']=[{'mode':m,'coverage':v.get('coverage'),'social_desirability_risk':v.get('social_desirability_risk'),'measurement_difference':'estimate with randomized bridge or calibration sample'} for m,v in p.get('modes',{}).items()]
 if row==1718:out['interview_guide']={'opening':['consent reminder','permission to record'],'core':p.get('topics',[]),'probes':['Can you give an example?','What happened next?','How did that affect you?'],'closing':['Anything missed?','withdrawal and contact reminder']}
 if row==1719:out['focus_group']={'composition':p.get('composition',{}),'size':p.get('size',6),'roles':['moderator','note taker'],'protocol':['consent','no guaranteed peer confidentiality','round-robin opening','topic prompts','member summary'],'analysis_unit':'interaction as well as individual statements'}
 return out

def field(row,p):
 question=req(p,'research_question',str);sites=req(p,'sites',list);out={'research_question':question,'sites':sites,'ethics':ethics(p),'reflexivity':{'researcher_position':p.get('researcher_position'),'assumptions_to_monitor':p.get('assumptions',[]),'field_decisions_log':True}}
 if row==1720:out['ethnographic_plan']={'immersion_schedule':p.get('schedule',[]),'fieldnotes':['descriptive','analytic','reflexive'],'emic_and_etic_accounts':True,'member_reflection_not_validation_claim':True}
 if row==1721:out['observation_protocol']={'role':p.get('role','observer-as-participant'),'dimensions':['setting','actors','activities','interactions','time'],'jottings_to_expanded_notes_deadline_hours':24,'no_covert_observation_without_ethics_approval':True}
 if row==1722:out['field_plan']={'access':p.get('access_plan'),'safety':p.get('safety_plan'),'contingencies':p.get('contingencies',[]),'daily_backup_and_deidentification':True}
 if row==1723:out['case_design']={'case_boundary':req(p,'case_boundary',dict),'case_type':p.get('case_type','instrumental'),'evidence_sources':p.get('evidence_sources',[]),'triangulation_matrix':True,'rival_explanations_required':True}
 if row==1724:out['comparison']={'cases':sites,'dimensions':p.get('dimensions',[]),'most_similar_or_different':p.get('logic','most_similar'),'case_selection_rationale':p.get('selection_rationale'),'avoid_variable_stretching':True}
 if row==1725:out['cross_cultural']={'constructs':p.get('constructs',[]),'translation':['forward translation','independent back translation','reconciliation','cognitive testing'],'measurement_invariance_required_before_mean_comparison':True,'local_collaborator_review':True,'avoid_cultural_deficit_framing':True}
 return out

def longitudinal(row,p):
 observations=req(p,'observations',list);clean=[]
 for i,o in enumerate(observations):
  if not isinstance(o,dict) or 'time' not in o or 'value' not in o:raise SocialResearchError(f'observations[{i}] needs time and value')
  clean.append({'id':o.get('id'),'time':o['time'],'value':float(o['value']),'group':o.get('group')})
 out={'observations':clean,'count':len(clean),'attrition_warning':'compare retained and lost participants; weight/sensitivity analyses require justified assumptions'}
 if row==1726:out['design']={'waves':sorted({str(x['time']) for x in clean}),'stable_measurement':True,'time_varying_confounders_review':True}
 if row==1727:
  by=defaultdict(int)
  for x in clean:by[x['id']]+=1
  out['panel_retention']={'participants':len(by),'complete_cases':sum(v==len({str(x['time']) for x in clean}) for v in by.values())}
 if row==1728:out['cohort_design']={'entry_definition':p.get('entry_definition'),'exposure_definition':p.get('exposure_definition'),'outcome_definition':p.get('outcome_definition'),'immortal_time_bias_check':True}
 if row==1729:
  vals=[x['value'] for x in clean];out['time_series']={'first_difference':[round(vals[i]-vals[i-1],6) for i in range(1,len(vals))],'mean':sum(vals)/len(vals),'intervention_time':p.get('intervention_time'),'checks':['trend','seasonality','autocorrelation','structural breaks'],'causal_claim_requires_identification_strategy':True}
 return out

def interpretive(row,p):
 texts=req(p,'texts',list); corpus=[]
 for i,x in enumerate(texts):
  if isinstance(x,str):x={'id':f't{i+1}','text':x}
  if not isinstance(x,dict) or not x.get('text'):raise SocialResearchError(f'texts[{i}] needs text')
  corpus.append({'id':x.get('id',f't{i+1}'),'text':x['text'],'speaker':x.get('speaker'),'context':x.get('context')})
 tokens=[re.findall(r"[a-z']+",x['text'].lower()) for x in corpus];freq=Counter(w for t in tokens for w in t)
 out={'corpus_count':len(corpus),'provenance':[{'id':x['id'],'context':x['context']} for x in corpus],'interpretations_are_situated':True}
 if row==1730:out['content_analysis']={'codebook':p.get('codebook',[]),'top_terms':freq.most_common(10),'unit_of_analysis':p.get('unit','document'),'double_code_and_reconcile':True}
 if row==1731:out['discourse_analysis']={'questions':['How is the subject positioned?','What is made sayable or unsayable?','Which institutions authorize claims?'],'linguistic_features':['modality','agency','nominalization','presupposition'],'historical_context_required':True}
 if row==1732:out['conversation_analysis']={'transcription':'turns, pauses, overlap, repair and prosody','sequence_focus':['adjacency pairs','preference organization','repair'],'do_not_reduce_to_word_counts':True}
 if row==1733:out['narrative_analysis']={'elements':['orientation','complicating action','evaluation','resolution','coda'],'temporality_and_telling_context':True,'preserve_counter_narratives':True}
 if row==1734:out['thematic_analysis']={'phases':['familiarize','code','generate themes','review themes','define/name','report'],'candidate_codes':p.get('codes',freq.most_common(8)),'negative_cases_required':True}
 if row==1735:out['grounded_theory']={'cycle':['initial coding','constant comparison','focused coding','theoretical sampling','memoing','category integration'],'theoretical_saturation':'document evidence; never claim from count alone','prior_theory_as_sensitizing_not_forcing':True}
 if row==1736:out['phenomenology']={'focus':'lived experience and meaning','steps':['bracket assumptions','significant statements','meaning units','textural description','structural description','synthesis'],'no_clinical_inference':True}
 if row==1737:out['hermeneutics']={'circle':['parts inform whole','whole reframes parts'],'horizon_and_preunderstanding':p.get('preunderstanding'),'alternative_readings_required':True}
 if row==1738:out['semiotics']={'signs':[{'signifier':s.get('signifier'),'signified':s.get('signified'),'code':s.get('code'),'denotation':s.get('denotation'),'connotation':s.get('connotation')} for s in p.get('signs',[])],'relations':['icon','index','symbol'],'context_changes_meaning':True}
 if row in (1739,1740):out['structure_reading']={'binary_oppositions':p.get('binary_oppositions',[]),'relations_over_isolated_elements':True,'instability_and_difference':row==1740,'authoritative_final_meaning':False}
 lenses={1741:('ideology','power','domination','emancipatory possibility'),1742:('gendered power','standpoint','intersectionality','care and labor'),1743:('heteronormativity','performativity','category instability','resistance'),1744:('racialization','structural racism','interest convergence','counter-story'),1745:('coloniality','orientalism','hybridity','subaltern voice'),1746:('human and nonhuman actors','translation','enrollment','obligatory passage points')}
 if row in lenses:out['theoretical_lens']={'concepts':list(lenses[row]),'questions':[f'How does {x} shape this material?' for x in lenses[row]],'avoid_totalizing_explanation':True,'positionality_required':True}
 return out

def systems(row,p):
 actors=req(p,'actors',list);out={'actors':actors,'assumptions':p.get('assumptions',[]),'sensitivity_required':True,'descriptive_not_deterministic':True}
 if row==1747:
  edges=req(p,'edges',list);names={str(a.get('id',a)) if isinstance(a,dict) else str(a) for a in actors};deg={n:0 for n in names}
  for e in edges:
   if e.get('source') not in names or e.get('target') not in names:raise SocialResearchError('edge references unknown actor')
   deg[e['source']]+=1;deg[e['target']]+=1
  out['network']={'nodes':len(names),'edges':len(edges),'degree':deg,'density':(len(edges)/(len(names)*(len(names)-1)/2) if len(names)>1 else 0),'missing_ties_are_not_absent_ties':True}
 if row==1748:out['organization']={'levels':['individual','team','organization','field'],'structure':p.get('structure',{}),'processes':p.get('processes',[]),'informal_vs_formal_gap':True}
 if row==1749:out['institutions']={'rules':p.get('rules',[]),'pillars':['regulative','normative','cultural-cognitive'],'isomorphism':['coercive','mimetic','normative'],'path_dependence_review':True}
 if row==1750:out['political_economy']={'resources':p.get('resources',[]),'ownership':p.get('ownership',[]),'institutions':p.get('institutions',[]),'distributional_impacts':p.get('distributional_impacts',[]),'power_not_reduced_to_price':True}
 if row in (1751,1752):out['choice_model']={'preferences':p.get('preferences',{}),'constraints':p.get('constraints',{}),'information':p.get('information','incomplete'),'predictions':p.get('predictions',[]),'bounded_rationality_alternative_required':True,'preferences_are_assumptions_not_observations':True}
 if row==1753:
  games=req(p,'payoffs',dict);out['game']={'players':list(games),'payoffs':games,'information':p.get('information','complete'),'timing':p.get('timing','simultaneous'),'equilibrium_candidates':p.get('equilibrium_candidates',[]),'equilibrium_is_not_moral_endorsement':True}
 if row==1754:out['bargaining']={'reservation_values':p.get('reservation_values',{}),'outside_options':p.get('outside_options',{}),'bargaining_power':p.get('bargaining_power',{}),'zone_of_possible_agreement_requires_verified_values':True}
 if row==1755:out['coalitions']={'winning_threshold':p.get('winning_threshold'),'weights':p.get('weights',{}),'candidate_coalitions':p.get('candidate_coalitions',[]),'stability_concept':p.get('stability_concept','core'),'ideology_and_commitment_not_assumed_away':True}
 if row==1756:
  ballots=req(p,'ballots',list);counts=Counter(str(b.get('choice')) for b in ballots if b.get('choice') is not None);out['voting']={'plurality_counts':dict(counts),'winner':(max(counts,key=counts.get) if counts else None),'rule':p.get('rule','plurality'),'turnout_denominator_required_for_turnout_claim':True,'audit_trail':True}
 if row==1757:out['social_choice']={'individual_rankings':p.get('rankings',[]),'aggregation_rule':p.get('rule'),'criteria':['unrestricted domain','pareto efficiency','independence','non-dictatorship'],'impossibility_tradeoffs_disclosed':True}
 if row==1758:out['collective_action']={'shared_goal':p.get('shared_goal'),'public_good':p.get('public_good'),'free_rider_risk':p.get('free_rider_risk'),'mechanisms':['selective incentives','repeated interaction','norms','monitoring','graduated sanctions'],'coercion_review':True}
 if row==1759:out['movement']={'claims':p.get('claims',[]),'mobilizing_structures':p.get('mobilizing_structures',[]),'political_opportunities':p.get('political_opportunities',[]),'frames':p.get('frames',[]),'repertoires':p.get('repertoires',[]),'countermovements_and_repression':p.get('countermovements_and_repression',[]),'do_not_equate_online_visibility_with_support':True}
 return out

def execute(method:str,payload:dict[str,Any]):
 key=slug(method);row=KEYS.get(key)
 if row is None:raise SocialResearchError(f'unknown method: {method}')
 if not isinstance(payload,dict):raise SocialResearchError('payload must be an object')
 src=source(payload);family=FAMILY[row];result={'survey':survey,'field':field,'longitudinal':longitudinal,'interpretive':interpretive,'systems':systems}[family](row,payload)
 return {'row_id':row,'capability':ROWS[row],'key':key,'family':family,'source':src,'result':result,'boundary':'Research decision support only. Preserve consent, context, provenance, uncertainty, reflexivity, and qualified human review; do not overgeneralize or automate high-stakes decisions.'}
