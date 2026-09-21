"""Evidence-led political and social analysis for audit rows 1760-1809.

All methods preserve provenance, competing explanations, affected-group voice and
uncertainty. Outputs are analysis, never political targeting, propaganda, coercion,
surveillance, diplomatic commitments, security operations, or eligibility decisions.
"""
from __future__ import annotations
from statistics import mean
from collections import Counter
from typing import Any
ROWS=dict(enumerate('''Revolution|Democratization|Authoritarianism|Nationalism|Ethnicity|Race Relations|Gender Relations|Class Analysis|Stratification|Mobility|Inequality|Poverty|Social Exclusion|Social Capital|Social Cohesion|Social Trust|Civic Engagement|Political Participation|Public Opinion|Political Communication|Media Effects|Propaganda|Framing|Agenda Setting|Priming|Persuasion|Attitude Change|Cognitive Dissonance|Social Influence|Conformity|Obedience|Compliance|Group Dynamics|Groupthink|Polarization|Conflict Resolution|Negotiation|Mediation|Diplomacy|International Relations|Foreign Policy|Security Studies|Terrorism|Counterterrorism|Peace Studies|Human Rights|Humanitarian Action|Development Studies|Globalization|Global Governance'''.split('|'),1760))
PROFILES={
1760:('process_tracing',['events','actors','institutions'],['grievances','mobilization','state_response','critical_junctures']),1761:('transition_analysis',['events','institutions','elections'],['contestability','participation','rights','civilian_control']),1762:('authoritarian_resilience',['institutions','coercion','legitimation'],['repression','cooptation','information_control','elite_cohesion']),
1763:('nationalism_analysis',['claims','symbols','institutions'],['civic','ethnic','anti_colonial','state_building']),1764:('ethnicity_analysis',['groups','contexts','institutions'],['self_identification','boundary_making','power','intersectionality']),1765:('race_relations',['groups','outcomes','institutions'],['disparity','discrimination_evidence','segregation','repair']),1766:('gender_relations',['groups','outcomes','institutions'],['roles','power','care','intersectionality']),1767:('class_analysis',['groups','resources','institutions'],['ownership','occupation','income','power']),1768:('stratification',['strata','outcomes','dimensions'],['rank','closure','inheritance','intersectionality']),1769:('mobility_analysis',['origin_destination_matrix'],['absolute_mobility','upward','downward','persistence']),1770:('inequality_analysis',['values'],['gini','distribution','top_share','between_group_limits']),1771:('poverty_analysis',['households','poverty_line'],['headcount','gap','severity','multidimensional_deprivation']),1772:('exclusion_analysis',['groups','dimensions'],['economic','social','political','service_access']),1773:('social_capital',['networks','ties'],['bonding','bridging','linking','resource_access']),1774:('cohesion_analysis',['groups','indicators'],['belonging','solidarity','conflict','institutional_inclusion']),1775:('trust_analysis',['responses','institutions'],['interpersonal','institutional','generalized','uncertainty']),1776:('civic_engagement',['activities','population'],['volunteering','associations','deliberation','collective_action']),1777:('participation_analysis',['activities','population'],['voting','protest','contact','barriers']),
1778:('opinion_estimation',['responses'],['weighted_estimate','sampling','nonresponse','question_wording']),1779:('communication_analysis',['messages','audiences','channels'],['sender','message','channel','reception']),1780:('media_effects',['exposed','comparison'],['difference_in_means','selection_bias','spillover','causal_limits']),1781:('propaganda_detection',['messages'],['source_concealment','manipulative_devices','false_dilemma','dehumanization']),1782:('frame_analysis',['texts','frames'],['problem_definition','causal_interpretation','moral_evaluation','treatment']),1783:('agenda_setting',['media_salience','public_salience'],['salience_association','lag','confounders','causal_limits']),1784:('priming_analysis',['exposure','evaluation_criteria'],['criterion_shift','pre_post','alternative_explanations','causal_limits']),1785:('persuasion_analysis',['pre','post'],['change','attrition','durability','autonomy']),1786:('attitude_change',['waves'],['direction','magnitude','stability','measurement_invariance']),1787:('dissonance_analysis',['beliefs','behavior'],['inconsistency','rationalization','belief_change','behavior_change']),1788:('influence_analysis',['network','actions'],['centrality','diffusion','homophily','peer_effect_limits']),1789:('conformity_analysis',['individual_choices','group_norm'],['alignment','private_acceptance_unknown','unanimity','independence']),1790:('obedience_analysis',['instructions','responses','authority_context'],['authority','escalation','dissent','right_to_refuse']),1791:('compliance_analysis',['requests','responses'],['request_strategy','consent','refusal','power_asymmetry']),
1792:('group_dynamics',['members','interactions'],['roles','norms','status','communication']),1793:('groupthink_risk',['decision_process'],['dissent','alternatives','independent_review','leader_impartiality']),1794:('polarization',['group_positions'],['between_group_distance','within_group_spread','sorting','affective_limits']),1795:('conflict_resolution',['parties','issues','interests'],['positions','interests','needs','options']),1796:('negotiation',['parties','offers','reservation_points'],['zopa','tradeoffs','batna','agreement_requires_approval']),1797:('mediation',['parties','issues','interests'],['neutrality','confidentiality','agenda','party_owned_outcome']),1798:('diplomacy',['actors','issues','constraints'],['interests','signals','channels','commitment_risk']),
1799:('international_relations',['actors','interactions','system'],['power','institutions','interdependence','ideas']),1800:('foreign_policy',['objectives','options','constraints'],['interests','instruments','tradeoffs','second_order_effects']),1801:('security_studies',['assets','threats','vulnerabilities'],['likelihood','impact','resilience','human_security']),1802:('terrorism_research',['incidents','definitions'],['targets','tactics','claimed_motives','definition_limits']),1803:('counterterrorism_review',['measures','objectives','rights_constraints'],['effectiveness','displacement','rights','oversight']),1804:('peace_studies',['conflict','actors','drivers'],['negative_peace','positive_peace','structural_violence','reconciliation']),1805:('human_rights',['facts','rights_framework'],['right','duty_bearer','alleged_interference','remedy']),1806:('humanitarian_action',['needs','population','constraints'],['humanity','neutrality','impartiality','independence']),1807:('development_studies',['indicators','population','interventions'],['capabilities','distribution','sustainability','local_ownership']),1808:('globalization',['flows','places','periods'],['trade','finance','migration','information']),1809:('global_governance',['institutions','issue','stakeholders'],['mandate','representation','accountability','coordination'])}
class AnalysisError(ValueError):pass
def _need(d,keys):
 m=[k for k in keys if d.get(k) in (None,[],{})]
 if m:raise AnalysisError('missing required inputs: '+', '.join(m))
