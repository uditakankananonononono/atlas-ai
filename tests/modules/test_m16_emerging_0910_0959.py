import pytest
from app.modules.m16_executive_dashboard import analysis
from app.modules.m16_executive_dashboard import emerging_capabilities_0910_0959 as em
Q=({'classical_cost':100,'quantum_cost':10,'fidelity':.95},{})
C=({'energy_per_operation':1e-9,'operations':1e6,'accuracy':.9},{})
S=({'candidate_scores':[1,2,3,2.5]},{'iterations':5})
E=({'fitness':[.8,.9,.7],'complexity':[5,20,2]},{'complexity_penalty':.01})
R=({'task_success':[.9,.8],'adaptation_scores':[.7,.8],'safety_checks':[.9,.85]},{})
M=({'measured_properties':[1,2],'target_properties':[1.05,2.1]},{'tolerance':.1})
T=({'cell_viability':[.9,.85],'mechanical_integrity':[.8,.75],'maturity':.5},{})
CASES={name:(Q if row in (910,911,913,914) else C if 918<=row<=924 else S if 925<=row<=934 else E if 935<=row<=939 else R if 940<=row<=947 else M if 948<=row<=955 else T) for name,row in em.ROWS.items()}
CASES.update({'quantum_error_correction':({'physical_error_rate':.001,'threshold':.01,'code_distance':5},{}),'quantum_cryptography':({'sifted_bits':10000,'qber':.02,'error_correction_leak':100},{}),'quantum_sensing':({'resources':100},{}),'quantum_networking':({'link_fidelities':[.99,.98],'link_success_probabilities':[.8,.9]},{}),'spiking_neural_networks':({'energy_per_operation':1e-9,'operations':1e6,'accuracy':.9,'spikes':1000,'neurons':100},{}),'dna_computing':({'energy_per_operation':1e-12,'operations':1e9,'accuracy':.8,'molecule_count':1e6,'parallel_reactions':1000},{}),'negative_index_materials':({'measured_properties':[-1,-2],'target_properties':[-1,-2],'permittivity':-2,'permeability':-1},{}),'cloaking_technology':({'measured_properties':[.1],'target_properties':[.1],'baseline_scattering':10,'cloaked_scattering':2},{}),'4d_printing':({'initial_dimension':10,'stimulated_dimension':12,'cycles':100},{}),})
@pytest.mark.parametrize('method,row',em.ROWS.items())
def test_each_emerging_row_is_mounted(method,row):
 d,p=CASES[method];r=analysis.run(method,d,p,seed=11)
 assert r['feature_row']==row and r['method']==method and r['output']
def test_quantum_concepts_and_security_bounds():
 q=analysis.run('quantum_error_correction',*CASES['quantum_error_correction'])['output'];assert q['below_threshold'] and q['logical_error_rate_bound']==pytest.approx(.001)
 k=analysis.run('quantum_cryptography',*CASES['quantum_cryptography'])['output'];assert k['secret_key_bits_bound']>0 and not k['abort']
def test_emerging_physical_and_biological_safety_boundaries():
 rep=analysis.run('self_replicating_robots',*CASES['self_replicating_robots'])['output'];assert not rep['replication_authorized'] and rep['containment_required']
 organ=analysis.run('organ_printing',*CASES['organ_printing'])['output'];assert not organ['clinical_use_authorized']
def test_seeded_swarm_search_is_reproducible():
 d,p=CASES['ant_colony_optimization'];assert analysis.run('ant_colony_optimization',d,p,7)==analysis.run('ant_colony_optimization',d,p,7)
def test_negative_paths():
 with pytest.raises(ValueError):analysis.run('quantum_error_correction',{'physical_error_rate':.1,'threshold':.01,'code_distance':4})
 with pytest.raises(ValueError):analysis.run('soft_robotics',{'task_success':[2],'adaptation_scores':[.5],'safety_checks':[.5]})
 with pytest.raises(ValueError):analysis.run('bioprinting',{'cell_viability':[1.2],'mechanical_integrity':[.8]})
