import pytest
from app.modules.m16_executive_dashboard import analysis
BASE={'base_predictions':[[1,2,3,4],[2,2,2,2]],'targets':[1,2,3,4]}
def test_row_1098_stacking_weights_oof_base_predictions():
 o=analysis.run('stacking',BASE)['output'];assert o['weights'][0]>o['weights'][1] and o['ensemble_mse']<o['base_validation_mse'][1] and o['validation_indices']==[0,1,2,3]
def test_row_1099_blending_uses_heldout_partition_only_for_weights():
 o=analysis.run('blending',BASE,{'validation_fraction':.5})['output'];assert o['validation_indices']==[2,3] and sum(o['weights'])==pytest.approx(1)
def test_row_1100_bagging_samples_with_replacement():
 o=analysis.run('bagging',{'features':[[i] for i in range(10)],'targets':list(range(10))},{'estimators':20,'sample_fraction':1},3)['output'];assert o['replacement'] and any(len(set(m['sample_indices']))<10 for m in o['models'])
def test_row_1101_pasting_samples_without_replacement():
 o=analysis.run('pasting',{'features':[[i] for i in range(10)],'targets':list(range(10))},{'estimators':20,'sample_fraction':.6},3)['output'];assert not o['replacement'] and all(len(set(m['sample_indices']))==6 for m in o['models'])
def test_row_1102_voting_supports_hard_and_soft_semantics():
 h=analysis.run('voting_classifiers',{'predictions':[[0,1,1],[1,1,0],[1,0,1]]},{'mode':'hard'})['output'];assert h['predictions']==[1,1,1] and h['vote_confidence']==pytest.approx([2/3]*3)
 s=analysis.run('voting_classifiers',{'predictions':[[.9,.2],[.7,.4]]},{'mode':'soft'})['output'];assert s['predictions']==[1,0] and s['vote_confidence']==pytest.approx([.8,.7])
def test_ensembles_reject_misaligned_predictions():
 with pytest.raises(ValueError):analysis.run('stacking',{'base_predictions':[[1,2],[1]],'targets':[1,2]})
