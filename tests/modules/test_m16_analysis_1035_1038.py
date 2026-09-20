"""Concept-level tests for doc rows 1035-1038."""
import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1035_kalman_filter_reduces_uncertainty_and_tracks_state():
 o=analysis.run('kalman_filter',{'observations':[0.9,1.1,1.0,1.05]},{'process_variance':0.01,'observation_variance':0.1,'initial_state':0,'initial_variance':10})['output']
 assert abs(o['filtered_states'][-1]-1)<.1
 assert o['posterior_variances'][-1] < o['posterior_variances'][0]
 assert len(o['innovations'])==4 and all(0<k<1 for k in o['kalman_gains'])

def test_row_1036_extended_kalman_filter_uses_local_jacobian():
 o=analysis.run('extended_kalman_filter',{'observations':[4,4.2,3.9]},{'observation_model':'square','initial_state':1.8,'observation_variance':.1})['output']
 assert abs(o['filtered_states'][-1]-2)<.15
 assert o['observation_jacobians'][0]==pytest.approx(3.6)
 assert 'diverge' in ' '.join(o['method_limits'])

def test_row_1037_ukf_propagates_sigma_points_without_jacobian():
 o=analysis.run('unscented_kalman_filter',{'observations':[4,4.1,3.95]},{'observation_model':'square','initial_state':1.8,'observation_variance':.1,'alpha':.5})['output']
 assert abs(o['filtered_states'][-1]-2)<.2
 assert o['sigma_parameters']=={'alpha':.5,'beta':2.0,'kappa':0.0}
 assert 'jacobian' not in o

def test_row_1038_hmm_forward_probabilities_and_viterbi_path():
 data={'observations':['walk','shop','clean'],'states':['Rainy','Sunny'],'start_probability':{'Rainy':.6,'Sunny':.4},'transition_probability':{'Rainy':{'Rainy':.7,'Sunny':.3},'Sunny':{'Rainy':.4,'Sunny':.6}},'emission_probability':{'Rainy':{'walk':.1,'shop':.4,'clean':.5},'Sunny':{'walk':.6,'shop':.3,'clean':.1}}}
 o=analysis.run('hidden_markov_model',data)['output']
 assert o['most_likely_path']==['Sunny','Rainy','Rainy']
 assert all(sum(step.values())==pytest.approx(1) for step in o['filtered_state_probabilities'])
 assert o['log_likelihood']<0

def test_new_estimators_reject_invalid_models():
 with pytest.raises(ValueError):analysis.run('kalman_filter',{'observations':[1]},{'observation_variance':0})
 with pytest.raises(ValueError):analysis.run('extended_kalman_filter',{'observations':[1]},{'observation_model':'arbitrary_code'})
 with pytest.raises(ValueError):analysis.run('hidden_markov_model',{'observations':['x'],'states':['a'],'start_probability':{'a':1},'transition_probability':{'a':{'a':.5}},'emission_probability':{'a':{'x':1}}})
