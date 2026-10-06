import math
import pytest
from app.modules.m20_general_cognitive_worker.learning_calibration import calibrate_attempts
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute, LearningReasoningError


def attempt(ident, strategy, probability, outcome):
    return dict(id=ident, strategy=strategy, evidence_id='scored-'+ident,
                predicted_success=probability, succeeded=outcome)


def test_observed_outcome_changes_loss_and_selected_strategy():
    a=attempt('a','retrieval',.9,True)
    b=attempt('b','reread',.6,True)
    first=calibrate_attempts([a,b])
    assert first['recommended_strategy']=='retrieval'
    a['succeeded']=False
    second=calibrate_attempts([a,b])
    assert second['recommended_strategy']=='reread'
    assert second['brier_loss']==pytest.approx((.81+.16)/2)
    assert second['observations'][0]['evidence_id']=='scored-a'


def test_calibration_ties_do_not_invent_a_winner():
    result=calibrate_attempts([attempt('a','A',.8,True),attempt('b','B',.8,True)])
    assert result['recommended_strategy'] is None
    assert result['best_observed_strategies']==['A','B']


@pytest.mark.parametrize('probability',[-.1,1.1,float('nan'),float('inf'),True,'0.5'])
def test_invalid_probability_is_rejected(probability):
    with pytest.raises(ValueError):calibrate_attempts([attempt('a','A',probability,True)])


def test_duplicate_attempts_and_unscored_attempts_are_rejected():
    a=attempt('a','A',.5,True)
    with pytest.raises(ValueError):calibrate_attempts([a,a])
    a['succeeded']=None
    with pytest.raises(ValueError):calibrate_attempts([a])


def test_row_823_empty_payload_cannot_claim_calibration():
    with pytest.raises(LearningReasoningError):execute('metacognition',{'objective':'learn','source':{'title':'record','url':'https://example.org'}})
