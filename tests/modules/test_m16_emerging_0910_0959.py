"""Distinctive per-row tests for emerging-capability feature rows 910-959.

Every row executes its own method with row-specific evidence, asserts the
distinctive quantitative behavior of that method, proves seeded reproducibility
where the method is stochastic, and exercises failure paths and the hard
physical/biological non-execution boundaries.
"""
import math
import pytest
from app.modules.m16_executive_dashboard import emerging_capabilities_0910_0959 as em

B=[[-5.0,5.0],[-5.0,5.0]]
PTS=[[x,x*x+2*x+1] for x in (-2.,-1.,0.,1.,2.,3.)]
SPHERE={'bounds':B,'objective':'sphere'}
CASES={
'quantum_computing_application':({'logical_qubits':100,'t_gates':1000,'code_distance':5,'classical_cost':1e6,'quantum_cost':1e3,'gate_time_ns':50,'physical_error_rate':.001,'threshold':.01},{}),
'quantum_algorithm_design':({'search_space_size':10000,'solutions':4},{}),
'quantum_error_correction':({'physical_error_rate':.001,'threshold':.01,'code_distance':5},{}),
'quantum_machine_learning':({'hamiltonian_coefficients':[1.0,0.5,-0.25],'ansatz_parameters':[0.1,0.2,0.3]},{'steps':30}),
'quantum_simulation':({'term_coefficients':[0.5,-1.2,0.3],'evolution_time':2.0,'target_error':.01},{'trotter_order':2}),
'quantum_cryptography':({'sifted_bits':10000,'qber':.02,'error_correction_leak':100},{}),
'quantum_sensing':({'resources':100,'readout_contrast':.3,'coherence_time_s':.001,'measurement_time_s':1.0},{}),
'quantum_networking':({'link_fidelities':[.99,.98,.97],'link_success_probabilities':[.8,.9,.85]},{}),
'neuromorphic_computing':({'membrane_tau_ms':20,'dt_ms':.5,'steps':400,'input_current_na':2.0,'membrane_resistance_mohm':10},{}),
'spiking_neural_networks':({'pre_spike_times_ms':[1,5,9],'post_spike_times_ms':[2,4,12],'a_plus':.1,'a_minus':.12,'tau_plus_ms':20,'tau_minus_ms':20},{}),
'memristor_computing':({'conductance_matrix':[[1e-4,5e-4],[9e-4,2e-4]],'input_vector':[.5,-.2],'device_noise_std':.01,'adc_bits':8},{}),
'optical_computing':({'dimension':4,'insertion_loss_db_per_mzi':.2,'phase_shifter_power_mw':20,'wavelength_nm':1550},{}),
'dna_computing':({'vertex_count':7,'edge_count':12,'word_length':8},{}),
'molecular_computing':({'species_initial':{'A':1.0,'B':.5,'C':0.0},'reactions':[{'reactants':{'A':1,'B':1},'products':{'C':1},'rate':.8}],'dt':.01,'steps':200},{}),
'biological_computing':({'alpha1':3.0,'alpha2':3.0,'beta':2.0,'gamma':2.0},{}),
'swarm_intelligence':({**SPHERE,'particles':20},{'iterations':25}),
'ant_colony_optimization':({'distance_matrix':[[0,2,9,10],[2,0,6,4],[9,6,0,8],[10,4,8,0]],'ants':10,'iterations':20},{}),
'bee_algorithm':({**SPHERE,'colony_size':20},{'iterations':25}),
'firefly_algorithm':({**SPHERE,'fireflies':15},{'iterations':25}),
'cuckoo_search':({**SPHERE,'nests':15,'abandon_probability':.25},{'iterations':25}),
'bat_algorithm':({**SPHERE,'bats':15},{'iterations':25}),
'wolf_pack_algorithm':({**SPHERE,'wolves':12},{'iterations':25}),
'whale_optimization':({**SPHERE,'whales':15},{'iterations':25}),
'artificial_immune_systems':({**SPHERE,'antibodies':12},{'iterations':25}),
'artificial_life':({'grid':[[0,1,0],[0,1,0],[0,1,0]],'steps':4},{'wrap':False}),
'genetic_programming':({'target_points':PTS,'population':30,'generations':15},{'max_depth':4}),
'grammatical_evolution':({'target_points':PTS,'population':40,'generations':30},{'genome_length':40}),
'gene_expression_programming':({'target_points':PTS,'population':30,'generations':15},{'head_length':6}),
'evolutionary_strategies':({'dimension':5,'mu':10,'lambda':40,'generations':30,'initial_sigma':1.0,'objective':'sphere'},{}),
'neuroevolution':({'population':40,'generations':60,'mutation_std':.5},{'hidden_units':4}),
'developmental_robotics':({'regions':[{'name':'reach','competence_errors':[.9,.8,.7,.5,.4,.3]},{'name':'grasp','competence_errors':[.5,.5,.5,.5,.5,.5]}],'samples':200},{}),
'epigenetic_robotics':({'stimulus_intensities':[1,1,1,1,2,1]},{'habituation_decay':.7}),
'morphological_computation':({'sensor_series':[0,1,0,1,0,1,0,1],'action_series':[1,2,1.5,2.2,1.1,2.3,1.4,2.0],'morphology_params':[1,1.9,1.6,2.1,1.2,2.2,1.5,1.95]},{}),
'soft_robotics':({'pressure_kpa':80,'length_mm':60,'wall_thickness_mm':2,'material_modulus_kpa':500,'fiber_angle_deg':35,'burst_pressure_kpa':400,'outer_diameter_mm':10},{}),
'swarm_robotics':({'agents':20,'steps':30,'arena_size':100,'perception_radius':20},{}),
'modular_robotics':({'module_count':8,'dof_per_module':2,'module_mass_g':50,'connector_strength_n':20,'module_length_mm':40,'target_reach_mm':250},{}),
'self_reconfiguring_robots':({'start_shape':[[0,0],[1,0],[2,0],[3,0]],'goal_shape':[[0,0],[0,1],[1,0],[1,1]],'max_steps':20},{}),
'self_replicating_robots':({'design':{'parts_count':120,'self_fabricated_parts':45},'containment':{'physical_isolation':True,'remote_disable':True,'feedstock_interlock':True}},{}),
'molecular_nanotechnology':({'atoms_per_product':1e6,'deposition_rate_atoms_per_s':1e5,'parallel_tools':4,'error_rate_per_op':1e-6},{}),
'programmable_matter':({'target_volume_mm3':1000,'module_edge_mm':2,'modules_available':200,'mean_moves_per_module':10,'energy_per_move_mj':.5},{}),
'metamaterials':({'ring_radius_mm':3,'ring_width_mm':.5,'split_gap_mm':.2,'substrate_permittivity':4.4,'frequency_ghz':33},{}),
'negative_index_materials':({'permittivity':-2.0,'permeability':-2.0,'incidence_angle_deg':30,'host_index':1.0},{}),
'cloaking_technology':({'inner_radius_mm':10,'outer_radius_mm':20,'wavelength_mm':30,'baseline_scattering':10,'cloaked_scattering':2},{}),
'acoustic_metamaterials':({'cavity_volume_mm3':1000,'neck_length_mm':2,'neck_area_mm2':20,'frequency_hz':100},{}),
'thermal_metamaterials':({'inner_radius_mm':10,'outer_radius_mm':20,'background_conductivity_w_mk':200,'inner_temp_c':20,'outer_temp_c':80,'cloaked_temp_deviation_c':1.5},{}),
'mechanical_metamaterials':({'length_ratio_h_over_l':2.0,'reentrant_angle_deg':60,'relative_density':.1},{}),
'4d_printing':({'programmed_strain':.5,'residual_strain':.05,'cte_1_per_k':1e-5,'cte_2_per_k':5e-5,'delta_temp_k':40,'total_thickness_mm':2,'modulus_ratio':2.0},{}),
'bioprinting':({'nozzle_radius_mm':.2,'nozzle_length_mm':10,'pressure_drop_kpa':50,'viscosity_pa_s':.5,'cell_viability':[.9,.85,.88]},{}),
'organ_printing':({'construct_thickness_mm':5,'oxygen_diffusivity_mm2_s':.002,'surface_oxygen_concentration':.2,'cell_consumption_rate':.01},{}),
'tissue_engineering':({'scaffold_porosity':.8,'pore_size_um':300,'initial_cells':1e5,'doubling_time_h':24,'carrying_capacity':1e8,'culture_time_h':120,'scaffold_half_thickness_mm':2},{}),
}
def run(m,seed=7):
    d,p=CASES[m];return em.run(m,d,p,seed=seed)
