import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1048_importance_sampling_tracks_target_and_ess():
 o=analysis.run('importance_sampling',{}, {'draws':20000,'proposal_mean':0,'proposal_sd':2,'target_mean':1,'target_sd':1},7)['output']
 assert abs(o['target_expectation']-1)<.05 and 0<o['effective_sample_size']<=o['draws']

def test_row_1049_rejection_sampling_checks_bound_and_accepts_target():
 o=analysis.run('rejection_sampling',{}, {'accepted_draws':2000,'proposal_mean':0,'proposal_sd':2,'target_mean':1,'target_sd':1,'bound':4},8)['output']
 assert o['completed'] and abs(o['sample_mean']-1)<.1 and 0<o['acceptance_rate']<1
 with pytest.raises(ValueError):analysis.run('rejection_sampling',{}, {'accepted_draws':100,'proposal_sd':2,'target_sd':1,'bound':.1},8)

def test_row_1050_slice_sampler_targets_distribution_without_normalizer():
 o=analysis.run('slice_sampling',{}, {'draws':5000,'target_mean':2,'target_sd':.5,'width':1},9)['output']
 assert abs(o['sample_mean']-2)<.05 and o['interval'][0]<2<o['interval'][1]

def test_row_1051_nested_sampling_returns_finite_log_evidence():
 o=analysis.run('nested_sampling',{'observation':1},{'live_points':100,'iterations':500,'prior_low':-5,'prior_high':5},10)['output']
 assert o['log_evidence']<0 and o['dead_point_count']==500

def test_row_1052_abc_likelihood_free_posterior_near_observed_summary():
 o=analysis.run('approximate_bayesian_computation',{'observed_summary':3},{'draws':50000,'epsilon':.15,'prior_low':-5,'prior_high':5,'simulation_sd':.5},11)['output']
 assert o['accepted']>100 and abs(o['posterior_mean']-3)<.15 and o['posterior_interval'][0]<3<o['posterior_interval'][1]
