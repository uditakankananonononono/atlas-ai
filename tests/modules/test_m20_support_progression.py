import pytest
from app.modules.m20_general_cognitive_worker.support_progression import progress_support,LEVELS
CAT=[{'id':l,'task':l+' real exercise','support_level':l} for l in LEVELS]

def attempt(i,level,success=True):return {'evidence_id':str(i),'task_id':level,'support_level':level,'succeeded':success}
def run(rows,**kw):return progress_support({'support_catalog':CAT,'support_attempts':rows,**kw})

def test_actual_success_evidence_fades_one_level_at_a_time():
 r=run([attempt(1,'model'),attempt(2,'model'),attempt(3,'guided'),attempt(4,'guided')])
 assert r['active_support']=='prompted' and r['selected_tasks'][0]['id']=='prompted'
 assert [h['next_support'] for h in r['history']]==['model','guided','guided','prompted']


def test_failure_restores_support_and_resets_success_streak():
 r=run([attempt(1,'guided'),attempt(2,'guided',False)],initial_support='guided')
 assert r['active_support']=='model' and r['success_streak']==0
 assert r['history'][-1]['previous_support']=='guided'


def test_empty_evidence_never_advances_and_missing_catalog_level_not_fabricated():
 assert run([])['active_support']=='model'
 r=progress_support({'support_catalog':[CAT[0]],'support_attempts':[attempt(1,'model'),attempt(2,'model')]})
 assert r['active_support']=='guided' and r['selected_tasks']==[] and r['missing_tasks_at_active_level']

@pytest.mark.parametrize('rows',[[attempt(1,'independent')],[attempt(1,'model'),attempt(1,'model')],[{'evidence_id':'1','task_id':'invented','support_level':'model','succeeded':True}]])
def test_missing_or_duplicate_or_wrong_level_evidence_rejected(rows):
 with pytest.raises(ValueError):run(rows)


def test_independent_success_cannot_advance_beyond_catalog():
 assert run([attempt(1,'independent'),attempt(2,'independent')],initial_support='independent')['active_support']=='independent'
