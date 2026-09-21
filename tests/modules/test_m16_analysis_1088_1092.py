import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1088_permutation_fdr_selects_extreme_signal():
 nulls=[[.1,.2,.3],[.2,.1,.4],[.1,.3,.2],[.2,.2,.3]];o=analysis.run('permutation_based_fdr',{'observed_statistics':[5,.2,.1],'permuted_statistics':nulls},{'alpha':.1})['output'];assert o['rejected_indices']==[0] and o['threshold']==5 and o['permutations']==4
def test_row_1089_knockoff_filter_uses_sign_flip_statistics():
 o=analysis.run('knockoffs',{'original_importance':[10,8,1,1,1,1],'knockoff_importance':[1,1,2,2,2,2]},{'fdr':.6,'offset':1})['output'];assert o['w_statistics'][:2]==[9.0,7.0] and o['selected_indices']==[0,1]
def test_row_1090_stability_selection_reports_probabilities_and_bound():
 o=analysis.run('stability_selection',{'feature_count':4,'selections':[[0,1],[0],[0,2],[0,1],[0]]},{'selection_probability':.8})['output'];assert o['stable_indices']==[0] and o['selection_probabilities'][0]==1 and o['expected_false_positive_bound']>0
def test_row_1091_bagging_estimates_variance_and_is_seeded():
 o=analysis.run('bootstrap_aggregation',{'values':[1,2,3,4,5]},{'draws':1000},7)['output'];assert abs(o['bagged_estimate']-3)<.1 and o['bootstrap_variance']>0
def test_row_1092_random_forest_bootstraps_features_and_oob():
 x=[[i,i%2] for i in range(20)];y=[2*i for i in range(20)];o=analysis.run('random_forests',{'features':x,'targets':y},{'trees':100,'max_features':2},9)['output'];assert o['tree_count']==100 and o['oob_coverage']>.8 and o['oob_mse'] is not None
def test_selection_ensembles_validate_inputs():
 with pytest.raises(ValueError):analysis.run('knockoffs',{'original_importance':[1],'knockoff_importance':[1]},{'fdr':2})
 with pytest.raises(ValueError):analysis.run('stability_selection',{'feature_count':2,'selections':[[3]]})
