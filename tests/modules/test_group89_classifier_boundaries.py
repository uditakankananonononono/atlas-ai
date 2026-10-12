"""Controlled logits test, not model-quality or actual inference evidence."""
import hashlib
import sys
import types
import torch
import pytest
from app.modules.c32.learned_affect import LearnedAffect,REVISION


def test_controlled_logits_sigmoid_threshold_and_nonperson_scope(monkeypatch):
    monkeypatch.setitem(sys.modules,'transformers',types.SimpleNamespace(AutoTokenizer=object,AutoModelForSequenceClassification=object))
    engine=LearnedAffect(threshold=.5)
    engine._tokenizer=lambda *a,**kw:{'input_ids':torch.tensor([[1,2]])}
    class Model:
        config=types.SimpleNamespace(id2label={0:'joy',1:'anger'})
        def __call__(self,**kw):return types.SimpleNamespace(logits=torch.tensor([[2.,-2.]]))
    engine._model=Model()
    out=engine.analyze('supplied passage','context')
    assert out['scores']==[{'label':'joy','score':pytest.approx(.880797,abs=1e-6)}, {'label':'anger','score':pytest.approx(.119203,abs=1e-6)}]
    assert [v['label'] for v in out['labels']]==['joy']
    assert out['source_text_sha256']==hashlib.sha256(b'supplied passage').hexdigest()
    assert out['model_revision']==REVISION
    assert out['personality_inferred'] is False and out['claims_feeling'] is False
    with pytest.raises(ValueError,match='identity'):engine.analyze('passage','context',real_person='person')
