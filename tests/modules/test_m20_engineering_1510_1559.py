import math
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.engineering_1510_1559 import METHODS,engineering_support_1510_1559
from app.modules.m20_general_cognitive_worker.routes import router

E=engineering_support_1510_1559
EXPECTED=['mechanical_design','cad_modeling','finite_element_analysis','computational_fluid_dynamics','thermal_analysis','stress_analysis','fatigue_analysis','fracture_mechanics','materials_selection','material_properties','failure_analysis','reliability_engineering','maintainability_engineering','safety_engineering','human_factors_engineering','ergonomics','industrial_design','design_for_manufacturing','design_for_assembly','design_for_sustainability','design_for_six_sigma','tolerance_analysis','gdt','metrology','quality_control','quality_assurance','statistical_process_control','process_capability','measurement_systems_analysis','design_of_experiments','taguchi_methods','response_surface_methodology','robust_design','reliability_testing','accelerated_life_testing','environmental_testing','vibration_testing','shock_testing','thermal_cycling','humidity_testing','corrosion_testing','wear_testing','fatigue_testing','creep_testing','impact_testing','hardness_testing','tensile_testing','compression_testing','shear_testing','torsion_testing']

def test_1510_to_1559_have_exact_unique_handlers_and_names():
 assert METHODS==EXPECTED and len(set(METHODS))==50
 for method in METHODS:
  assert isinstance(method,str) and method

def test_1510_mechanical_design_traceability():
 r=E('mechanical_design',{'requirements':[{'id':'R1','verification_method':'test','acceptance':'load > 5kN'},{'id':'R2'}]})['result']
 assert r['uncovered_requirement_ids']==['R2'] and r['verification_matrix'][0]['covered']
def test_1511_cad_reference_order():
 r=E('cad_modeling',{'features':[{'id':'sketch','references':[]},{'id':'hole','references':['missing']} ]})['result']; assert r['reference_errors']==[{'feature':'hole','missing_references':['missing']}]
def test_1512_fea_mesh_convergence_without_claiming_solver_run():
 r=E('finite_element_analysis',{'mesh_results':[{'result':100},{'result':102}],'convergence_tolerance_percent':2})['result']; assert r['converged_to_percent'] and not r['solver_run_claimed']
def test_1513_cfd_mass_balance():
 r=E('computational_fluid_dynamics',{'mass_in':[1,2],'mass_out':[2.9]})['result']; assert r['mass_imbalance_percent']==pytest.approx(100/30)
def test_1514_thermal_network(): assert E('thermal_analysis',{'heat_w':10,'ambient_c':20,'thermal_resistances_k_per_w':[.2,.3]})['result']['predicted_hot_temperature_c']==25
def test_1515_stress_von_mises_and_factor_of_safety():
 r=E('stress_analysis',{'sigma_x':100,'sigma_y':0,'tau_xy':0,'yield_strength':250})['result']; assert r['von_mises_stress']==100 and r['factor_of_safety']==2.5
def test_1516_fatigue_miner_damage(): assert E('fatigue_analysis',{'cycles':[{'applied_cycles':10,'allowable_cycles':100},{'applied_cycles':1,'allowable_cycles':10}]})['result']['miner_sum']==pytest.approx(.2)
def test_1517_fracture_mechanics(): assert E('fracture_mechanics',{'stress':100,'crack_length':.001,'fracture_toughness':50})['result']['stress_intensity']==pytest.approx(100*math.sqrt(math.pi*.001))
def test_1518_materials_missing_criterion_blocks_score():
 r=E('materials_selection',{'criteria':[{'id':'strength','weight':2},{'id':'cost','weight':1}],'candidates':[{'material':'A','scores':{'strength':4}}]})['result']; assert r['decision_matrix'][0]['weighted_score'] is None
def test_1519_properties_require_condition_unit_and_source():
 r=E('material_properties',{'properties':[{'name':'E','value':200,'unit':'GPa','condition':'20C','source_ref':'cert'},{'name':'Sy','value':1}]})['result']; assert r['untraceable_properties']==['Sy']
def test_1520_failure_analysis_does_not_invent_root_cause(): assert not E('failure_analysis',{'hypotheses':[{'id':'h'}]})['result']['root_cause_claimed']
def test_1521_series_reliability(): assert E('reliability_engineering',{'component_reliabilities':[.9,.8]})['result']['series_reliability']==pytest.approx(.72)
def test_1522_maintainability_mttr(): assert E('maintainability_engineering',{'repair_durations_hours':[1,2,3]})['result']['mttr_hours']==2
def test_1523_safety_rpn_and_acceptance():
 h=E('safety_engineering',{'hazards':[{'severity':5,'occurrence':2,'detection':4}]})['result']['hazards'][0]; assert h['rpn']==40 and h['residual_risk_requires_acceptance']
