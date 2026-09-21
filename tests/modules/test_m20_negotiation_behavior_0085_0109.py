import math
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

# ---- rows 85-100 practitioner-depth evidence: distinctive per-row checks ----

def test_row85_asymmetry_index_severity_and_unknown_material():
 o=run('information_asymmetry_exploitation',{'known_by_proposer':['defect','cost_floor'],'shared_with_counterparty':['cost_floor'],'material_facts':['defect','cost_floor','pending_bid']})['output']
 assert o['asymmetry_index']==pytest.approx(1/3) and o['severity']=='medium'
 assert o['required_disclosures']==['defect'] and o['disclosed_material_facts']==['cost_floor']
 assert o['material_facts_not_yet_known_to_proposer']==['pending_bid']
 empty=run('information_asymmetry_exploitation',{'known_by_proposer':[],'shared_with_counterparty':[],'material_facts':[]})['output']
 assert empty['asymmetry_index']==0 and empty['confidence']<0.5 and not empty['exploitation_blocked']
def test_row86_adverse_selection_z_score_and_small_sample_uncertainty():
 o=run('adverse_selection_detection',{'offered_risk_scores':[.8,.9],'population_mean_risk':.5})['output']
 assert o['sample_std']==pytest.approx(math.sqrt(.005)) and o['standard_error']==pytest.approx(.05)
 assert o['selection_gap']==pytest.approx(.35) and o['adverse_selection_signal']
 calm=run('adverse_selection_detection',{'offered_risk_scores':[.5,.52],'population_mean_risk':.5})['output']
 assert not calm['adverse_selection_signal']
 with pytest.raises(ValueError):run('adverse_selection_detection',{'offered_risk_scores':[.8],'population_mean_risk':.5})
def test_row87_moral_hazard_exposure_scoring_and_controls():
 o=run('moral_hazard_prevention',{'actions':['report','maintain'],'observable':[True,False],'incentive_alignment':[1,-1]})['output']
 assert o['per_action_assessment'][1]['hazard_exposure']==pytest.approx(1.0) and o['per_action_assessment'][1]['risk']=='high'
 assert o['monitoring_coverage']==.5 and o['recommended_controls']==['make outcomes measurable','share downside and upside','audit exceptions']
 with pytest.raises(ValueError):run('moral_hazard_prevention',{'actions':['a'],'observable':[True,False],'incentive_alignment':[1]})
def test_row88_screening_separation_spread_and_pooling_pairs():
 o=run('screening_mechanism_design',{'types':['low','high'],'signal_costs':[1,3],'benefits':[2,8]})['output']
 assert o['self_selection_separates'] and o['net_utility_spread']==pytest.approx(4) and not o['pooling_risk_pairs']
 pooled=run('screening_mechanism_design',{'types':['x','y'],'signal_costs':[1.0,1.001],'benefits':[2.0,2.001]})['output']
 assert not pooled['self_selection_separates'] or pooled['pooling_risk_pairs']
def test_row89_commitment_device_strength_and_deadline_validation():
 o=run('commitment_device_creation',{'goal':'save','deadline':'2027-01-01','checkins':['monthly'],'reversible':True,'self_selected_penalty':'donate 500'})['output']
 assert o['device_strength_score']==pytest.approx(.8) and o['adherence_support_estimate']['point']==pytest.approx(.72)
 lo,hi=o['adherence_support_estimate']['interval_80pct'];assert lo<o['adherence_support_estimate']['point']<hi
 with pytest.raises(ValueError):run('commitment_device_creation',{'goal':'save','deadline':'next friday','checkins':['x']})
 with pytest.raises(ValueError):run('commitment_device_creation',{'goal':'save','deadline':'2027-01-01','checkins':[]})
def test_row90_threat_credibility_components():
 o=run('credible_threat_construction',{'proposed_consequence':'terminate per contract','lawful':True,'proportionate':True,'authorized':True})['output']
 assert o['credible'] and o['credibility_score']==1.0 and o['credibility_components']=={'lawful':True,'proportionate':True,'authorized':True}
def test_row91_bargaining_power_weighted_score_and_interval():
 o=run('bargaining_power_assessment',{'alternative_strength':.8,'time_pressure':.2,'information_quality':.7,'dependence':.3})['output']
 expected=(.35*.8+.25*.7)/.6-(.2*.2+.2*.3)/.4
 assert o['power_score']==pytest.approx(expected,abs=1e-4) and o['dominant_driver']=='alternatives'
 lo,hi=o['score_interval'];assert lo==pytest.approx(max(-1,expected-.15),abs=1e-4) and hi==pytest.approx(min(1,expected+.15),abs=1e-4)
 with pytest.raises(ValueError):run('bargaining_power_assessment',{'alternative_strength':1.4,'time_pressure':.2,'information_quality':.7,'dependence':.3})
def test_row92_batna_sensitivity_and_fragility():
 o=run('batna_identification',{'alternatives':['walk','other'],'values':[5,10],'costs':[0,3]})['output']
 assert o['batna']=='other' and o['batna_value']==7 and o['walk_away_threshold']==7
 assert o['runner_up_swing_to_flip']==2 and o['choice_fragility']=='robust'
 fragile=run('batna_identification',{'alternatives':['a','b'],'values':[10,10.05],'costs':[0,0]})['output']
 assert fragile['choice_fragility']=='fragile' and fragile['confidence']<0.5
