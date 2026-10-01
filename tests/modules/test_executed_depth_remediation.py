import math
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute as learning, LearningReasoningError
from app.modules.m12_ai_research_lab.research_methods_135_184 import execute as research, ResearchMethodError
SRC = {'title':'Owner supplied data','url':'https://example.org/evidence'}


def test_calibration_responds_to_actual_outcomes():
    payload={'source':SRC,'objective':'calibrate','predictions':[.9]*5,'outcomes':[0]*5}
    bad=learning('metacognition',payload)['result']
    assert bad['brier_score']==pytest.approx(.81)
    assert bad['expected_calibration_error']==pytest.approx(.9)
    assert bad['adjustments'][0]['suggested_confidence']==pytest.approx(.45)
    assert len(bad['surprises'])==5
    good=learning('metacognition',{**payload,'outcomes':[1]*5})['result']
    assert good['brier_score']==pytest.approx(.01)
    assert good['adjustments'][0]['suggested_confidence']==pytest.approx(.95)
    assert 'does not persist' in ' '.join(bad['limits'])


@pytest.mark.parametrize('predictions,outcomes', [([2],[1]),([float('nan')],[1]),([.5],[]),([.5],[.3]),([True],[1])])
def test_calibration_rejects_invalid_observations(predictions,outcomes):
    with pytest.raises(LearningReasoningError):
        learning('metacognition',{'source':SRC,'objective':'x','predictions':predictions,'outcomes':outcomes})


def test_missing_data_stays_explicitly_worksheet():
    assert learning('metacognition',{'source':SRC,'objective':'x'})['result']['execution_status'].startswith('worksheet')
    assert research('hyperparameter_tuning',{'source':SRC,'task':'x','search_space':{'alpha':[1]}})['result']['tuning']['execution_status'].startswith('plan_only')
    assert research('arima_modeling',{'source':SRC,'values':[1,2,3]})['result']['arima']['execution_status'].startswith('plan_only')


def test_ridge_grid_fits_selects_and_predicts_deterministically():
    p={'source':SRC,'task':'regression','X':[[i] for i in range(30)],'y':[2*i+3 for i in range(30)],
       'search_space':{'alpha':[0,1,100]},'budget':3,'X_predict':[[40]],'inner_cv':3}
    a=research('hyperparameter_tuning',p)['result']['tuning']
    b=research('hyperparameter_tuning',p)['result']['tuning']
    assert a==b
    assert a['best_parameters']['alpha']==0
    assert a['predictions'][0]==pytest.approx(83,abs=1e-8)
    assert len(a['trials'])==3 and len(a['trials'][0]['fold_validation_mse'])==3
    assert len(a['fitted_model']['coefficients'])==1


@pytest.mark.parametrize('change', [{'y':[1]}, {'search_space':{'alpha':[-1]}}, {'budget':1}, {'estimator':'eval'}, {'time_ordered':True}, {'X':[[float('nan')]]*30}])
def test_tuning_negative_paths(change):
    p={'source':SRC,'task':'regression','X':[[i] for i in range(30)],'y':list(range(30)),
       'search_space':{'alpha':[0,1]},'budget':2}
    with pytest.raises(ResearchMethodError): research('hyperparameter_tuning',{**p,**change})


def test_arima_fits_forecasts_intervals_and_past_only_backtest():
    import random
    rng=random.Random(17)
    values=[10+.1*i+rng.gauss(0,.4) for i in range(40)]
    p={'source':SRC,'values':values,'order':[1,0,0],'execute_fit':True,'horizon':3,'backtest_steps':2}
    a=research('arima_modeling',p)['result']['arima']
    assert a['execution_status']=='executed' and len(a['forecast'])==3
    assert a['parameters'] and math.isfinite(a['aic'])
    assert all(lo<=mu<=hi for mu,(lo,hi) in zip(a['forecast'],a['intervals']))
    assert all(r['training_end_index']<r['target_index'] for r in a['rolling_origin_backtest'])
    changed=values[:]; changed[-1]+=2
    b=research('arima_modeling',{**p,'values':changed})['result']['arima']
    assert a['rolling_origin_backtest'][0]['predicted']==pytest.approx(b['rolling_origin_backtest'][0]['predicted'])


@pytest.mark.parametrize('change',[{'values':[1,2,3]}, {'order':[1,-1,0]}, {'horizon':100}, {'values':[float('nan')]*30}, {'seasonal_order':[1,0,0,7]}])
def test_arima_invalid_data_rejected(change):
    p={'source':SRC,'values':list(range(30)),'execute_fit':True,'order':[1,0,0]}
    with pytest.raises(ResearchMethodError):research('arima_modeling',{**p,**change})
