import pytest
from app.modules.m20_general_cognitive_worker.progress_measurement import measure_progress
R=[{'value':10.,'evidence_id':'1','observed_at':'2026-10-01T00:00:00+00:00'},
   {'value':6.,'evidence_id':'2','observed_at':'2026-10-03T00:00:00+00:00'}]

def test_decreasing_goal_progress_and_explicit_linear_projection():
 r=measure_progress({'records':R,'unit':'seconds','direction':'decrease','target':3,'deadline':'2026-10-05T00:00:00+00:00'})
 assert r['change']==-4 and r['improvement']==4 and r['linear_rate_per_day']==-2
 assert not r['target_reached'] and r['on_track'] and r['projected_at_deadline']==2


def test_target_reached_is_not_same_as_forecast_and_missing_deadline_unknown():
 r=measure_progress({'records':R,'unit':'seconds','direction':'decrease','target':7})
 assert r['target_reached'] and r['on_track'] is None and r['projected_at_deadline'] is None
 r=measure_progress({'records':R[:1],'unit':'seconds'})
 assert r['linear_rate_per_day'] is None and r['on_track'] is None

@pytest.mark.parametrize('records',[R[::-1],[R[0],{**R[1],'evidence_id':'1'}],[R[0],{**R[1],'unit':'dollars'}],[{**R[0],'value':float('inf')}],[{**R[0],'observed_at':'2026-10-01'}]])
def test_bad_chronology_units_nonfinite_or_duplicate_evidence_rejected(records):
 with pytest.raises(ValueError):measure_progress({'records':records,'unit':'seconds'})
