import pytest
from app.modules.m20_general_cognitive_worker.model_update879 import fit_update


def data():
    return {'feature_names':['x'],'ridge':1e-8,'prior_parameters':[0,0],
            'training':[{'id':f't{i}','features':[i],'target':2*i+3,'source':'synthetic fixture'}for i in range(10)],
            'heldout':[{'id':f'h{i}','features':[i],'target':2*i+3,'source':'synthetic fixture'}for i in range(10,15)]}


def test_actual_fit_and_heldout_metrics():
    p=data();out=fit_update(p)
    assert out['fitted_parameters']==pytest.approx([3,2],abs=1e-7)
    assert out['heldout_mse_fitted']<1e-10 and out['heldout_error_reduced']
    assert not out['model_promoted'] and not out['causal_model_learned']
    assert out['training_record_ids']==[f't{i}'for i in range(10)]
    assert fit_update(p)==out


def test_holdout_never_influences_parameters():
    p=data();first=fit_update(p)
    for r in p['heldout']:r['target']=-999
    second=fit_update(p)
    assert second['fitted_parameters']==first['fitted_parameters']
    assert not second['heldout_error_reduced']


def test_disjoint_record_ids_and_nonfinite_refused():
    p=data();p['heldout'][0]['id']='t0'
    with pytest.raises(ValueError,match='disjoint'):fit_update(p)
    p=data();p['training'][0]['features']=[float('nan')]
    with pytest.raises(ValueError):fit_update(p)
    p=data();p['prior_parameters']=[True,0]
    with pytest.raises(ValueError):fit_update(p)


def test_constant_feature_and_rank_handled_without_inversion_failure():
    p=data()
    for r in p['training']:r['features']=[0];r['target']=5
    out=fit_update(p)
    assert out['fitted_parameters']==pytest.approx([5,0])
