from datetime import datetime,timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.political_social_1760_1809 import ROWS,PROFILES,AnalysisError,analyze
from app.modules.m20_general_cognitive_worker.political_social_routes_1760_1809 import router
S=[{'source_id':'s1','observed_at':datetime.now(timezone.utc).isoformat(),'supports':['power','institutions','rights','participation']}]
GEN={
1760:{'events':['e'],'actors':['a'],'institutions':['i']},1761:{'events':['e'],'institutions':['i'],'elections':['x']},1762:{'institutions':['i'],'coercion':['c'],'legitimation':['l']},1763:{'claims':['c'],'symbols':['s'],'institutions':['i']},1764:{'groups':['g'],'contexts':['c'],'institutions':['i']},1765:{'groups':['g'],'outcomes':['o'],'institutions':['i']},1766:{'groups':['g'],'outcomes':['o'],'institutions':['i']},1767:{'groups':['g'],'resources':['r'],'institutions':['i']},1768:{'strata':['s'],'outcomes':['o'],'dimensions':['d']},1772:{'groups':['g'],'dimensions':['d']},1773:{'networks':['n'],'ties':['t']},1774:{'groups':['g'],'indicators':['i']},1775:{'responses':['r'],'institutions':['i']},1776:{'activities':['a'],'population':'p'},1777:{'activities':['a'],'population':'p'},1779:{'messages':['m'],'audiences':['a'],'channels':['c']},1781:{'messages':['m']},1782:{'texts':['t'],'frames':['f']},1784:{'exposure':['e'],'evaluation_criteria':['c']},1787:{'beliefs':['b'],'behavior':['x']},1788:{'network':['n'],'actions':['a']},1789:{'individual_choices':['c'],'group_norm':'n'},1790:{'instructions':['i'],'responses':['r'],'authority_context':'a'},1791:{'requests':['q'],'responses':['r']},1792:{'members':['m'],'interactions':['i']},1793:{'decision_process':['d']},1795:{'parties':['p'],'issues':['i'],'interests':['n']},1797:{'parties':['p'],'issues':['i'],'interests':['n']},1798:{'actors':['a'],'issues':['i'],'constraints':['c']},1799:{'actors':['a'],'interactions':['i'],'system':'s'},1800:{'objectives':['o'],'options':['x'],'constraints':['c']},1801:{'assets':['a'],'threats':['t'],'vulnerabilities':['v']},1802:{'incidents':['i'],'definitions':['d']},1803:{'measures':['m'],'objectives':['o'],'rights_constraints':['r']},1804:{'conflict':'c','actors':['a'],'drivers':['d']},1805:{'facts':['f'],'rights_framework':'law'},1806:{'needs':['n'],'population':'p','constraints':['c']},1807:{'indicators':['i'],'population':'p','interventions':['x']},1808:{'flows':['f'],'places':['p'],'periods':['t']},1809:{'institutions':['i'],'issue':'climate','stakeholders':['s']}}
def payload(i):return {**GEN[i],'sources':S,'competing_explanations':['alternative'],'affected_group_inputs':['voice'],'limitations':['observational']}
@pytest.mark.parametrize('i',sorted(GEN))
def test_concept_specific_generic_rows(i):
 o=analyze(i,payload(i));assert o['capability']==ROWS[i] and o['method']==PROFILES[i][0] and o['actions_taken']==[] and o['competing_explanations']==['alternative']
def test_1769_mobility_matrix():
 o=analyze(1769,{'origin_destination_matrix':[[8,2],[1,9]],'sources':S})['findings'];assert o=={'absolute_mobility':.15,'upward':.1,'downward':.05,'persistence':.85}
def test_1770_gini():assert analyze(1770,{'values':[0,0,10,10],'sources':S})['findings']['gini']==.5
def test_1771_poverty_metrics():
 o=analyze(1771,{'households':[{'resource':50},{'resource':100}], 'poverty_line':100,'sources':S})['findings'];assert o['headcount_ratio']==.5 and o['poverty_gap']==.25 and o['severity']==.125
def test_1778_public_opinion_weighted():assert analyze(1778,{'responses':[{'value':1,'weight':3},{'value':0,'weight':1}],'sources':S})['findings']['weighted_estimate']==.75
def test_1780_media_effects_no_causal_overclaim():
 o=analyze(1780,{'exposed':[3,5],'comparison':[1,3],'sources':S})['findings'];assert o['difference_in_means']==2 and not o['causal_effect_claimed']
