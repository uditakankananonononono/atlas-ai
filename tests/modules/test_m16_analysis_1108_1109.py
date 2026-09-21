import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1108_leave_one_out_requires_n_minus_one_training_and_reports_uncertainty():
 o=analysis.run('leave_one_out',{'predictions':[1,2,4,4],'targets':[1,3,3,5],'train_sizes':[3,3,3,3]})['output'];assert o['training_size_per_fold']==3 and o['holdout_count']==4 and o['loo_mse']==pytest.approx(.75) and o['standard_error_mse']>=0

def test_row_1109_kfold_weights_unequal_fold_sizes_and_validates_k():
 o=analysis.run('k_fold_cross_validation',{'fold_ids':[0,0,1,1,1],'predictions':[0,2,1,1,4],'targets':[0,0,1,3,2]},{'k':2})['output'];assert o['k']==2 and o['fold_size_range']==[2,3] and o['weighted_mse']==pytest.approx(12/5) and o['every_row_held_out_once']

def test_cv_variants_reject_invalid_fold_provenance():
 with pytest.raises(ValueError):analysis.run('leave_one_out',{'predictions':[1,2],'targets':[1,2],'train_sizes':[1,0]})
 with pytest.raises(ValueError):analysis.run('k_fold_cross_validation',{'fold_ids':[0,0],'predictions':[1,2],'targets':[1,2]},{'k':2})
