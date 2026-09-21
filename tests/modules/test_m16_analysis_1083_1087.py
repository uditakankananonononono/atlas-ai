import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1083_bonferroni_reports_per_test_alpha_and_adjusted_p():
 o=analysis.run('bonferroni_correction',{'p_values':[.001,.02,.2]},{'alpha':.05})['output'];assert o['per_test_alpha']==pytest.approx(.05/3) and o['adjusted_p_values']==pytest.approx([.003,.06,.6]) and o['rejected_indices']==[0]
def test_row_1084_holm_stops_after_first_failed_step():
 o=analysis.run('holm_bonferroni',{'p_values':[.001,.03,.04,.5]},{'alpha':.05})['output'];assert o['rejected_indices']==[0] and o['steps'][1]['reject'] is False and all(not s['reject'] for s in o['steps'][1:])
def test_row_1085_bh_uses_largest_passing_rank_stepup():
 o=analysis.run('benjamini_hochberg',{'p_values':[.001,.01,.03,.2]},{'alpha':.05})['output'];assert o['largest_passing_rank']==3 and o['rejected_indices']==[0,1,2]
def test_row_1086_storey_estimates_pi0_and_qvalues():
 p=[.001,.01,.02,.6,.7,.8,.9,1.0];o=analysis.run('storeys_method',{'p_values':p},{'lambda':.5,'alpha':.05})['output'];assert 0<o['pi0']<=1 and o['rejected_indices']==[0,1] and all(0<=q<=1 for q in o['q_values'])
def test_row_1087_local_fdr_is_lower_for_extreme_zscores():
 o=analysis.run('local_fdr',{'z_scores':[0,1,5]},{'pi0':.9,'null_sd':1,'signal_sd':3,'threshold':.2})['output'];assert o['local_fdr'][0]>o['local_fdr'][1]>o['local_fdr'][2] and o['discovery_indices']==[2]
def test_correction_methods_validate_probabilities():
 with pytest.raises(ValueError):analysis.run('storeys_method',{'p_values':[.1]},{'lambda':1})
 with pytest.raises(ValueError):analysis.run('local_fdr',{'z_scores':[1]},{'pi0':1})
