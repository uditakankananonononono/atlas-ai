"""Pinned pretrained English text-affect classifier, not human mind inference."""
import hashlib,math
from threading import Lock
MODEL='SamLowe/roberta-base-go_emotions'
REVISION='d75048347613a25d77de8cf6412eaae9fa7b26be'
LIMITS='Labels describe model associations with supplied English text, not a person\'s actual feelings, personality, motives or intelligence. Domain shift, sarcasm, missing context and training bias may change predictions. Scores are sigmoid outputs, not calibrated probabilities.'
class LearnedAffect:
    def __init__(self,*,threshold=.5):
        if isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not math.isfinite(threshold) or not 0<threshold<1:raise ValueError('threshold must be finite and between zero and one')
        self.threshold=threshold;self._model=None;self._tokenizer=None;self._lock=Lock()
    def analyze(self,text,field,*,real_person=None):
        if real_person is not None:raise ValueError('personality/identity inference is not supported')
        if not isinstance(text,str) or not text.strip() or len(text)>10000:raise ValueError('1..10000 characters of text required')
        if not isinstance(field,str) or not field.strip() or len(field)>64:raise ValueError('bounded field required')
        with self._lock:
            import torch
            from transformers import AutoTokenizer,AutoModelForSequenceClassification
            if self._model is None:
                self._tokenizer=AutoTokenizer.from_pretrained(MODEL,revision=REVISION,trust_remote_code=False)
                self._model=AutoModelForSequenceClassification.from_pretrained(MODEL,revision=REVISION,trust_remote_code=False,use_safetensors=True).to('cpu').eval()
            tokens=self._tokenizer(text,return_tensors='pt',truncation=False)
            if tokens['input_ids'].shape[-1]>512:raise ValueError('text exceeds model token limit; split into reviewed passages')
            with torch.no_grad():scores=torch.sigmoid(self._model(**tokens).logits)[0].tolist()
            values=[{'label':self._model.config.id2label[i],'score':float(value)} for i,value in enumerate(scores)]
        if not all(math.isfinite(v['score']) and 0<=v['score']<=1 for v in values):raise RuntimeError('invalid classifier scores')
        values.sort(key=lambda v:(-v['score'],v['label']))
        return {'field':field,'labels':[v for v in values if v['score']>=self.threshold],'scores':values,'threshold':self.threshold,'method':'pretrained multilabel text classifier','model_id':MODEL,'model_revision':REVISION,'source_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'claims_feeling':False,'personality_inferred':False,'field_is_context_label_only':True,'limits':LIMITS}
