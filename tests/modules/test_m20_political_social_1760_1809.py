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
