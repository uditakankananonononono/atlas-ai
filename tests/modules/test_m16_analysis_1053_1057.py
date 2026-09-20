import math,pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1053_synthetic_likelihood_scores_simulated_summaries():
 o=analysis.run('synthetic_likelihood',{'observed_summary':[2.0],'simulated_summaries':[[1.8],[2.0],[2.2],[1.9],[2.1]]})['output']
 assert o['simulation_count']==5 and o['simulated_mean']==pytest.approx([2]) and math.isfinite(o['synthetic_log_likelihood'])

def test_row_1054_indirect_inference_selects_matching_binding_statistic():
 o=analysis.run('indirect_inference',{'observed_auxiliary':4.1,'parameter_grid':[1,2,3],'simulated_auxiliary':[[2,2.1],[4,4.2],[6,6.1]]})['output']
 assert o['estimate']==2 and o['binding_grid'][1]['distance']==pytest.approx(0)

def test_row_1055_method_of_moments_matches_population_moments():
 o=analysis.run('method_of_moments',{'values':[1,2,3,4,5]})['output']
 assert o['estimates']=={'location':3.0,'scale_variance':2.0} and o['moment_residuals']=={'mean':0.0,'variance':0.0}

def test_row_1056_gmm_solves_orthogonality_condition():
 o=analysis.run('generalized_method_of_moments',{'instrument':[1,2,3,4],'regressor':[1,2,3,4],'outcome':[2,4,6,8]})['output']
 assert o['estimate']==pytest.approx(2) and abs(o['moment'])<1e-12

def test_row_1057_iv_recovers_effect_and_exposes_first_stage():
 o=analysis.run('instrumental_variables',{'instrument':[0,1,2,3,4],'regressor':[1,3,5,7,9],'outcome':[3,7,11,15,19]})['output']
 assert o['estimate']==pytest.approx(2) and o['intercept']==pytest.approx(1) and o['first_stage_r_squared']==pytest.approx(1)
 assert not o['weak_instrument_warning']

def test_estimation_methods_reject_underidentified_inputs():
 with pytest.raises(ValueError):analysis.run('synthetic_likelihood',{'observed_summary':[1],'simulated_summaries':[[1],[1],[1]]})
 with pytest.raises(ValueError):analysis.run('generalized_method_of_moments',{'instrument':[0,0],'regressor':[1,2],'outcome':[2,4]})