@pytest.mark.parametrize('method,row',em.ROWS.items())
def test_every_row_executes_its_own_method_with_complete_envelope(method,row):
    r=run(method)
    assert r['method']==method and r['feature_row']==row
    assert r['output'] and r['assumptions'] and r['method_limits']
    assert r['execution_boundary'] and r['physical_execution']=='not_performed'
@pytest.mark.parametrize('method',em.ROWS)
def test_seeded_reproducibility(method):
    assert run(method,seed=11)==run(method,seed=11)
def test_catalog_lists_fifty_named_methods_with_row_evidence():
    c=em.catalog();assert len(c)==50 and {x['feature_row'] for x in c}==set(range(910,960))
    assert all(x['required_evidence'] and x['family'] for x in c)

# ---------------- quantum rows 910-917 ----------------
def test_row_910_fault_tolerant_resource_estimate():
    o=run('quantum_computing_application')['output']
    assert o['physical_qubit_estimate']==100*2*25 and o['logical_error_rate_bound']==pytest.approx((.1)**3)
    assert o['ideal_speedup']==pytest.approx(1000) and isinstance(o['advantage_expected'],bool)
def test_row_911_grover_iteration_count_and_success():
    o=run('quantum_algorithm_design')['output']
    theta=math.asin(math.sqrt(4/10000))
    assert o['optimal_grover_iterations']==int(math.pi/(4*theta))
    assert o['success_probability']==pytest.approx(math.sin((2*o['optimal_grover_iterations']+1)*theta)**2)
    assert o['classical_expected_queries']==2500
