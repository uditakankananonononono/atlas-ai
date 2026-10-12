from datetime import date
from app.modules.m23_study_abroad.roadmap_progress import reconcile

def test_reflow_completed_hours_do_not_stay_in_pending_schedule():
    curriculum={'domains':[{'id':'math','name':'Math'}],'steps':[
        {'id':'a','domain':'math','title':'a','hours':20,'after':[]},
        {'id':'b','domain':'math','title':'b','hours':30,'after':['a']},
        {'id':'c','domain':'math','title':'c','hours':10,'after':['b']}]}
    roadmap={'schedule':{'weekly_hours':10,'horizon_weeks':4,'total_hours':60,
                         'steps':[dict(s,start_week=3,end_week=7) for s in curriculum['steps']]}}
    result=reconcile(roadmap,curriculum,[{'step_id':'a','completed_at':'2026-10-01','artifact_url':'https://example.org/a'}],today=date(2026,10,12),reflow=True)
    assert result['schedule']['remaining_hours']==40
    assert result['schedule']['steps'][0]['start_week']==1
    assert result['schedule']['steps'][0]['end_week']==3
    assert result['schedule']['steps'][1]['start_week']==4
    assert result['next_ready']==['b']
    assert roadmap['schedule']['steps'][0]['start_week']==3

def test_formerly_unscheduled_step_reenters_after_completed_prerequisite():
    curriculum={'domains':[{'id':'math','name':'Math'}],'steps':[
        {'id':'a','domain':'math','title':'a','hours':20,'after':[]},
        {'id':'b','domain':'math','title':'b','hours':10,'after':['a']}]}
    roadmap={'schedule':{'weekly_hours':10,'horizon_weeks':2,'total_hours':30,
                         'steps':[dict(curriculum['steps'][0],start_week=1,end_week=2)],
                         'unscheduled':[{'id':'b','reason':'beyond_horizon'}]}}
    out=reconcile(roadmap,curriculum,[{'step_id':'a','completed_at':'2026-10-01','artifact_url':'https://example.org/a'}],today=date(2026,10,12),reflow=True)
    assert out['schedule']['steps'][0]['id']=='b'
    assert out['schedule']['steps'][0]['start_week']==1
    assert out['schedule']['remaining_hours']==10
    assert out['schedule']['original_total_hours']==30
    assert 'total_hours' not in out['schedule']

def test_future_evidence_and_missing_prerequisite_refuse():
    import pytest
    curriculum={'domains':[{'id':'math','name':'Math'}],'steps':[
        {'id':'a','domain':'math','title':'a','hours':20,'after':[]},
        {'id':'b','domain':'math','title':'b','hours':10,'after':['a']}]}
    roadmap={'schedule':{'weekly_hours':10,'horizon_weeks':4,'total_hours':30,'steps':curriculum['steps']}}
    for evidence in ([{'step_id':'a','completed_at':'2026-10-13','artifact_url':'https://example.org/a'}],
                     [{'step_id':'b','completed_at':'2026-10-01','artifact_url':'https://example.org/b'}]):
        with pytest.raises(ValueError):reconcile(roadmap,curriculum,evidence,today=date(2026,10,12),reflow=True)