def test_1524_human_factors_flags_safety_critical(): assert E('human_factors_engineering',{'tasks':[{'id':'t','safety_consequence':'injury'}]})['result']['tasks'][0]['critical']
def test_1525_ergonomics_keeps_instrument_context(): assert E('ergonomics',{'assessment_instrument':'RULA','score':6})['result']['instrument_interpretation_requires_qualified_reviewer']
def test_1526_industrial_design_not_release_ready(): assert not E('industrial_design',{'concepts':['A']})['result']['release_ready']
def test_1527_dfm_process_constraints():
 r=E('design_for_manufacturing',{'features':[{'id':'wall','thickness':.5}],'process_constraints':[{'id':'minwall','field':'thickness','min':1}]})['result']; assert r['feature_checks'][0]['violations']==['minwall']
def test_1528_dfa_theoretical_minimum():
 r=E('design_for_assembly',{'parts':[{'id':'a','moves_relative':True},{'id':'b'}]})['result']; assert r['theoretical_minimum_parts']==1 and r['combination_candidates']==['b']
def test_1529_sustainability_sums_lifecycle_impacts():
 r=E('design_for_sustainability',{'lifecycle_stages':[{'impacts':{'co2':2}},{'impacts':{'co2':3}}]})['result']; assert r['impact_totals']['co2']==5
def test_1530_dfss_open_ctq(): assert E('design_for_six_sigma',{'ctqs':[{'id':'x'}]})['result']['open_ctq_ids']==['x']
def test_1531_tolerance_wc_and_rss():
 r=E('tolerance_analysis',{'component_nominals':[2,3],'component_tolerances':[.3,.4]})['result']; assert r['nominal_stack']==5 and r['worst_case_plus_minus']==pytest.approx(.7) and r['rss_plus_minus']==pytest.approx(.5)
def test_1532_gdt_invalid_frame(): assert E('gdt',{'feature_control_frames':[{'id':'f','characteristic':'position','tolerance':.1,'requires_datum':True}]})['result']['invalid_frames']==['f']
def test_1533_metrology_uncertainty(): assert E('metrology',{'standard_uncertainties':[3,4],'coverage_factor':2})['result']['expanded_uncertainty']==10
def test_1534_quality_control_yield(): assert E('quality_control',{'measurements':[1,2,9],'lower_spec':0,'upper_spec':3})['result']['yield_fraction']==pytest.approx(2/3)
def test_1535_quality_assurance_traceability():
 r=E('quality_assurance',{'requirements':[{'id':'a'},{'id':'b'}],'verification_records':[{'requirement_ids':['a']}]})['result']; assert r['uncovered_requirement_ids']==['b'] and not r['release_authorized']
def test_1536_spc_uses_three_sigma_baseline(): assert E('statistical_process_control',{'values':[1,1,1,10]})['result']['baseline_only']
def test_1537_capability_cp_cpk():
 r=E('process_capability',{'values':[8,10,12],'lower_spec':0,'upper_spec':20})['result']; assert r['cp']==r['cpk'] and r['stability_must_be_established_first']
def test_1538_msa_variance_decomposition(): assert E('measurement_systems_analysis',{'repeatability_variance':1,'reproducibility_variance':2,'part_variance':7})['result']['gage_rr_percent_contribution']==30
def test_1539_full_factorial_doe(): assert E('design_of_experiments',{'factors':{'a':[1,2],'b':['x','y']}})['result']['run_count']==4
def test_1540_taguchi_larger_is_better(): assert E('taguchi_methods',{'responses':[2,2],'goal':'larger'})['result']['signal_to_noise_db']==pytest.approx(20*math.log10(2))
def test_1541_response_surface_terms():
 r=E('response_surface_methodology',{'point':{'x':2,'z':3},'coefficients':{'intercept':1,'linear':{'x':2},'quadratic':{'x':3},'interaction':{'x*z':4}}})['result']; assert r['predicted_response']==41