def test_row_912_surface_code_scaling_and_qubit_layout():
    o=run('quantum_error_correction')['output']
    assert o['below_threshold'] and o['logical_error_rate_bound']==pytest.approx(.001)
    assert (o['data_qubits'],o['ancilla_qubits'],o['total_physical_qubits'])==(25,24,49)
def test_row_913_parameter_shift_vqe_descends_toward_bound():
    o=run('quantum_machine_learning')['output']
    assert o['final_energy']<o['initial_energy'] and o['theoretical_ground_energy_bound']==-1.75
    assert len(o['energy_history'])==31 and o['final_energy']>o['theoretical_ground_energy_bound']-1e-9
def test_row_914_trotter_steps_from_spectral_range():
    o=run('quantum_simulation')['output']
    lam=2.0;expected=math.ceil(((lam*2.0)**3/(12*.01))**.5)
    assert o['spectral_range']==lam and o['trotter_steps_required']==expected and o['gate_estimate']==expected*3*10
def test_row_915_bb84_key_rate_and_eavesdrop_probe():
    o=run('quantum_cryptography')['output']
    h=-.02*math.log2(.02)-.98*math.log2(.98)
    assert o['secret_key_bits_bound']==pytest.approx(10000*(1-2*h)-100) and not o['abort']
    assert o['intercept_resend_detection_probability']==pytest.approx(1-.75**64)
def test_row_916_sql_heisenberg_and_coherence_floor():
    o=run('quantum_sensing')['output']
    assert o['standard_quantum_limit']==pytest.approx(.1) and o['heisenberg_limit']==pytest.approx(.01)
    assert o['ideal_advantage']==pytest.approx(10) and o['coherence_limited_phase_floor']==pytest.approx(1/(.3*math.sqrt(1000)))
def test_row_917_repeater_chain_werner_decay_and_distillation():
    o=run('quantum_networking')['output']
    assert o['end_to_end_success']==pytest.approx(.8*.9*.85)
    assert o['end_to_end_fidelity_lower_bound']==pytest.approx(.99*.98*.97)
    f,q=.97,.01;distilled=(f*f+q*q)/(f*f+2*f*q+5*q*q)
    assert o['bbpssw_distilled_worst_link']==pytest.approx(distilled) and o['distillation_gain']>0
