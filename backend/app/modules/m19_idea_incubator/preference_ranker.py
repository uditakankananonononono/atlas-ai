"""Fit and evaluate a bounded content-preference algorithm from owner labels.

A smoothed token likelihood model is a small learned ranker, not an AGI, an
owner-thinking replica, a novelty claim, or evidence that a venture will earn.
"""
from collections import Counter
from math import log, exp, isfinite
import re
from pydantic import BaseModel, Field, model_validator

class LabeledPost(BaseModel):
    post_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=10000)
    liked: bool
    source_reference: str = Field(min_length=1, max_length=240)

class RankingTrial(BaseModel):
    train: list[LabeledPost] = Field(min_length=2, max_length=2000)
    test: list[LabeledPost] = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def split(self):
        all_posts = self.train + self.test
        if len({p.post_id for p in all_posts}) != len(all_posts):
            raise ValueError('train and test ids must be unique and disjoint')
        if len({p.liked for p in self.train}) != 2:
            raise ValueError('training needs both liked and disliked examples')
        if any(not p.text.strip() for p in all_posts):
            raise ValueError('blank training/test text')
        return self

def tokens(text):
    return set(re.findall(r'[a-z0-9]{3,40}', text.lower()))

def fit(posts: list[LabeledPost]) -> dict:
    if not isinstance(posts, list) or not 2 <= len(posts) <= 2000:
        raise ValueError('training needs 2..2000 labeled posts')
    if len({p.post_id for p in posts}) != len(posts) or len({p.liked for p in posts}) != 2:
        raise ValueError('training needs unique ids and both label classes')
    pos, neg = Counter(), Counter()
    positive = sum(p.liked for p in posts)
    for p in posts:
        (pos if p.liked else neg).update(tokens(p.text))
    # Bounded vocabulary chosen without looking at held-out test labels.
    vocab = sorted(pos.keys() | neg.keys(), key=lambda t: (-(pos[t]+neg[t]),t))[:1000]
    npos, nneg = positive, len(posts)-positive
    weights = {t: log((pos[t]+1)/(npos+2))-log((neg[t]+1)/(nneg+2)) for t in vocab}
    return {'algorithm': 'smoothed_token_presence_log_ratio_v1',
            'weights': weights, 'bias': log((npos+1)/(nneg+1)),
            'training_count': len(posts), 'training_ids': [p.post_id for p in posts],
            'claim': 'owner-labeled content ranker; not general reasoning or action authority'}

def predict(model: dict, text: str) -> float:
    value = model['bias'] + sum(model['weights'].get(t, 0) for t in tokens(text))
    if not isfinite(value):
        raise ValueError('nonfinite ranker score')
    value = max(-50, min(50, value))
    return 1/(1+exp(-value))

def run_trial(trial: RankingTrial) -> dict:
    model = fit(trial.train)
    scores = [predict(model, p.text) for p in trial.test]
    majority = sum(p.liked for p in trial.train) >= len(trial.train)/2
    correct = sum((score >= .5) == p.liked for score,p in zip(scores,trial.test))
    baseline_correct = sum(majority == p.liked for p in trial.test)
    return {'model': model, 'heldout_accuracy': correct/len(scores),
            'majority_baseline_accuracy': baseline_correct/len(scores),
            'brier_score': sum((score-int(p.liked))**2 for score,p in zip(scores,trial.test))/len(scores),
            'test_count': len(scores), 'predictions': [
                {'post_id': p.post_id, 'score': score, 'source_reference': p.source_reference}
                for p,score in zip(trial.test,scores)],
            'superior_to_baseline_on_supplied_test': correct > baseline_correct,
            'external_trial_performed': False, 'commercial_success_verified': False,
            'publication_or_spend_authorized': False}
