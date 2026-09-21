import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1073_causal_tree_finds_effect_heterogeneity():
 x=[0,0,0,0,1,1,1,1];t=[0,1,0,1,0,1,0,1];y=[0,1,0,1,0,5,0,5]
 o=analysis.run('causal_forests',{'treated':t,'outcome':y,'feature':x})['output'];assert o['split']==pytest.approx(.5) and sorted(q['effect'] for q in o['leaves'])==[1,5]

def _dml(method):
 x=list(range(10));t=[.5*i+(i%2) for i in x];y=[3*v+2*i for v,i in zip(t,x)];return analysis.run(method,{'treatment':t,'outcome':y,'feature':x})['output']
def test_row_1074_dml_cross_fits_nuisance_models():
 o=_dml('double_machine_learning');assert o['estimate']==pytest.approx(3) and o['folds']==2 and abs(sum(o['orthogonal_scores'])/10)<1e-10
def test_row_1075_orthogonalized_estimation_matches_partial_linear_effect():
 o=_dml('orthogonalized_estimation');assert o['estimate']==pytest.approx(3) and o['standard_error']>=0

def test_row_1076_cross_fitting_reports_oof_error_and_no_empty_fold():
 o=analysis.run('cross_fitting',{'ids':['a','b','c','d','e','f'],'predictions':[1,2,3,4,5,6],'targets':[1,2,2,4,5,7]},{'folds':2})['output'];assert o['out_of_fold_mse']==pytest.approx(2/6) and sum(o['fold_counts'].values())==6

def test_row_1077_sample_split_is_deterministic_disjoint_and_complete():
 data={'ids':list(range(10))};a=analysis.run('sample_splitting',data,{'train_fraction':.6,'split_seed':7})['output'];b=analysis.run('sample_splitting',data,{'train_fraction':.6,'split_seed':7})['output'];assert a==b and a['disjoint'] and sorted(a['train_ids']+a['holdout_ids'])==list(range(10)) and a['train_count']==6

def test_residual_estimators_reject_no_treatment_variation():
 with pytest.raises(ValueError):analysis.run('double_machine_learning',{'treatment':[1]*6,'outcome':list(range(6)),'feature':list(range(6))})
