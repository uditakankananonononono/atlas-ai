import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1068_entropy_balancing_hits_target_moment():
 o=analysis.run('entropy_balancing',{'treated':[1,1,0,0,0],'outcome':[10,12,3,7,11],'covariate':[1,3,0,2,4]})['output'];assert o['weighted_control_mean']==pytest.approx(2,abs=1e-6) and sum(o['control_weights'])==pytest.approx(1)
def test_row_1069_ipw_recovers_weighted_marginal_difference_and_ess():
 o=analysis.run('inverse_probability_weighting',{'treated':[1,1,0,0],'outcome':[5,7,1,3],'propensity_score':[.5]*4})['output'];assert o['ate']==pytest.approx(4) and o['effective_sample_size']==pytest.approx(4)
def test_row_1070_aipw_is_doubly_robust_score():
 o=analysis.run('doubly_robust_estimation',{'treated':[1,0,1,0],'outcome':[5,1,7,3],'propensity_score':[.5]*4,'outcome_model_treated':[5,5,7,7],'outcome_model_control':[1,1,3,3]})['output'];assert o['ate']==pytest.approx(4) and abs(sum(o['influence_scores'])/4-4)<1e-12

def test_row_1071_tmle_targets_and_has_near_zero_ic_mean():
 o=analysis.run('targeted_maximum_likelihood',{'treated':[1,0,1,0],'outcome':[1,0,1,0],'propensity_score':[.5]*4,'initial_q1':[.7]*4,'initial_q0':[.3]*4})['output'];assert o['ate']>.4 and abs(o['influence_curve_mean'])<1e-6

def test_row_1072_cross_fitted_ml_causal_inference_avoids_self_fit():
 data={'treated':[0,1,0,1,0,1,0,1],'outcome':[0,2,1,3,2,4,3,5],'features':[[0],[0],[1],[1],[2],[2],[3],[3]]}
 o=analysis.run('machine_learning_causal_inference',data)['output'];assert o['folds']==2 and 1<o['ate']<3 and len(o['individual_effects'])==8

def test_causal_weighting_rejects_positivity_violations():
 with pytest.raises(ValueError):analysis.run('inverse_probability_weighting',{'treated':[1,0],'outcome':[1,0],'propensity_score':[1,0]})
