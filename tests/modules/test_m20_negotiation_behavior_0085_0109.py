import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.negotiation_behavior_0085_0109 import ROWS,run
C={
'information_asymmetry_exploitation':{'known_by_proposer':['defect'],'shared_with_counterparty':[],'material_facts':['defect']},'adverse_selection_detection':{'offered_risk_scores':[.8,.9],'population_mean_risk':.5},'moral_hazard_prevention':{'actions':['report','maintain'],'observable':[True,False],'incentive_alignment':[1,-1]},'screening_mechanism_design':{'types':['low','high'],'signal_costs':[1,3],'benefits':[2,8]},'commitment_device_creation':{'goal':'save','deadline':'2027-01-01','checkins':['monthly'],'reversible':True},'credible_threat_construction':{'proposed_consequence':'terminate per contract','lawful':True,'proportionate':True,'authorized':True},'bargaining_power_assessment':{'alternative_strength':.8,'time_pressure':.2,'information_quality':.7,'dependence':.3},'batna_identification':{'alternatives':['walk','other'],'values':[5,10],'costs':[0,3]},'zopa_mapping':{'seller_reservation':80,'buyer_reservation':100},'integrative_bargaining':{'issues':['price','time'],'party_a_weights':[.9,.1],'party_b_weights':[.2,.8]},'anchoring_strategy':{'objective_value':95,'evidence_low':80,'evidence_high':100},'framing_effects_utilization':{'gain_frame':'gain 10','loss_frame':'lose 10','facts':{'delta':10}},'loss_aversion_leverage':{'gain_frame':'keep 10','loss_frame':'lose 10','facts':{'delta':10}},'social_proof_deployment':{'claim':'60% chose it','evidence':'survey-1'},'scarcity_creation':{'claim':'3 verified units remain','evidence':'inventory snapshot'},'reciprocity_triggers':{'benefit':'free guide','strings_attached':False},'authority_positioning':{'claim':'licensed','evidence':'registry record'},'consistency_commitment':{'prior_commitment':'a','current_choice':'a','freely_chosen':True},'liking_enhancement':{'genuine_commonalities':['same school']},'unity_building':{'genuine_commonalities':['same team']},'pre_suasion':{'context':'compare total cost first','disclosed':True},'priming_effects':{'context':'safety checklist','disclosed':True},'nudge_design':{'options':['standard','green'],'default':'green','easy_opt_out':True,'transparent':True,'alternatives_visible':True},'choice_architecture':{'options':['monthly','annual'],'default':'monthly','easy_opt_out':True,'transparent':True,'alternatives_visible':True},'libertarian_paternalism':{'options':['opt in','opt out'],'default':'opt out','easy_opt_out':True,'transparent':True,'alternatives_visible':True}}
@pytest.mark.parametrize('method,row',ROWS.items())
def test_exact_substantive_row(method,row):
 r=run(method,C[method]);assert r['feature_row']==row and r['method']==method and r['output'] and r['output']['method_limits']
def test_material_asymmetry_and_unverified_influence_are_blocked():
 assert run('information_asymmetry_exploitation',C['information_asymmetry_exploitation'])['output']['required_disclosures']==['defect']
 assert not run('social_proof_deployment',{'claim':'everyone buys this'})['output']['deployment_allowed']
 assert not run('scarcity_creation',{'claim':'last chance'})['output']['deployment_allowed']
def test_threat_coercion_and_covert_priming_are_blocked():
 x=run('credible_threat_construction',{'proposed_consequence':'harm','lawful':False,'proportionate':False,'authorized':False})['output'];assert not x['may_communicate'] and len(x['blocked_reasons'])==3
 assert not run('priming_effects',{'context':'hidden cue','disclosed':False})['output']['allowed']
def test_choice_preserves_easy_informed_exit():
 assert run('nudge_design',C['nudge_design'])['output']['autonomy_preserved']
 bad=dict(C['nudge_design'],easy_opt_out=False);assert not run('nudge_design',bad)['output']['deployment_allowed']
def test_negative_paths_and_mounted_api():
 with pytest.raises(ValueError):run('zopa_mapping',{'seller_reservation':'x','buyer_reservation':10})
 with pytest.raises(ValueError):run('choice_architecture',{'options':['a'],'default':'b'})
 c=TestClient(app);h={'X-Tenant-ID':'n','X-Actor-ID':'tester'}
 r=c.get('/api/v1/api/modules/20/negotiation-behavior-85-109/methods',headers=h);assert r.status_code==200 and len(r.json())==25
 r=c.post('/api/v1/api/modules/20/negotiation-behavior-85-109/analyze',headers=h,json={'method':'zopa_mapping','data':C['zopa_mapping']});assert r.status_code==200 and r.json()['feature_row']==93
 assert c.post('/api/v1/api/modules/20/negotiation-behavior-85-109/analyze',headers=h,json={'method':'bad'}).status_code==422
