import pytest
from app.modules.m20_general_cognitive_worker.spaced_review import schedule_reviews


def review(**kwargs):
 row={'id':'one','evidence_id':'r1','quality':5,'reviewed_at':'2026-10-07T00:00:00+05:30'};row.update(kwargs)
 return schedule_reviews({'items':[row]})['schedule'][0]


def test_actual_sm2_first_second_third_interval_and_prior_ease():
 first=review();assert first['interval_days']==1 and first['repetitions']==1 and first['ease']==pytest.approx(2.6)
 second=review(repetitions=1,interval_days=1,ease=2.6);assert second['interval_days']==6 and second['repetitions']==2
 third=review(repetitions=2,interval_days=6,ease=2.7);assert third['interval_days']==17
 assert third['due_at']=='2026-10-24T00:00:00+05:30'


def test_lapse_resets_count_preserves_evidence_and_floors_ease():
 r=review(quality=0,repetitions=8,interval_days=100,ease=1.4)
 assert r['interval_days']==1 and r['repetitions']==0 and r['ease']==1.3
 assert r['lapse'] and r['same_session_retry_required'] and r['evidence_id']=='r1'
 assert r['due_at']=='2026-10-08T00:00:00+05:30'


def test_difficulty_changes_ease_not_fabricated_mastery():
 assert review(quality=3)['ease']<review(quality=5)['ease']
 assert not review(quality=4)['same_session_retry_required']

@pytest.mark.parametrize('changes',[{'quality':6},{'quality':True},{'ease':float('nan')},{'repetitions':-1},{'repetitions':1,'interval_days':0},{'reviewed_at':'2026-10-07'},{'evidence_id':None}])
def test_invalid_or_unobserved_review_rejected(changes):
 with pytest.raises(ValueError):review(**changes)