def test_1783_agenda_setting_correlation():assert analyze(1783,{'media_salience':[1,2,3],'public_salience':[2,4,6],'sources':S})['findings']['salience_correlation']==1
def test_1785_persuasion_change():assert analyze(1785,{'pre':[1,2],'post':[2,3],'sources':S})['findings']['mean_change']==1
def test_1786_attitude_waves():assert analyze(1786,{'waves':[[1,2],[2,3],[3,4]],'sources':S})['findings']['wave_count']==3
def test_1794_polarization_distance_not_person_label():
 o=analyze(1794,{'group_positions':{'a':[0,1],'b':[4,5]},'sources':S})['findings'];assert o['between_group_distance']==4 and not o['polarized_person_labeling']
def test_1796_negotiation_zopa_and_no_agreement():
 o=analyze(1796,{'parties':['a','b'],'offers':[80,100],'reservation_points':{'buyer_max':95,'seller_min':90},'sources':S})['findings'];assert o['zopa']==[90,95] and not o['agreement_made']
def test_all_50_exact_names():assert set(ROWS)==set(range(1760,1810)) and ROWS[1760]=='Revolution' and ROWS[1809]=='Global Governance'
def test_provenance_required():
 with pytest.raises(AnalysisError,match='sources'):analyze(1770,{'values':[1,2]})
def test_required_inputs_rejected():
 with pytest.raises(AnalysisError,match='institutions'):analyze(1809,{'issue':'x','stakeholders':['s'],'sources':S})
def test_evidence_gaps_explicit():
 o=analyze(1809,{'institutions':['un'],'issue':'x','stakeholders':['s'],'sources':S});assert 'evidence_gap' in o['findings']['lens_status'].values()
def test_mounted_route():
 a=FastAPI();a.include_router(router,prefix='/api/modules/20');c=TestClient(a);r=c.post('/api/modules/20/political-social-1760-1809/1809',json={'payload':{'institutions':['un'],'issue':'x','stakeholders':['s'],'sources':S}});assert r.status_code==200 and r.json()['capability']=='Global Governance'
def test_route_rejects_unknown():
 a=FastAPI();a.include_router(router);assert TestClient(a).post('/political-social-1760-1809/1759',json={'payload':{}}).status_code==422

# --- audit family D: distinctive per-row metrics, failure paths, tenant boundary
def MET(i,**kw):return analyze(i,{**kw,'sources':S})['findings']['metrics']
def test_1760_revolution_phases():
 m=MET(1760,events=[{'id':'e1','phase':'grievances'},{'id':'e2','phase':'mobilization','critical':True}],actors=['a','b'],institutions=['i'])
 assert m['phase_counts']=={'grievances':1,'mobilization':1} and m['critical_junctures']==['e2'] and m['actor_count']==2
def test_1761_democratization_elections():
 m=MET(1761,events=['e'],institutions=['i'],elections=[{'contested':True,'turnout':.6},{'contested':False,'turnout':.4}])
 assert m['contested_rate']==.5 and m['mean_turnout']==.5
def test_1762_authoritarian_pillars():
 m=MET(1762,institutions=['elite_cohesion'],coercion=['repression'],legitimation=['x'])
 assert set(m['resilience_pillars_covered'])=={'elite_cohesion','repression'} and m['pillar_coverage_fraction']==.5
def test_1763_nationalism_claim_types():assert MET(1763,claims=[{'type':'civic'},{'type':'ethnic'},{'type':'civic'}],symbols=['s'],institutions=['i'])['claim_type_counts']=={'civic':2,'ethnic':1}
def test_1764_ethnicity_self_id():
 m=MET(1764,groups=[{'self_identified':True},{}],contexts=['c'],institutions=['i']);assert m['self_identified_fraction']==.5 and m['externally_labeled_count']==1
