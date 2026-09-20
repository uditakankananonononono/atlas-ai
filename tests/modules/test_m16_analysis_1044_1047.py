import math,pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1044_sum_product_exact_on_tree():
 data={'variables':['a','b'],'factors':[{'scope':['a'],'table':{'0':.2,'1':.8}},{'scope':['a','b'],'table':{'00':3,'01':1,'10':1,'11':3}}]}
 o=analysis.run('belief_propagation',data,{'iterations':4})['output']
 assert o['converged_on_tree'] and o['marginal_true']['a']==pytest.approx(.8)
 assert o['marginal_true']['b']==pytest.approx(.68)

def test_row_1045_vmp_combines_natural_parameter_messages():
 o=analysis.run('variational_message_passing',{'observations':[1,2,3]},{'prior_mean':0,'prior_variance':100,'observation_variance':1})['output']
 assert o['converged'] and o['iterations']==1
 assert o['posterior_mean']==pytest.approx(6/3.01)
 assert o['posterior_variance']==pytest.approx(1/3.01)

def test_row_1046_ep_matches_truncated_gaussian_moments():
 o=analysis.run('expectation_propagation',{'lower':0},{'prior_mean':0,'prior_variance':1})['output']
 assert o['moment_matched_mean']==pytest.approx(math.sqrt(2/math.pi))
 assert o['moment_matched_variance']==pytest.approx(1-2/math.pi)
 assert o['normalizer']==pytest.approx(.5)

def test_row_1047_laplace_finds_logistic_map_and_positive_curvature():
 o=analysis.run('laplace_approximation',{'observations':[-1,1],'trials':[10,10],'successes':[2,8]},{'prior_variance':10})['output']
 assert o['converged'] and o['posterior_mode']>0 and o['gaussian_variance']>0
 assert o['interval'][0]<o['posterior_mode']<o['interval'][1]

def test_approximate_inference_rejects_invalid_parameters():
 with pytest.raises(ValueError):analysis.run('belief_propagation',{'variables':['a'],'factors':[]},{'damping':1})
 with pytest.raises(ValueError):analysis.run('variational_message_passing',{'observations':[1]},{'prior_variance':0})
 with pytest.raises(ValueError):analysis.run('laplace_approximation',{'observations':[1],'trials':[2],'successes':[3]})
