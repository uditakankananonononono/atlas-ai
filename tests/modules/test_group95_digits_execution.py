import pytest

def test_digits_execution_uses_real_bundled_dataset_and_train_only_scaler():
    pytest.importorskip('sklearn')
    from scripts.group95_digits import run
    out=run()
    assert out['dataset']['name']=='sklearn bundled UCI handwritten digits'
    assert out['dataset']['original_count']==1797
    assert out['experiment']['training_count']>1000
    assert out['experiment']['heldout_count']>300
    assert out['experiment']['accuracy']==pytest.approx(0.86,abs=1e-12)
    assert out['experiment']['majority_baseline_accuracy']==pytest.approx(46/450,abs=1e-12)
    assert out['comparison']['standardized_logistic_accuracy']==pytest.approx(440/450,abs=1e-12)
    assert out['experiment']['training_count']==1347
    assert out['experiment']['heldout_count']==450
    assert 'Training-only standardized Euclidean' in out['experiment']['limits']
    assert out['scaling']=='fit on training only'
    assert out['experiment']['breakthrough_claim'] is False
    assert out['scope']=='One fixed public educational split, not sector-wide superiority.'

def test_scaler_fit_receives_only_training_rows(monkeypatch):
    from sklearn.preprocessing import StandardScaler
    original=StandardScaler.fit
    seen=[]
    def recorded(self,X,*args,**kwargs):
        seen.append(len(X))
        return original(self,X,*args,**kwargs)
    monkeypatch.setattr(StandardScaler,'fit',recorded)
    from scripts.group95_digits import run
    out=run()
    assert seen==[out['experiment']['training_count']]
    assert out['comparison']['same_split'] is True and out['comparison']['tuned_on_heldout'] is False
