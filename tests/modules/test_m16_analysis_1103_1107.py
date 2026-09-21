import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1103_weighted_voting_normalizes_and_combines_probabilities():
 o=analysis.run('weighted_voting',{'predictions':[[.9,.2],[.6,.8]],'weights':[3,1]})['output'];assert o['normalized_weights']==pytest.approx([.75,.25]) and o['positive_scores']==pytest.approx([.825,.35]) and o['predictions']==[1,0]
def test_row_1104_bma_uses_stable_posterior_model_weights():
 o=analysis.run('bayesian_model_averaging',{'model_predictions':[[1,2],[3,4]],'log_evidence':[0,-2]})['output'];assert o['posterior_model_probabilities'][0]>.8 and 1<o['averaged_predictions'][0]<3 and o['between_model_variance'][0]>0
def test_row_1105_bayesian_model_selection_combines_prior_and_evidence():
 o=analysis.run('bayesian_model_selection',{'model_names':['a','b'],'log_evidence':[0,1]},{'prior_probabilities':[.9,.1]})['output'];assert o['selected_model']=='a' and sum(o['posterior_probabilities'].values())==pytest.approx(1)
def test_row_1106_information_criteria_penalize_complexity_differently():
 models=[{'name':'small','log_likelihood':-10,'parameters':2},{'name':'large','log_likelihood':-8,'parameters':8}];o=analysis.run('information_criteria',{'models':models,'sample_size':100},{'criterion':'bic'})['output'];assert o['selected_model']=='small' and o['deltas']['small']==0 and o['models'][1]['aicc']>o['models'][1]['aic']
def test_row_1107_cross_validation_weights_fold_sizes():
 o=analysis.run('cross_validation',{'fold_predictions':[[0,2],[1]],'fold_targets':[[0,0],[3]]})['output'];assert o['fold_metrics'][0]['mse']==2 and o['fold_metrics'][1]['mse']==4 and o['weighted_mse']==pytest.approx(8/3)
def test_model_combination_rejects_misalignment():
 with pytest.raises(ValueError):analysis.run('weighted_voting',{'predictions':[[.2]],'weights':[0]})
