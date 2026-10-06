import pytest
from app.modules.m20_general_cognitive_worker.measured_learning import recall_practice, deliberate_practice


def item():return {'id':'1','question':'capital of Assam','accepted_answers':['Dispur'],'skill':'geography'}
def attempt(response):return {'evidence_id':'e','item_id':'1','response':response,'confidence':.9,'closed_book':True,'attempted_at':'2026-10-07T10:00:00+05:30'}


def test_recall_actually_scores_response_and_retry_changes_with_outcome():
 wrong=recall_practice({'recall_items':[item()],'recall_attempts':[attempt('Guwahati')]})
 right=recall_practice({'recall_items':[item()],'recall_attempts':[attempt('  DISPUR  ')]})
 assert not wrong['results'][0]['correct'] and right['results'][0]['correct']
 assert wrong['results'][0]['retry_due_at']=='2026-10-07T11:00:00+05:30'
 assert right['results'][0]['retry_due_at'] is None
 assert wrong['results'][0]['brier_loss']==pytest.approx(.81)
 assert right['results'][0]['brier_loss']==pytest.approx(.01)


def test_unattempted_recall_prompts_do_not_expose_answers_or_invent_mastery():
 r=recall_practice({'recall_items':[item()]})
 assert 'accepted_answers' not in r['unattempted_items'][0]
 assert r['attempt_count']==0 and r['skill_scores']==[]


def test_non_closed_book_and_reused_evidence_rejected():
 a=attempt('Dispur')
 with pytest.raises(ValueError):recall_practice({'recall_items':[item()],'recall_attempts':[{**a,'closed_book':False}]})
 with pytest.raises(ValueError):recall_practice({'recall_items':[item()],'recall_attempts':[a,a]})


def test_deliberate_practice_targets_measured_weakness_and_changes_with_scores():
 rows=[{'evidence_id':'a','skill':'math','succeeded':False,'feedback':'sign error'},{'evidence_id':'b','skill':'reading','succeeded':True,'feedback':'all correct'}]
 exercises=[{'id':'m','skill':'math','task':'correct sign'},{'id':'r','skill':'reading','task':'read paragraph'}]
 first=deliberate_practice({'scored_attempts':rows,'exercise_catalog':exercises})
 assert first['target_subskills']==['math'] and first['selected_exercises'][0]['id']=='m'
 rows[0]['succeeded']=True;rows[1]['succeeded']=False
 second=deliberate_practice({'scored_attempts':rows,'exercise_catalog':exercises})
 assert second['target_subskills']==['reading']


def test_missing_exercise_for_weakness_is_explicit_not_generated_filler():
 r=deliberate_practice({'scored_attempts':[{'evidence_id':'a','skill':'math','succeeded':False,'feedback':'sign'}],
    'exercise_catalog':[{'id':'r','skill':'reading','task':'read'}]})
 assert r['missing_exercise_skills']==['math'] and r['selected_exercises']==[]