def _gini(v):
 v=sorted(float(x) for x in v)
 if any(x<0 for x in v) or not v or sum(v)==0:raise AnalysisError('values must be non-negative with positive sum')
 n=len(v);return sum((2*i-n-1)*x for i,x in enumerate(v,1))/(n*sum(v))
def _special(i,d):
 if i==1769:
  m=d['origin_destination_matrix']
  if not isinstance(m,list) or not m or any(not isinstance(r,list) or len(r)!=len(m) for r in m):raise AnalysisError('origin_destination_matrix must be a non-empty square matrix')
  total=sum(map(sum,m))
  if total<=0:raise AnalysisError('origin_destination_matrix must have positive total')
  up=sum(m[a][b] for a in range(len(m)) for b in range(len(m[a])) if b>a);down=sum(m[a][b] for a in range(len(m)) for b in range(len(m[a])) if b<a);return {'absolute_mobility':round((up+down)/total,4),'upward':round(up/total,4),'downward':round(down/total,4),'persistence':round(1-(up+down)/total,4)}
 if i==1770:
  v=d['values'];return {'gini':round(_gini(v),4),'mean':mean(v),'count':len(v),'normative_threshold_applied':False}
 if i==1771:
  h=d['households'];line=float(d['poverty_line'])
  if not h or line<=0:raise AnalysisError('households must be non-empty and poverty_line positive')
  g=[max(0,line-float(x['resource']))/line for x in h];return {'headcount_ratio':round(sum(x>0 for x in g)/len(g),4),'poverty_gap':round(mean(g),4),'severity':round(mean(x*x for x in g),4)}
 if i==1778:
  rs=d['responses']
  if not rs:raise AnalysisError('responses must be non-empty')
  den=sum(float(x.get('weight',1)) for x in rs)
  if den<=0:raise AnalysisError('response weights must sum positive')
  return {'weighted_estimate':round(sum(float(x['value'])*float(x.get('weight',1)) for x in rs)/den,4),'n':len(rs),'margin_of_error_claimed':False}
 if i==1780:
  if not d['exposed'] or not d['comparison']:raise AnalysisError('exposed and comparison must be non-empty')
  return {'exposed_mean':mean(d['exposed']),'comparison_mean':mean(d['comparison']),'difference_in_means':round(mean(d['exposed'])-mean(d['comparison']),4),'causal_effect_claimed':False}
 if i==1783:
  a=d['media_salience'];b=d['public_salience'];
  if len(a)!=len(b) or len(a)<2:raise AnalysisError('salience series must align')
  ma,mb=mean(a),mean(b);num=sum((x-ma)*(y-mb) for x,y in zip(a,b));den=(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))**.5;return {'salience_correlation':None if den==0 else round(num/den,4),'causal_effect_claimed':False}
 if i in (1785,1786):
  before=d['pre'] if i==1785 else d['waves'][0];after=d['post'] if i==1785 else d['waves'][-1]
  if not before or not after:raise AnalysisError('measurement waves must be non-empty')
  return {'mean_change':round(mean(after)-mean(before),4),'wave_count':2 if i==1785 else len(d['waves']),'individual_causation_claimed':False}
 if i==1794:
  gp=d['group_positions']
  if not isinstance(gp,dict) or len(gp)<2 or any(not v for v in gp.values()):raise AnalysisError('group_positions needs 2+ non-empty groups')
  means={k:mean(v) for k,v in gp.items()};return {'group_means':means,'between_group_distance':round(max(means.values())-min(means.values()),4),'polarized_person_labeling':False}
 if i==1796:
  r=d['reservation_points'];buyer=float(r['buyer_max']);seller=float(r['seller_min']);return {'zopa_exists':buyer>=seller,'zopa':[seller,buyer] if buyer>=seller else None,'agreement_made':False,'offers':d['offers']}
 return None
