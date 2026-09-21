import pytest
from app.modules.m16_executive_dashboard import analysis
X=[[i] for i in range(10)];Y=[2*i for i in range(10)]
def run(m):return analysis.run(m,{'features':X,'targets':Y},{'rounds':30,'learning_rate':.2},7)['output']
def test_row_1093_gradient_boosting_reduces_residual_error():
 o=run('gradient_boosting');assert o['training_rmse']<3 and len(o['learners'])==30 and o['algorithm']=='squared_error_stump_boosting'
def test_row_1094_xgboost_regularizes_leaf_updates():
 a=analysis.run('xgboost',{'features':X,'targets':Y},{'rounds':10,'learning_rate':.2,'l2':0},7)['output'];b=analysis.run('xgboost',{'features':X,'targets':Y},{'rounds':10,'learning_rate':.2,'l2':100},7)['output'];assert abs(b['learners'][0]['left'])<abs(a['learners'][0]['left'])
def test_row_1095_lightgbm_boundary_is_explicit_and_fits():
 o=run('lightgbm');assert 'leafwise_style' in o['algorithm'] and any('histogram' in x.lower() for x in o['method_limits'])
def test_row_1096_catboost_boundary_is_explicit_and_fits():
 o=run('catboost');assert 'ordered_style' in o['algorithm'] and any('categorical' in x.lower() for x in o['method_limits'])
def test_row_1097_adaboost_reweights_mistakes_and_classifies():
 x=[[0],[1],[2],[3],[4],[5]];y=[-1,-1,-1,1,1,1];o=analysis.run('adaboost',{'features':x,'labels':y},{'rounds':10},3)['output'];assert o['training_error']==0 and o['learners'][0]['weighted_error']<.5 and sum(o['final_sample_weights'])==pytest.approx(1)
def test_boosters_validate_learning_inputs():
 with pytest.raises(ValueError):analysis.run('adaboost',{'features':[[1]],'labels':[0]})