def test_1542_robust_design_worst_case(): assert E('robust_design',{'objective':'maximize','scenarios':[{'response':4},{'response':2}]})['result']['worst_case_response']==2
def test_1543_zero_failure_reliability_bound(): assert E('reliability_testing',{'units':10,'failures':0,'confidence':.9})['result']['zero_failure_reliability_lower_bound']==pytest.approx(.1**.1)
def test_1544_arrhenius_acceleration(): assert E('accelerated_life_testing',{'activation_energy_ev':.7,'use_temperature_k':300,'test_temperature_k':350})['result']['acceleration_factor']>1
@pytest.mark.parametrize('method,kind',[('environmental_testing','environmental'),('thermal_cycling','thermal_cycling'),('humidity_testing','humidity')])
def test_1545_1548_1549_environment_plans_not_fake_results(method,kind):
 r=E(method,{'profiles':[{'level':1}]})['result']; assert r['test_type']==kind and not r['test_executed']
def test_1546_vibration_grms():
 r=E('vibration_testing',{'psd_points':[{'frequency_hz':0,'psd_g2_per_hz':1},{'frequency_hz':4,'psd_g2_per_hz':1}]})['result']; assert r['grms']==2 and not r['test_executed']
def test_1547_shock_delta_velocity(): assert E('shock_testing',{'peak_acceleration_g':10,'duration_ms':10,'pulse_shape':'rectangular'})['result']['estimated_delta_velocity_m_per_s']==pytest.approx(.980665)
def test_1550_corrosion_rate(): assert E('corrosion_testing',{'mass_loss_g':1,'density_g_cm3':2,'area_cm2':5,'duration_hours':10})['result']['penetration_rate_cm_per_hour']==pytest.approx(.01)
def test_1551_wear_rate(): assert E('wear_testing',{'wear_volume_mm3':10,'load_n':2,'sliding_distance_m':5})['result']['specific_wear_rate_mm3_per_n_m']==1
def test_1552_fatigue_test_basquin_fit():
 r=E('fatigue_testing',{'sn_points':[{'stress':100,'cycles':1000},{'stress':10,'cycles':100000}]})['result']; assert r['basquin_slope']==pytest.approx(-2)
def test_1553_creep_interval_rates(): assert E('creep_testing',{'time_hours':[0,2,4],'strain':[0,.2,.6]})['result']['interval_rates_per_hour']==pytest.approx([.1,.2])
def test_1554_impact_absorbed_energy(): assert E('impact_testing',{'initial_energy_j':100,'remaining_energy_j':30})['result']['absorbed_energy_j']==70
def test_1555_hardness_no_unsafe_conversion(): assert not E('hardness_testing',{'scale':'HRC','values':[30,32]})['result']['cross_scale_conversion_performed']
def test_1556_tensile_properties():
 r=E('tensile_testing',{'max_force_n':1000,'original_area_mm2':10,'original_gauge_length_mm':50,'final_gauge_length_mm':55,'yield_force_n':800})['result']; assert r['ultimate_tensile_strength_mpa']==100 and r['elongation_percent']==10 and r['yield_strength_mpa']==80
def test_1557_compression(): assert E('compression_testing',{'force_n':1000,'area_mm2':10,'shortening_mm':1,'original_length_mm':20})['result']['compressive_strain']==.05
def test_1558_shear_double_plane(): assert E('shear_testing',{'force_n':1000,'shear_area_mm2':10,'shear_planes':2})['result']['average_shear_stress_mpa']==50
def test_1559_torsion():
 r=E('torsion_testing',{'torque_n_mm':100,'outer_radius_mm':2,'polar_moment_mm4':4,'gauge_length_mm':10,'angle_rad':.5})['result']; assert r['maximum_shear_stress_mpa']==50 and r['shear_modulus_mpa']==500

def test_mounted_route_and_validation():
 app=FastAPI();app.include_router(router);c=TestClient(app)
 r=c.post('/api/modules/20/engineering/1510-1559/analyze',json={'method':'stress_analysis','data':{'sigma_x':100,'yield_strength':250}})
 assert r.status_code==200 and r.json()['result']['factor_of_safety']==2.5
 assert c.post('/api/modules/20/engineering/1510-1559/analyze',json={'method':'thermal_analysis','data':{}}).status_code==422
def test_1545_environmental_plan_not_fake_result():
 r=E('environmental_testing',{'profiles':[{'level':1}]})['result'];assert r['test_type']=='environmental' and not r['test_executed']
def test_1548_thermal_cycling_plan_not_fake_result():
 r=E('thermal_cycling',{'profiles':[{'level':1}]})['result'];assert r['test_type']=='thermal_cycling' and not r['test_executed']
def test_1549_humidity_plan_not_fake_result():
 r=E('humidity_testing',{'profiles':[{'level':1}]})['result'];assert r['test_type']=='humidity' and not r['test_executed']