def test_1765_race_disparity_ratio():assert MET(1765,groups=['a','b'],outcomes=[{'group':'a','value':10},{'group':'b','value':5}],institutions=['i'])['disparity_ratio']==2
def test_1766_gender_gap():assert MET(1766,groups=['a','b'],outcomes=[{'group':'a','value':10},{'group':'b','value':4}],institutions=['i'])['max_group_gap']==6
def test_1767_class_concentration():assert MET(1767,groups=['a'],resources=[{'owner':'a','value':80},{'owner':'b','value':20}],institutions=['i'])['top_owner_share']==.8
def test_1768_stratification_ranking():assert MET(1768,strata=[{'name':'low','mean_outcome':1},{'name':'high','mean_outcome':9}],outcomes=['o'],dimensions=['d'])['strata_ranking']==['high','low']
def test_1772_exclusion_dimensions():assert MET(1772,groups=['g'],dimensions=[{'name':'economic','excluded_groups':['g1','g2']}])['excluded_counts_by_dimension']=={'economic':2}
def test_1773_social_capital_tie_types():
 m=MET(1773,networks=['n'],ties=[{'type':'bonding'},{'type':'bridging'},{'type':'bonding'}]);assert m['tie_type_fractions']['bonding']==round(2/3,4)
def test_1774_cohesion_index():assert MET(1774,groups=['g'],indicators=[{'value':.5},{'value':.9}])['cohesion_index']==.7
def test_1775_trust_by_institution():assert MET(1775,responses=[{'institution':'courts','score':4},{'institution':'courts','score':2}],institutions=['courts'])['trust_mean_by_institution']=={'courts':3}
def test_1776_1777_participation_rates():
 for i in (1776,1777):
  m=MET(i,activities=[{'name':'voting','participants':40}],population=100);assert m['activity_participation_rates'][0]['rate']==.4
def test_1779_channel_counts():assert MET(1779,messages=[{'channel':'tv'},{'channel':'web'},{'channel':'tv'}],audiences=['a'],channels=['tv','web'])['message_counts_by_channel']=={'tv':2,'web':1}
def test_1781_propaganda_device_counts():
 m=MET(1781,messages=[{'text':'Everyone must join us or else danger'}]);assert m['device_counts']['bandwagon']==2 and m['device_counts']['fear_appeal']==1 and m['messages_flagged']==1
def test_1782_frame_term_counts():assert MET(1782,texts=[{'text':'crime wave crime'}],frames=[{'name':'crime frame','terms':['crime']}])['frame_term_counts']=={'crime frame':2}
def test_1784_priming_shift():
 m=MET(1784,exposure=['e'],evaluation_criteria=[{'name':'competence','pre':.3,'post':.7}]);assert m['criterion_shifts'][0]['shift']==.4
def test_1787_dissonance_inconsistency():
 m=MET(1787,beliefs=[{'statement':'smoking is fine','contradicts_behavior':True},{'statement':'exercise is good'}],behavior=['x'])
 assert m['inconsistency_rate']==.5 and m['inconsistent_beliefs']==['smoking is fine']
def test_1788_influence_centrality():assert MET(1788,network=[['a','b'],['a','c']],actions=['x'])['most_central']=='a'
def test_1789_conformity_alignment():assert MET(1789,individual_choices=['x','x','y'],group_norm='x')['alignment_rate']==round(2/3,4)
def test_1790_obedience_compliance():
 m=MET(1790,instructions=['i'],responses=[{'complied':True,'level':3},{'complied':False,'level':1}],authority_context='a');assert m['compliance_rate']==.5 and m['max_escalation_level']==3
def test_1791_compliance_by_strategy():assert MET(1791,requests=['q'],responses=[{'strategy':'foot','complied':True},{'strategy':'foot','complied':False},{'strategy':'door','complied':True}])['compliance_rate_by_strategy']=={'foot':.5,'door':1}
def test_1792_group_roles():assert MET(1792,members=[{'role':'leader'},{'role':'member'},{'role':'member'}],interactions=['i'])['role_counts']=={'leader':1,'member':2}
def test_1793_groupthink_antecedents():
 m=MET(1793,decision_process={'dissent_suppressed':True,'high_cohesion':True});assert m['antecedent_count']==2 and 'dissent_suppressed' in m['antecedents_present']
def test_1795_conflict_interest_coverage():assert MET(1795,parties=['a','b'],issues=[{'name':'land'},{'name':'water'}],interests=[{'issue':'land','party':'a'}])['interest_coverage_fraction']==.5
def test_1797_mediation_agenda_coverage():assert MET(1797,parties=['a','b'],issues=[{'name':'land'},{'name':'water'}],interests=[{'issue':'land'},{'issue':'water'}])['agenda_coverage_fraction']==1
def test_1798_diplomacy_constraints():assert MET(1798,actors=['a'],issues=['i'],constraints=[{'issue':'trade'},{'issue':'trade'}])['constraint_counts_by_issue']=={'trade':2}
def test_1799_ir_interaction_types():
 m=MET(1799,actors=['a'],interactions=[{'type':'cooperation'},{'type':'conflict'},{'type':'cooperation'}],system='s');assert m['cooperation_fraction']==round(2/3,4)