def analyze(row_id:int,payload:dict[str,Any])->dict[str,Any]:
 if row_id not in ROWS:raise AnalysisError('unsupported row')
 method,required,lenses=PROFILES[row_id];_need(payload,required);sources=payload.get('sources',[])
 if not sources or any(not x.get('source_id') or not x.get('observed_at') for x in sources):raise AnalysisError('sources require source_id and observed_at')
 special=_special(row_id,payload)
 findings=special or {'evidence_map':{lens:[x['source_id'] for x in sources if lens in x.get('supports',[])] for lens in lenses},'lens_status':{lens:'evidence_supplied' if any(lens in x.get('supports',[]) for x in sources) else 'evidence_gap' for lens in lenses},'metrics':_metrics(row_id,payload)}
 return {'row_id':row_id,'capability':ROWS[row_id],'method':method,'findings':findings,'lenses':lenses,'competing_explanations':payload.get('competing_explanations',[]),'affected_group_inputs':payload.get('affected_group_inputs',[]),'limitations':payload.get('limitations',[]),'sources':sources,'status':'analysis_for_qualified_human_review','actions_taken':[],'boundary':'Analysis only. Do not target political beliefs or protected groups, manipulate, propagandize, coerce, surveil, operationalize violence, make diplomatic commitments, allocate aid, or determine rights. Preserve lawful dissent, consent, privacy, human rights, local voice and accountable human decisions.'}

def _d(v):return [x for x in v if isinstance(x,dict)] if isinstance(v,list) else []
def _frac(n,d):return round(n/d,4) if d else None
def _group_means(rows,key='group',val='value'):
 g={}
 for r in rows:
  if isinstance(r.get(val),(int,float)):g.setdefault(str(r.get(key)),[]).append(float(r[val]))
 return {k:round(mean(v),4) for k,v in g.items() if v}