# ---------------- alternative computing 918-924 ----------------
def test_row_918_lif_spike_rate_matches_analytic():
    o=run('neuromorphic_computing')['output']
    analytic=1000.0/(20*math.log(20/5))
    assert o['spike_count']>0 and o['analytic_rate_hz']==pytest.approx(analytic)
    assert abs(o['simulated_rate_hz']-analytic)<5
def test_row_919_stdp_all_pair_kernel():
    o=run('spiking_neural_networks')['output']
    pot=.1*(math.exp(-1/20)+math.exp(-3/20)+math.exp(-11/20)+math.exp(-7/20)+math.exp(-3/20))
    dep=.12*(math.exp(-3/20)+math.exp(-1/20)+math.exp(-7/20)+math.exp(-5/20))
    assert o['potentiation']==pytest.approx(pot) and o['depression']==pytest.approx(dep)
    assert o['weight_change']==pytest.approx(pot-dep) and o['spike_pairs_evaluated']==9
def test_row_920_crossbar_vmm_ideal_vs_noisy_quantized():
    o=run('memristor_computing')['output']
    assert o['ideal_output']==pytest.approx([-5e-5,4.1e-4]) and o['mac_count']==4
    assert len(o['noisy_quantized_output'])==2 and o['mse_vs_ideal']>=0
def test_row_921_mzi_mesh_loss_and_power():
    o=run('optical_computing')['output']
    assert o['mzi_count']==6 and o['worst_path_mzis']==5 and o['worst_path_loss_db']==pytest.approx(1.0)
    assert o['worst_path_transmission']==pytest.approx(10**(-.1)) and o['static_heater_power_mw']==pytest.approx(120)
def test_row_922_dna_strand_library_and_wallace_tm():
    o=run('dna_computing')['output']
    assert o['strands_required']==31 and o['wallace_tm_celsius_estimate']==24.0
    assert o['classical_path_enumerations']==720
def test_row_923_crn_mass_action_conserves_mass():
    o=run('molecular_computing')['output']
    f=o['final_concentrations']
    assert f['A']+f['C']==pytest.approx(1.0) and f['B']+f['C']==pytest.approx(.5) and f['C']>.3
def test_row_924_toggle_switch_bistability():
    o=run('biological_computing')['output']
    assert o['bistable'] and o['state_separation']>.3 and 'stable' in o['toggle_logic']
# ---------------- metaheuristics 925-934 ----------------
def test_row_925_pso_converges_on_sphere():
    o=run('swarm_intelligence')['output']
    assert o['best_fitness']<.01 and len(o['fitness_history'])==26 and o['best_fitness']<=o['fitness_history'][0]
def test_row_926_aco_finds_short_tour():
    o=run('ant_colony_optimization')['output']
    assert o['best_length']<=24 and sorted(o['best_tour'])==[0,1,2,3] and o['cities']==4
def test_row_927_abc_converges_with_scout_record():
    o=run('bee_algorithm')['output']
    assert o['best_fitness']<.01 and 'scouts_triggered' in o
def test_row_928_firefly_attraction_converges():
    o=run('firefly_algorithm')['output']
    assert o['best_fitness']<.1 and o['best_fitness']<=o['fitness_history'][0]
def test_row_929_cuckoo_levy_flights_converge():
    o=run('cuckoo_search')['output']
    assert o['best_fitness']<1 and o['levy_lambda']==1.5
def test_row_930_bat_echolocation_converges_with_loudness_decay():
    o=run('bat_algorithm')['output']
    assert o['best_fitness']<1 and o['final_mean_loudness']<=.9
def test_row_931_gwo_alpha_leadership_converges():
    o=run('wolf_pack_algorithm')['output']
    assert o['best_fitness']<.01
def test_row_932_whale_spiral_converges():
    o=run('whale_optimization')['output']
    assert o['best_fitness']<.01
def test_row_933_clonal_selection_converges():
    o=run('artificial_immune_systems')['output']
    assert o['best_fitness']<.01 and o['best_fitness']<=o['fitness_history'][0]
