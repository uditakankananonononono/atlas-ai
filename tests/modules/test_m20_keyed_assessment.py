import pytest
from app.modules.m20_general_cognitive_worker.keyed_assessment import assess
ITEMS=[{'id':'a','objective_id':'add','accepted_answers':['4'],'points':2},
       {'id':'b','objective_id':'subtract','accepted_answers':['1'],'points':3}]
def response(id,answer):return {'item_id':id,'response':answer,'evidence_id':'e'+id}
def run(row,answers,**kw):return assess(row,{'assessment_items':ITEMS,'assessment_responses':answers,**kw})


def test_summative_weights_actual_responses_not_caller_score():
 r=run(830,[response('a','4'),response('b','9')],score=1.)
 assert r['earned_points']==2 and r['possible_points']==5 and r['final_score']==.4 and r['complete']
 assert run(830,[response('a','0'),response('b','1')])['final_score']==.6


def test_formative_error_feedback_and_diagnostic_observed_needs():
 r=run(829,[response('a','0'),response('b','1')])
 assert r['items'][0]['feedback']['accepted_answers']==['4']
 assert r['items'][0]['feedback']['next_step']=='review this objective and retry'
 assert run(831,[response('a','0'),response('b','1')])['needs']==['add']


def test_unanswered_objective_is_unknown_and_no_final_grade_or_key_leak():
 r=run(830,[response('a','4')])
 assert r['final_score'] is None and r['observed_score']==1 and r['missing_item_ids']==['b']
 assert not r['complete'] and 'feedback' not in r['items'][0]
 r=run(831,[]);assert r['needs']==[] and r['unassessed_objectives']==['add','subtract']
 assert all(g['needs_review'] is None for g in r['objective_scores'])

@pytest.mark.parametrize('answers',[[response('x','1')],[response('a','4'),response('a','4')]])
def test_duplicate_unknown_responses_rejected(answers):
 with pytest.raises(ValueError):run(829,answers)


def test_bad_weights_and_duplicate_evidence_rejected():
 with pytest.raises(ValueError):assess(830,{'assessment_items':[{**ITEMS[0],'points':float('nan')}],'assessment_responses':[]})
 responses=[response('a','4'),{**response('b','1'),'evidence_id':'ea'}]
 with pytest.raises(ValueError):run(830,responses)