def test_row93_zopa_surplus_splits_and_no_deal_zone():
 o=run('zopa_mapping',{'seller_reservation':80,'buyer_reservation':100})['output']
 assert o['zopa_exists'] and o['width']==20 and o['midpoint']==90
 assert o['surplus_split_options']['buyer_favored_75_25_price']==85 and o['surplus_split_options']['seller_favored_75_25_price']==95
 nope=run('zopa_mapping',{'seller_reservation':110,'buyer_reservation':100})['output']
 assert not nope['zopa_exists'] and nope['width']==0 and nope['surplus_split_options']=={}
def test_row94_integrative_logrolling_gain_and_distributive_detection():
 o=run('integrative_bargaining',{'issues':['price','time'],'party_a_weights':[.9,.1],'party_b_weights':[.2,.8]})['output']
 assert o['efficient_allocation'][0]['efficient_holder']=='party_a' and o['efficient_allocation'][1]['efficient_holder']=='party_b'
 assert o['logrolling_gain_vs_naive_split']==pytest.approx(.7) and not o['purely_distributive']
 flat=run('integrative_bargaining',{'issues':['price'],'party_a_weights':[.5],'party_b_weights':[.5]})['output']
 assert flat['purely_distributive'] and flat['logrolling_gain_vs_naive_split']==0
 with pytest.raises(ValueError):run('integrative_bargaining',{'issues':['p'],'party_a_weights':[-.1],'party_b_weights':[.5]})
def test_row95_anchoring_rejects_objective_outside_evidence():
 o=run('anchoring_strategy',{'objective_value':95,'evidence_low':80,'evidence_high':100})['output']
 assert o['evidence_based_anchor']==95 and o['estimated_adjustment_band']==5 and o['expected_settlement_zone']==[90,95]
 bad=run('anchoring_strategy',{'objective_value':130,'evidence_low':80,'evidence_high':100})['output']
 assert bad['evidence_based_anchor'] is None and not bad['deployment_allowed'] and 'rejection' in bad
def test_row96_framing_numeric_equivalence_gate():
 o=run('framing_effects_utilization',{'gain_frame':'gain 10','loss_frame':'lose 10','facts':{'delta':10}})['output']
 assert o['numeric_equivalence'] and o['consistent_with_facts'] and o['deployment_allowed']
 one_sided=run('framing_effects_utilization',{'gain_frame':'gain 10','loss_frame':'terrible outcome','facts':{'delta':10}})['output']
 assert not one_sided['numeric_equivalence'] and not one_sided['deployment_allowed']
 with pytest.raises(ValueError):run('framing_effects_utilization',{'gain_frame':'x','loss_frame':'y','facts':{}})
def test_row97_loss_aversion_reports_reference_lambda_and_asymmetry():
 o=run('loss_aversion_leverage',{'gain_frame':'keep 10','loss_frame':'lose 10','facts':{'delta':10}})['output']
 assert o['reference_loss_aversion_lambda']==2.25 and o['frame_asymmetry_ratio']==pytest.approx(1.0)
 skewed=run('loss_aversion_leverage',{'gain_frame':'keep 5','loss_frame':'lose 20','facts':{'delta':5}})['output']
 assert skewed['frame_asymmetry_ratio']==pytest.approx(.25) and not skewed['numeric_equivalence']
def test_row98_social_proof_wilson_interval_and_sample_floor():
 o=run('social_proof_deployment',{'claim':'60% chose it','evidence':'survey-1','claimed_proportion':.6,'sample_size':100})['output']
 lo,hi=o['wilson_interval_95'];assert lo==pytest.approx(.502,abs=.005) and hi==pytest.approx(.691,abs=.005)
 assert o['statistically_supported'] and o['deployment_allowed']
 tiny=run('social_proof_deployment',{'claim':'60% chose it','evidence':'survey-1','claimed_proportion':.6,'sample_size':4})['output']
 assert not tiny['statistically_supported'] and not tiny['deployment_allowed']
 unquantified=run('social_proof_deployment',{'claim':'popular','evidence':'survey-1','claimed_proportion':.6})['output']
 assert not unquantified['deployment_allowed']
def test_row99_scarcity_arithmetic_verification():
 o=run('scarcity_creation',{'claim':'3 remain','evidence':'inventory snapshot','total_units':50,'sold_units':47,'claimed_remaining':3})['output']
 assert o['scarcity_arithmetic']['computed_remaining']==3 and o['arithmetic_consistent'] and o['deployment_allowed']
 lying=run('scarcity_creation',{'claim':'3 remain','evidence':'snapshot','total_units':50,'sold_units':40,'claimed_remaining':3})['output']
 assert not lying['arithmetic_consistent'] and not lying['deployment_allowed'] and lying['fabrication_blocked']
 with pytest.raises(ValueError):run('scarcity_creation',{'claim':'x','total_units':5,'sold_units':9})
def test_row100_reciprocity_obligation_risk_blocks_strings():
 o=run('reciprocity_triggers',{'benefit':'free guide','strings_attached':False})['output']
 assert o['allowed'] and o['obligation_risk_score']==0
 quid=run('reciprocity_triggers',{'benefit':'free guide','strings_attached':True,'expected_return':'a referral'})['output']
 assert not quid['allowed'] and quid['blocked'] and quid['obligation_risk_score']==pytest.approx(1.0)