def test_row_934_blinker_oscillator_detected():
    o=run('artificial_life')['output']
    assert o['final_population']==3 and o['detected_period']==2 and o['population_history'][0]==3
# ---------------- evolutionary computation 935-939 ----------------
def test_row_935_gp_evolves_fitting_expression():
    o=run('genetic_programming')['output']
    assert o['best_mse']<.5 and 'x' in o['best_expression'] and o['tree_nodes']>=1
def test_row_936_grammatical_evolution_recovers_polynomial():
    o=run('grammatical_evolution')['output']
    assert o['best_mse']<1e-6 and o['best_expression'] is not None
def test_row_937_gep_karva_decoding_fits_data():
    o=run('gene_expression_programming')['output']
    assert o['best_mse']<.1 and o['head_length']==6 and len(o['gene'])==13
def test_row_938_self_adaptive_es_converges_and_shrinks_sigma():
    o=run('evolutionary_strategies')['output']
    assert o['best_fitness']<.01 and o['final_sigma_mean']<1.0
def test_row_939_neuroevolution_solves_xor():
    o=run('neuroevolution')['output']
    assert o['best_accuracy']==1.0 and o['best_mse']<.01 and o['topology']==[2,4,1]
# ---------------- robotics 940-947 ----------------
def test_row_940_learning_progress_drives_region_choice():
    o=run('developmental_robotics')['output']
    lp={r['name']:r['learning_progress'] for r in o['learning_progress']}
    assert lp['reach']==pytest.approx(.8-.4) and lp['grasp']==pytest.approx(0.0)
    assert sum(o['selection_counts'].values())==200 and o['selection_counts']['reach']>o['selection_counts']['grasp']
def test_row_941_habituation_curve_and_stage():
    o=run('epigenetic_robotics')['output']
    c=o['response_curve']
    assert c[1]<c[0] and o['habituation_index']>.6 and o['stage_estimate']=='habituated' and c[4]>c[3]
def test_row_942_morphology_beats_sensor_as_action_predictor():
    o=run('morphological_computation')['output']
    assert o['morphology_action_correlation']>o['sensor_action_correlation']
    assert o['morphological_computation_index']>0 and o['estimated_morphology_bits']>0
def test_row_943_soft_actuator_angle_force_and_burst_margin():
    o=run('soft_robotics')['output']
    k=math.sin(math.radians(70));theta=k*(80/500)*30
    assert o['tip_angle_deg_estimate']==pytest.approx(math.degrees(theta))
    assert o['blocked_force_n_estimate']==pytest.approx(80*1000*math.pi*.005**2)
    assert o['within_safe_pressure'] and o['safety_margin_kpa']==pytest.approx(120)
def test_row_944_boids_order_parameter_bounded():
    o=run('swarm_robotics')['output']
    assert len(o['order_parameter_history'])==30 and all(0<=v<=1 for v in o['order_parameter_history'])
def test_row_945_modular_chain_statics():
    o=run('modular_robotics')['output']
    assert o['total_dof']==16 and o['max_reach_mm']==320 and o['reach_feasible']
    assert o['cantilever_torque_nm']==pytest.approx(.05*9.81*.04*36) and o['static_safety_factor']==pytest.approx(.8/(.05*9.81*.04*36))
def test_row_946_reconfiguration_plan_completes_without_hardware():
    o=run('self_reconfiguring_robots')['output']
    assert o['reconfiguration_complete'] and o['goal_match_fraction']==1.0
    assert o['plan_only'] and not o['hardware_commands_emitted'] and o['steps_used']<=20
def test_row_947_self_replication_never_authorized():
    o=run('self_replicating_robots')['output']
    assert o['closure_index']==pytest.approx(.375) and not o['von_neumann_closure_complete']
    assert o['replication_authorized'] is False and o['containment_required'] and o['containment_ok']
def test_row_947b_missing_containment_controls_are_flagged_not_authorized():
    r=em.run('self_replicating_robots',{'design':{'parts_count':10,'self_fabricated_parts':10},'containment':{'physical_isolation':True}})
    assert r['output']['missing_controls']==['remote_disable','feedstock_interlock']
    assert not r['output']['containment_ok'] and r['output']['replication_authorized'] is False
