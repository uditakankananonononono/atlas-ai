import pytest
from app.modules.c32.learned_affect import LearnedAffect

def test_actual_local_model_predicts_text_categories_without_person_claims():
    engine=LearnedAffect()
    positive=engine.analyze('I am so happy and grateful that my friends helped me succeed.','research')
    negative=engine.analyze('I am furious and angry about what happened.','research')
    assert 'joy' in {v['label'] for v in positive['labels']}
    assert 'anger' in {v['label'] for v in negative['labels']}
    assert positive['field']=='research' and positive['personality_inferred'] is False
    assert positive['claims_feeling'] is False and positive['model_revision']
    assert positive['method']=='pretrained multilabel text classifier'
    assert all(0<=v['score']<=1 for v in positive['scores'])
    assert positive['source_text_sha256']!=negative['source_text_sha256']

def test_input_and_human_identity_requests_fail_closed():
    engine=LearnedAffect()
    with pytest.raises(ValueError):engine.analyze('','research')
    with pytest.raises(ValueError):engine.analyze('x'*10001,'research')
    with pytest.raises(ValueError):engine.analyze('Tell me about them','research',real_person='someone')