def test_1800_option_coverage():
 m=MET(1800,objectives=['growth','stability'],options=[{'name':'o1','covers':['growth']}],constraints=['c']);assert m['option_objective_coverage'][0]['coverage_fraction']==.5
def test_1801_security_risk_scores():
 m=MET(1801,assets=['a'],threats=[{'name':'t1','likelihood':.5,'impact':8},{'name':'t2','likelihood':.9,'impact':3}],vulnerabilities=['v'])
 assert m['threat_risk_scores'][0]=={'threat':'t1','risk_score':4} and m['vulnerability_count']==1
def test_1802_incident_counts():assert MET(1802,incidents=[{'target':'civilians','tactic':'bombing'}],definitions=['d1','d2'])['incidents_by_target_type']=={'civilians':1}
def test_1803_counterterrorism_measures():
 m=MET(1803,measures=[{'effectiveness':'effective'},{'effectiveness':'harmful','rights_impact':True}],objectives=['o'],rights_constraints=['r'])
 assert m['measure_effectiveness_counts']=={'effective':1,'harmful':1} and m['measures_with_rights_impact']==1
def test_1804_peace_drivers():assert MET(1804,conflict='c',actors=['a'],drivers=[{'category':'economic'},{'category':'economic'},{'category':'identity'}])['driver_category_counts']=={'economic':2,'identity':1}
def test_1805_rights_allegations():assert MET(1805,facts=[{'right':'speech'},{'right':'assembly'},{'right':'speech'}],rights_framework='law')['allegations_by_right']=={'speech':2,'assembly':1}
def test_1806_humanitarian_coverage():assert MET(1806,needs=[{'met':True},{'met':False}],population='p',constraints=['c'])['needs_coverage_fraction']==.5
def test_1807_development_indicators():assert MET(1807,indicators=[{'value':2},{'value':4}],population='p',interventions=['x'])['indicator_mean']==3
def test_1808_globalization_flows():assert MET(1808,flows=[{'type':'trade','value':10},{'type':'trade','value':5},{'type':'finance','value':3}],places=['p'],periods=['t'])['flow_totals_by_type']=={'trade':15,'finance':3}
def test_1809_governance_coverage():assert MET(1809,institutions=[{'mandate':True,'representative':False,'accountable':True}],issue='x',stakeholders=['s'])['governance_dimension_coverage']=={'mandate':1,'representative':0,'accountable':1}
def test_political_failure_paths():
 with pytest.raises(AnalysisError,match='square'):analyze(1769,{'origin_destination_matrix':[[1,2]],'sources':S})
 with pytest.raises(AnalysisError,match='positive total'):analyze(1769,{'origin_destination_matrix':[[0,0],[0,0]],'sources':S})
 with pytest.raises(AnalysisError,match='non-negative'):analyze(1770,{'values':[1,-2],'sources':S})
 with pytest.raises(AnalysisError,match='poverty_line'):analyze(1771,{'households':[{'resource':1}],'poverty_line':0,'sources':S})
 with pytest.raises(AnalysisError,match='weights'):analyze(1778,{'responses':[{'value':1,'weight':0}],'sources':S})
 with pytest.raises(AnalysisError,match='required inputs'):analyze(1780,{'exposed':[],'comparison':[1],'sources':S})
 with pytest.raises(AnalysisError,match='non-empty'):analyze(1786,{'waves':[[1],[]],'sources':S})
 with pytest.raises(AnalysisError,match='align'):analyze(1783,{'media_salience':[1],'public_salience':[1,2],'sources':S})
 with pytest.raises(AnalysisError,match='2\+ non-empty'):analyze(1794,{'group_positions':{'a':[1]},'sources':S})
 with pytest.raises(AnalysisError,match='unsupported'):analyze(9999,{'sources':S})
def test_political_tenant_boundary(monkeypatch):
 from app.main import app
 monkeypatch.setenv('ATLAS_ENV','production')
 c=TestClient(app)
 assert c.get('/api/v1/api/modules/20/political-social-1760-1809/capabilities').status_code==401
 h={'X-Atlas-Tenant':'tenant-a','X-Atlas-Actor':'tester'}
 r=c.get('/api/v1/api/modules/20/political-social-1760-1809/capabilities',headers=h);assert r.status_code==200 and len(r.json())==50