# ---------------- advanced materials 948-955 ----------------
def test_row_948_mechanosynthesis_build_time_and_yield():
    o=run('molecular_nanotechnology')['output']
    assert o['build_time_s']==pytest.approx(2.5) and o['expected_misplaced_atoms']==pytest.approx(1.0)
    assert o['defect_free_yield_estimate']==pytest.approx(math.exp(-1))
def test_row_949_voxel_inventory_and_energy():
    o=run('programmable_matter')['output']
    assert o['voxels_required']==125 and o['feasible_with_inventory'] and o['module_deficit']==0
    assert o['estimated_energy_joules']==pytest.approx(.625)
def test_row_950_srr_resonance_and_negative_mu_band():
    o=run('metamaterials')['output']
    assert 20<o['resonance_ghz']<45 and o['negative_mu_at_frequency'] and o['mu_eff_real_at_frequency']<0
def test_row_951_veselago_negative_refraction():
    o=run('negative_index_materials')['output']
    assert o['negative_index_condition'] and o['refractive_index']==pytest.approx(-2.0)
    assert o['refraction_angle_deg']==pytest.approx(math.degrees(math.asin(-.25))) and o['negative_refraction']
def test_row_952_transformation_optics_cloak_profile():
    o=run('cloaking_technology')['output']
    assert o['mu_r_mid']==pytest.approx(1/3) and o['mu_theta_mid']==pytest.approx(3.0)
    assert o['epsilon_z_mid']==pytest.approx(4/3) and o['scattering_reduction']==pytest.approx(.8)
def test_row_953_helmholtz_resonance_band():
    o=run('acoustic_metamaterials')['output']
    leff=2+1.6*math.sqrt(20/math.pi);f0=343/(2*math.pi)*math.sqrt(20/(1000*leff)*1000)
    assert o['resonance_hz']==pytest.approx(f0) and o['negative_bulk_modulus_band']
def test_row_954_thermal_cloak_anisotropy_and_efficiency():
    o=run('thermal_metamaterials')['output']
    assert o['k_r_over_k_theta_mid']==pytest.approx(1/9) and o['cloaking_efficiency']==pytest.approx(.975)
    assert o['core_gradient_shielded']
def test_row_955_reentrant_honeycomb_is_auxetic():
    o=run('mechanical_metamaterials')['output']
    nu=-math.cos(math.radians(60))**2/((2+math.sin(math.radians(60)))*math.sin(math.radians(60)))
    assert o['poisson_ratio_estimate']==pytest.approx(nu) and o['auxetic']
# ---------------- printing / bio 956-959 ----------------
def test_row_956_bilayer_curvature_and_recovery_ratio():
    o=run('4d_printing')['output']
    kappa=6*4e-5*40*4/(2*(12+3*1.5))
    assert o['recovery_ratio']==pytest.approx(.9) and o['bilayer_curvature_per_mm']==pytest.approx(kappa)
    assert o['fold_radius_mm']==pytest.approx(1/kappa)
def test_row_957_extrusion_flow_shear_and_viability_boundary():
    o=run('bioprinting')['output']
    q=math.pi*(2e-4)**4*50000/(8*.5*.01)
    assert o['flow_rate_mm3_s']==pytest.approx(q*1e9) and o['wall_shear_pa']==pytest.approx(500)
    assert o['stage_speed_mm_s']==pytest.approx(50) and not o['shear_stress_warning']
    assert o['clinical_use_authorized'] is False
def test_row_958_oxygen_diffusion_forces_vascularization():
    o=run('organ_printing')['output']
    pen=math.sqrt(2*.002*.2/.01)
    assert o['oxygen_penetration_depth_mm']==pytest.approx(pen)
    assert o['vascularization_required'] and o['perfusion_channels_required_estimate']==math.ceil(5/(2*pen))
    assert o['clinical_use_authorized'] is False