def _metrics(i,d):
 """Distinctive per-row measurements computed only from supplied inputs."""
 if i==1760:
  ev=_d(d.get('events',[]));return {'event_count':len(d.get('events',[])),'phase_counts':dict(Counter(str(e.get('phase')) for e in ev if e.get('phase'))),'critical_junctures':[e.get('id',e.get('name')) for e in ev if e.get('critical')],'actor_count':len(d.get('actors',[])),'institution_count':len(d.get('institutions',[]))}
 if i==1761:
  el=_d(d.get('elections',[]));cont=[e for e in el if 'contested' in e];return {'election_count':len(el),'contested_rate':_frac(sum(bool(e.get('contested')) for e in cont),len(cont)),'mean_turnout':(round(mean(float(e['turnout']) for e in el if isinstance(e.get('turnout'),(int,float))),4) if any(isinstance(e.get('turnout'),(int,float)) for e in el) else None)}
 if i==1762:
  pillars={'repression','cooptation','information_control','elite_cohesion'};blob=str(d.get('institutions',''))+str(d.get('coercion',''))+str(d.get('legitimation',''))
  covered=sorted(x for x in pillars if x in blob);return {'resilience_pillars_covered':covered,'pillar_coverage_fraction':round(len(covered)/4,4)}
 if i==1763:
  cl=_d(d.get('claims',[]));return {'claim_type_counts':dict(Counter(str(c.get('type','untyped')) for c in cl)),'symbol_count':len(d.get('symbols',[]))}
 if i==1764:
  gr=_d(d.get('groups',[]));selfid=sum(bool(g.get('self_identified')) for g in gr);return {'group_count':len(d.get('groups',[])),'self_identified_fraction':_frac(selfid,len(gr)),'externally_labeled_count':len(gr)-selfid}
 if i in (1765,1766):
  means=_group_means(_d(d.get('outcomes',[])));vals=list(means.values())
  key='disparity_ratio' if i==1765 else 'max_group_gap';out={'group_mean_outcomes':means}
  if len(vals)>=2:out[key]=(round(max(vals)/min(vals),4) if i==1765 and min(vals)!=0 else round(max(vals)-min(vals),4))
  else:out[key]=None
  return out
 if i==1767:
  res=_d(d.get('resources',[]));by={}
  for r in res:
   if isinstance(r.get('value'),(int,float)):by[str(r.get('owner','unassigned'))]=by.get(str(r.get('owner','unassigned')),0)+r['value']
  total=sum(by.values());return {'resource_totals_by_owner':by,'top_owner_share':_frac(max(by.values()),total) if by else None}
 if i==1768:
  st=_d(d.get('strata',[]));ranked=sorted((s for s in st if isinstance(s.get('mean_outcome'),(int,float))),key=lambda s:-s['mean_outcome'])
  return {'strata_ranking':[s.get('name') for s in ranked],'overlap_warning':'strata means can mask within-strata spread'}
 if i==1772:
  dims=_d(d.get('dimensions',[]));return {'excluded_counts_by_dimension':{str(x.get('name')):len(x.get('excluded_groups',[])) for x in dims if x.get('name') is not None},'dimensions_assessed':len(dims)}
 if i==1773:
  ties=_d(d.get('ties',[]));types=Counter(str(t.get('type','untyped')) for t in ties);total=sum(types.values())
  return {'tie_type_counts':dict(types),'tie_type_fractions':({k:round(v/total,4) for k,v in types.items()} if total else {})}
 if i==1774:
  ind=_d(d.get('indicators',[]));vals=[float(x['value']) for x in ind if isinstance(x.get('value'),(int,float))]
  return {'cohesion_index':(round(mean(vals),4) if vals else None),'indicator_count':len(ind)}
 if i==1775:
  return {'trust_mean_by_institution':_group_means(_d(d.get('responses',[])),'institution','score')}
 if i in (1776,1777):
  acts=_d(d.get('activities',[]));pop=d.get('population');pop=float(pop) if isinstance(pop,(int,float)) and pop>0 else None
  return {'activity_participation_rates':[{ 'activity':a.get('name'),'participants':a.get('participants'),'rate':_frac(a['participants'],pop) if pop and isinstance(a.get('participants'),(int,float)) else None} for a in acts],'population_supplied':pop is not None}
 if i==1779:
  msgs=_d(d.get('messages',[]));return {'message_counts_by_channel':dict(Counter(str(m.get('channel','unspecified')) for m in msgs)),'audience_count':len(d.get('audiences',[]))}
 if i==1781:
  devices={'bandwagon':['everyone','everybody','all agree','join us'],'false_dilemma':['either','or else','only two'],'fear_appeal':['threat','danger','fear','catastrophe'],'dehumanization':['vermin','animals','subhuman','infestation'],'ad_hominem':['stupid','corrupt','evil']}
  texts=[(m.get('text','') if isinstance(m,dict) else str(m)).lower() for m in d.get('messages',[])]
  return {'device_counts':{k:sum(t.count(w) for t in texts for w in ws) for k,ws in devices.items()},'messages_flagged':sum(any(w in t for ws in devices.values() for w in ws) for t in texts)}
 if i==1782:
  frames=_d(d.get('frames',[]));texts=' '.join((t.get('text','') if isinstance(t,dict) else str(t)).lower() for t in d.get('texts',[]))
  return {'frame_term_counts':{str(f.get('name')):sum(texts.count(str(x).lower()) for x in f.get('terms',[])) for f in frames if f.get('name') is not None},'elements':['problem_definition','causal_interpretation','moral_evaluation','treatment_recommendation']}
 if i==1784:
  crit=_d(d.get('evaluation_criteria',[]));shifts=[{'criterion':c.get('name'),'shift':round(float(c['post'])-float(c['pre']),4)} for c in crit if isinstance(c.get('pre'),(int,float)) and isinstance(c.get('post'),(int,float))]
  return {'criterion_shifts':shifts,'mean_abs_shift':(round(mean(abs(s['shift']) for s in shifts),4) if shifts else None)}
 if i==1787:
  bels=_d(d.get('beliefs',[]));incon=[b for b in bels if b.get('contradicts_behavior')]
  return {'belief_count':len(bels),'inconsistent_beliefs':[b.get('statement') for b in incon],'inconsistency_rate':_frac(len(incon),len(bels))}
 if i==1788:
  net=d.get('network');edges=net.get('edges',[]) if isinstance(net,dict) else net if isinstance(net,list) else []
  deg=Counter()
  for e in edges:
   if isinstance(e,(list,tuple)) and len(e)==2:deg[str(e[0])]+=1;deg[str(e[1])]+=1
  return {'degree_centrality':dict(deg),'most_central':(deg.most_common(1)[0][0] if deg else None),'action_count':len(d.get('actions',[]))}
 if i==1789:
  ch=d.get('individual_choices',[]);norm=d.get('group_norm');aligned=sum(str(c.get('choice') if isinstance(c,dict) else c)==str(norm) for c in ch)
  return {'choice_count':len(ch),'alignment_rate':_frac(aligned,len(ch))}
 if i==1790:
  rs=_d(d.get('responses',[]));comp=[r for r in rs if 'complied' in r]
  return {'compliance_rate':_frac(sum(bool(r['complied']) for r in comp),len(comp)),'max_escalation_level':(max((r['level'] for r in rs if isinstance(r.get('level'),(int,float))),default=None))}
 if i==1791:
  rs=_d(d.get('responses',[]));by={}
  for r in rs:
   s=str(r.get('strategy','unspecified'));by.setdefault(s,[0,0]);by[s][1]+=1;by[s][0]+=bool(r.get('complied'))
  return {'compliance_rate_by_strategy':{k:round(v[0]/v[1],4) for k,v in by.items()}}
 if i==1792:
  mem=_d(d.get('members',[]));return {'role_counts':dict(Counter(str(m.get('role','unassigned')) for m in mem)),'interaction_count':len(d.get('interactions',[]))}
 if i==1793:
  dp=d.get('decision_process',{});flags=['dissent_suppressed','high_cohesion','directive_leadership','insulation_from_outside','time_pressure']
  present=[f for f in flags if isinstance(dp,dict) and dp.get(f)]
  return {'antecedents_present':present,'antecedent_count':len(present),'risk_note':'antecedent presence elevates groupthink risk; mitigations require independent review'}
 if i==1795:
  ints=_d(d.get('interests',[]));issues=[str(x.get('name') if isinstance(x,dict) else x) for x in d.get('issues',[])]
  covered={s for s in issues if any(str(x.get('issue'))==s for x in ints)}
  return {'issues_with_identified_interests':sorted(covered),'interest_coverage_fraction':_frac(len(covered),len(issues))}
 if i==1797:
  ints=_d(d.get('interests',[]));issues=[str(x.get('name') if isinstance(x,dict) else x) for x in d.get('issues',[])]
  covered={s for s in issues if any(str(x.get('issue'))==s for x in ints)}
  return {'agenda_coverage_fraction':_frac(len(covered),len(issues)),'party_count':len(d.get('parties',[]))}
 if i==1798:
  cons=_d(d.get('constraints',[]));return {'constraint_counts_by_issue':dict(Counter(str(c.get('issue','general')) for c in cons)),'actor_count':len(d.get('actors',[]))}
 if i==1799:
  ints=_d(d.get('interactions',[]));return {'interaction_type_counts':dict(Counter(str(x.get('type',x.get('kind','untyped'))) for x in ints)),'cooperation_fraction':_frac(sum(str(x.get('type',x.get('kind','')))=='cooperation' for x in ints),len(ints))}
 if i==1800:
  opts=_d(d.get('options',[]));objs={str(o.get('name') if isinstance(o,dict) else o) for o in d.get('objectives',[])}
  return {'option_objective_coverage':[{'option':o.get('name'),'objectives_covered':sorted({str(c) for c in o.get('covers',[])}&objs) if objs else [str(c) for c in o.get('covers',[])],'coverage_fraction':_frac(len({str(c) for c in o.get('covers',[])}&objs),len(objs))} for o in opts]}
 if i==1801:
  th=_d(d.get('threats',[]));scored=[{'threat':t.get('name'),'risk_score':round(float(t['likelihood'])*float(t['impact']),4)} for t in th if isinstance(t.get('likelihood'),(int,float)) and isinstance(t.get('impact'),(int,float))]
  return {'threat_risk_scores':sorted(scored,key=lambda x:-x['risk_score']),'asset_count':len(d.get('assets',[])),'vulnerability_count':len(d.get('vulnerabilities',[]))}
 if i==1802:
  inc=_d(d.get('incidents',[]));return {'incident_count':len(inc),'incidents_by_target_type':dict(Counter(str(x.get('target','unspecified')) for x in inc)),'incidents_by_tactic':dict(Counter(str(x.get('tactic','unspecified')) for x in inc)),'definition_count':len(d.get('definitions',[]))}
 if i==1803:
  ms=_d(d.get('measures',[]));return {'measure_effectiveness_counts':dict(Counter(str(m.get('effectiveness','unrated')) for m in ms)),'measures_with_rights_impact':sum(bool(m.get('rights_impact')) for m in ms),'oversight_note':'effectiveness claims require independent evaluation'}
 if i==1804:
  dr=_d(d.get('drivers',[]));return {'driver_category_counts':dict(Counter(str(x.get('category','uncategorized')) for x in dr)),'actor_count':len(d.get('actors',[]))}
 if i==1805:
  facts=_d(d.get('facts',[]));return {'allegations_by_right':dict(Counter(str(f.get('right','unspecified')) for f in facts)),'fact_count':len(facts)}
 if i==1806:
  needs=_d(d.get('needs',[]));met=sum(bool(n.get('met')) for n in needs)
  return {'needs_met_count':met,'needs_coverage_fraction':_frac(met,len(needs)),'constraint_count':len(d.get('constraints',[]))}
 if i==1807:
  ind=_d(d.get('indicators',[]));vals=[float(x['value']) for x in ind if isinstance(x.get('value'),(int,float))]
  return {'indicator_mean':(round(mean(vals),4) if vals else None),'indicator_count':len(ind),'intervention_count':len(d.get('interventions',[]))}
 if i==1808:
  flows=_d(d.get('flows',[]));by={}
  for f in flows:
   if isinstance(f.get('value'),(int,float)):by[str(f.get('type','untyped'))]=by.get(str(f.get('type','untyped')),0)+f['value']
  return {'flow_totals_by_type':by,'place_count':len(d.get('places',[])),'period_count':len(d.get('periods',[]))}
 if i==1809:
  inst=_d(d.get('institutions',[]))
  return {'governance_dimension_coverage':{k:sum(bool(x.get(k)) for x in inst) for k in ('mandate','representative','accountable')},'stakeholder_count':len(d.get('stakeholders',[]))}
 return {}
