import pytest

def test_digits_execution_uses_real_bundled_dataset_and_train_only_scaler():
    pytest.importorskip('sklearn')
    from scripts.group95_digits import run
    out=run()
    assert out['dataset']['name']=='sklearn bundled UCI handwritten digits'
    assert out['dataset']['original_count']==1797
    assert out['experiment']['training_count']>1000
    assert out['experiment']['heldout_count']>300
    assert out['comparison']['standardized_logistic_accuracy']>=0
    assert out['scaling']=='fit on training only'
    assert out['experiment']['breakthrough_claim'] is False
    assert out['scope']=='One fixed public educational split, not sector-wide superiority.'