def test_row_959_logistic_growth_and_nutrient_window():
    o=run('tissue_engineering')['output']
    r=math.log(2)/24;expected=1e8/(1+999*math.exp(-r*120))
    assert o['cells_at_culture_time']==pytest.approx(expected) and o['doublings_elapsed']==5
    assert not o['nutrient_limited'] and o['research_use_only']
# ---------------- failure paths ----------------
NEGATIVE=[
 ('quantum_computing_application',{'logical_qubits':10,'t_gates':10,'code_distance':4,'classical_cost':1,'quantum_cost':1,'gate_time_ns':1,'physical_error_rate':.1,'threshold':.01},{}),
 ('quantum_algorithm_design',{'search_space_size':10,'solutions':11},{}),
 ('quantum_error_correction',{'physical_error_rate':.1,'threshold':.01,'code_distance':4},{}),
 ('quantum_machine_learning',{'hamiltonian_coefficients':[1.0],'ansatz_parameters':[.1,.2]},{}),
 ('quantum_simulation',{'term_coefficients':[1.0],'evolution_time':-1,'target_error':.01},{}),
 ('quantum_cryptography',{'sifted_bits':100,'qber':.7},{}),
 ('quantum_sensing',{'resources':100,'readout_contrast':0,'coherence_time_s':.001,'measurement_time_s':1},{}),
 ('quantum_networking',{'link_fidelities':[.2],'link_success_probabilities':[.9]},{}),
 ('neuromorphic_computing',{'membrane_tau_ms':1,'dt_ms':2,'steps':10,'input_current_na':1,'membrane_resistance_mohm':1},{}),
 ('spiking_neural_networks',{'pre_spike_times_ms':[1],'post_spike_times_ms':[2],'a_plus':2,'a_minus':.1,'tau_plus_ms':20,'tau_minus_ms':20},{}),
 ('memristor_computing',{'conductance_matrix':[[1e-2]],'input_vector':[1.0],'device_noise_std':0,'adc_bits':8},{}),
 ('optical_computing',{'dimension':1,'insertion_loss_db_per_mzi':.2,'phase_shifter_power_mw':20,'wavelength_nm':1550},{}),
 ('dna_computing',{'vertex_count':3,'edge_count':2,'word_length':7},{}),
 ('molecular_computing',{'species_initial':{'A':1.0},'reactions':[{'reactants':{'A':1},'products':{},'rate':10.0}],'dt':5,'steps':10},{}),
 ('biological_computing',{'alpha1':3,'alpha2':3,'beta':.5,'gamma':2},{}),
 ('swarm_intelligence',{'bounds':[[5,-5]],'objective':'sphere','particles':5},{'iterations':3}),
 ('ant_colony_optimization',{'distance_matrix':[[0,2],[3,0]],'ants':2,'iterations':2},{}),
 ('bee_algorithm',{'bounds':B,'objective':'sphere','colony_size':2},{'iterations':3}),
 ('firefly_algorithm',{'bounds':B,'objective':'sphere','fireflies':1},{'iterations':3}),
 ('cuckoo_search',{'bounds':B,'objective':'sphere','nests':5},{'iterations':3,'abandon_probability':1.5}),
 ('bat_algorithm',{'bounds':B,'objective':'sphere','bats':5},{'iterations':3,'fmin':2,'fmax':1}),
 ('wolf_pack_algorithm',{'bounds':B,'objective':'sphere','wolves':2},{'iterations':3}),
 ('whale_optimization',{'bounds':B,'objective':'sphere','whales':1},{'iterations':3}),
 ('artificial_immune_systems',{'bounds':B,'objective':'sphere','antibodies':1},{'iterations':3}),
 ('artificial_life',{'grid':[[0,1,2],[1,0,1]],'steps':2},{}),
 ('genetic_programming',{'target_points':[[1,2]],'population':10,'generations':2},{}),
 ('grammatical_evolution',{'target_points':PTS,'population':3,'generations':2},{}),
 ('gene_expression_programming',{'target_points':PTS,'population':10,'generations':2},{'head_length':1}),
 ('evolutionary_strategies',{'dimension':3,'mu':10,'lambda':5,'generations':2,'initial_sigma':1},{}),
 ('neuroevolution',{'population':10,'generations':2,'mutation_std':0},{}),
 ('developmental_robotics',{'regions':[{'name':'r','competence_errors':[.5,-.1,.4,.3]}],'samples':10},{}),
 ('epigenetic_robotics',{'stimulus_intensities':[1,-1]},{'habituation_decay':.7}),
 ('morphological_computation',{'sensor_series':[1,1,1],'action_series':[1,2,3],'morphology_params':[1,2,3]},{}),
 ('soft_robotics',{'pressure_kpa':80,'length_mm':60,'wall_thickness_mm':2,'material_modulus_kpa':500,'fiber_angle_deg':95,'burst_pressure_kpa':400,'outer_diameter_mm':10},{}),
 ('swarm_robotics',{'agents':1,'steps':5,'arena_size':10,'perception_radius':2},{}),
 ('modular_robotics',{'module_count':1,'dof_per_module':2,'module_mass_g':50,'connector_strength_n':20,'module_length_mm':40,'target_reach_mm':250},{}),
 ('self_reconfiguring_robots',{'start_shape':[[0,0],[1,0]],'goal_shape':[[0,0],[1,0],[2,0]],'max_steps':5},{}),
 ('self_replicating_robots',{'design':{'parts_count':10,'self_fabricated_parts':11},'containment':{}},{}),
 ('molecular_nanotechnology',{'atoms_per_product':1e6,'deposition_rate_atoms_per_s':1e5,'parallel_tools':2,'error_rate_per_op':1.5},{}),
 ('programmable_matter',{'target_volume_mm3':1000,'module_edge_mm':2,'modules_available':10,'mean_moves_per_module':-1},{}),
 ('metamaterials',{'ring_radius_mm':.1,'ring_width_mm':.5,'split_gap_mm':.2,'substrate_permittivity':4.4,'frequency_ghz':10},{}),
 ('negative_index_materials',{'permittivity':-2,'permeability':2,'incidence_angle_deg':30,'host_index':1},{}),
 ('cloaking_technology',{'inner_radius_mm':20,'outer_radius_mm':10,'wavelength_mm':30,'baseline_scattering':10,'cloaked_scattering':2},{}),
 ('acoustic_metamaterials',{'cavity_volume_mm3':1000,'neck_length_mm':0,'neck_area_mm2':20,'frequency_hz':500},{}),
 ('thermal_metamaterials',{'inner_radius_mm':10,'outer_radius_mm':20,'background_conductivity_w_mk':200,'inner_temp_c':20,'outer_temp_c':20},{}),
 ('mechanical_metamaterials',{'length_ratio_h_over_l':2,'reentrant_angle_deg':120,'relative_density':.1},{}),
 ('4d_printing',{'programmed_strain':.5,'residual_strain':.6,'cte_1_per_k':1e-5,'cte_2_per_k':2e-5,'delta_temp_k':10,'total_thickness_mm':1,'modulus_ratio':1},{}),
 ('bioprinting',{'nozzle_radius_mm':.2,'nozzle_length_mm':10,'pressure_drop_kpa':50,'viscosity_pa_s':.5,'cell_viability':[1.2]},{}),
 ('organ_printing',{'construct_thickness_mm':-1,'oxygen_diffusivity_mm2_s':.002,'surface_oxygen_concentration':.2,'cell_consumption_rate':.01},{}),
 ('tissue_engineering',{'scaffold_porosity':.8,'pore_size_um':300,'initial_cells':1e5,'doubling_time_h':24,'carrying_capacity':1e4,'culture_time_h':10,'scaffold_half_thickness_mm':1},{}),
]
@pytest.mark.parametrize('method,data,params',NEGATIVE)
def test_row_specific_failure_paths_raise(method,data,params):
    with pytest.raises(ValueError):em.run(method,data,params)
def test_unknown_method_and_bad_envelope_rejected():
    with pytest.raises(ValueError):em.run('label_echo',{})
    with pytest.raises(ValueError):em.run('quantum_sensing','not-a-dict')
def test_no_method_executes_the_physical_world():
    for m in em.ROWS:
        r=run(m);assert r['physical_execution']=='not_performed' and r['execution_boundary']
