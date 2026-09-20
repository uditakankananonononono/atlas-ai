import pytest
from app.modules.m16_executive_dashboard import analysis
DATA={'instrument':[0,1,2,3,4],'regressor':[1,3,5,7,9],'outcome':[3,7,11,15,19]}
def test_row_1058_2sls_exposes_both_stages():
 o=analysis.run('two_stage_least_squares',DATA)['output'];assert o['estimate']==pytest.approx(2) and o['intercept']==pytest.approx(1) and o['first_stage']['r_squared']==pytest.approx(1)
def test_row_1059_liml_k_class_just_identified_matches_2sls():
 o=analysis.run('limited_information_maximum_likelihood',DATA,{'k_class':1})['output'];assert o['estimate']==pytest.approx(2) and o['k_class']==1

def test_row_1060_control_function_recovers_effect_and_residual_term():
 data={'instrument':[0,1,2,3,4,5],'regressor':[1,3.1,4.9,7.2,8.8,11.1]};data['outcome']=[1+2*x+.5*(x-(1+2*z)) for z,x in zip(data['instrument'],data['regressor'])]
 o=analysis.run('control_functions',data)['output'];assert o['treatment_effect']==pytest.approx(2,abs=.002) and o['control_residual_coefficient']==pytest.approx(.5,abs=.05)

def test_row_1061_rd_estimates_intercept_jump_not_global_difference():
 x=[-2,-1,-.5,-.1,.1,.5,1,2];y=[1+v+(3 if v>=0 else 0) for v in x]
 o=analysis.run('regression_discontinuity',{'running_variable':x,'outcome':y},{'cutoff':0,'bandwidth':2})['output'];assert o['treatment_effect_at_cutoff']==pytest.approx(3) and o['left_slope']==pytest.approx(1) and o['right_slope']==pytest.approx(1)

def test_row_1062_did_removes_shared_time_trend():
 o=analysis.run('difference_in_differences',{'treated':[0,0,1,1],'post':[0,1,0,1],'outcome':[10,12,9,16]})['output'];assert o['effect']==pytest.approx(5) and o['group_changes']=={'control':2.0,'treated':7.0}

def test_causal_estimators_reject_unidentified_designs():
 with pytest.raises(ValueError):analysis.run('two_stage_least_squares',{'instrument':[1,1,1],'regressor':[1,2,3],'outcome':[1,2,3]})
 with pytest.raises(ValueError):analysis.run('difference_in_differences',{'treated':[0,1],'post':[0,1],'outcome':[1,2]})
