"""Native package import, real schemas and SQLite, no initializer bypass/mocks."""
from datetime import datetime, timedelta, timezone
import pytest
import sqlalchemy as sa
from app.modules.m20_general_cognitive_worker.schemas import ActionRecord, Episode, EpisodeOutcome, TaskContext
from app.modules.m20_general_cognitive_worker.persistence import DurableEpisodicMemory
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.repository_outcome_metacognition import gate_from_repository


def test_sqlite_disk_reload_tenant_and_unknown(tmp_path):
    url = 'sqlite:///' + str(tmp_path/'episodes.db')
    engine=sa.create_engine(url)
    repo=GCWRepository(engine,tenant_id='owner-a');repo.create_schema()
    task=TaskContext(goal='local audit fixture',tenant_id='owner-a');repo.save_task(task)
    now=datetime(2026,10,18,tzinfo=timezone.utc)
    actions=[ActionRecord(tool='inspect',succeeded=True,started_at=now+timedelta(seconds=i)) for i in range(60)]
    actions += [ActionRecord(tool='inspect',succeeded=False,outcome_unknown=True,started_at=now),
                ActionRecord(tool='retry',succeeded=False,started_at=now)]
    memory=DurableEpisodicMemory(repo)
    memory.record(Episode(task_id=task.id,goal=task.goal,actions=actions,outcome=EpisodeOutcome.ABANDONED))
    gate,stats=gate_from_repository(repo)
    assert stats=={'counted':61,'unknown_excluded':1,'malformed_skipped':0,'repository_tenant_id':'owner-a'}
    assert gate.learner.report()['inspect']['wins']==60
    assert gate.learner.report()['retry']['losses']==1
    decision=gate.decide('high')
    assert decision['action']=='eligible_pending_authority' and decision['requires_authority']
    before=gate.learner.to_state()
    with pytest.raises(ValueError):gate.run_with_fallback(None,lambda *_:True,'high')
    assert before==gate.learner.to_state()
    engine.dispose()
    engine=sa.create_engine(url)
    fresh=GCWRepository(engine,tenant_id='owner-a')
    reloaded=DurableEpisodicMemory.load(fresh)
    assert len(reloaded)==1
    gate2,stats2=gate_from_repository(fresh)
    assert stats2==stats and gate2.learner.report()==gate.learner.report()
    assert gate2.decide('high')==decision
    with pytest.raises(ValueError):gate_from_repository(GCWRepository(engine,tenant_id='owner-b'))
    engine.dispose()


def test_reject_unbound_and_policy(tmp_path):
    with pytest.raises(ValueError):gate_from_repository(object())
    engine=sa.create_engine('sqlite://')
    repo=GCWRepository(engine,tenant_id='a');repo.create_schema()
    task=TaskContext(goal='fixture');repo.save_task(task)
    repo.save_episode(Episode(task_id=task.id,goal='fixture',actions=[ActionRecord(tool='x',succeeded=True)]))
    gate,_=gate_from_repository(repo,{'low':(.1,0),'medium':(.1,0),'high':(.1,0)})
    assert gate.decide('high')['action']=='eligible_pending_authority'
    engine.dispose()


def test_overconfident_reads_are_pure_and_selection_stable():
    from app.modules.m20_general_cognitive_worker.outcome_metacognition_1975_2009 import OutcomeMetacognition
    from app.modules.m20_general_cognitive_worker.uncertainty_gate_metacognition import UncertaintyGate
    learner=OutcomeMetacognition({'a':lambda _:True,'b':lambda _:True})
    for i in range(20):learner.record('a' if i%2 else 'b',.95,False)
    gate=UncertaintyGate(learner)
    before=learner.to_state();selection=learner.select();decision=gate.decide('low')
    for _ in range(5):
        gate.conservative_confidence('a');gate.conservative_confidence('b')
        assert gate.decide('low')==decision
        assert learner.to_state()==before and learner.select()==selection
    # A deliberate reflection remains an explicit mutator.
    learner.reflect()
    assert learner.explore==1.5


def test_state_rejection_is_strict_and_atomic():
    from copy import deepcopy
    from app.modules.m20_general_cognitive_worker.outcome_metacognition_1975_2009 import OutcomeMetacognition
    learner=OutcomeMetacognition({'a':lambda _:True});learner.record('a',.5,True)
    before=learner.to_state()
    invalid=[]
    for value in [True,False,1.0,'1',None,2]:
        state=deepcopy(before);state['predictions']=[[.5,value]];invalid.append(state)
    for errors in [{'a':-1},{'a':True},{'a':.5},{'a':'1'},{'a':None},{'other':0},[],None]:
        state=deepcopy(before);state['errors']=errors;invalid.append(state)
    for state in invalid:
        with pytest.raises(ValueError):learner.load_state(state)
        assert learner.to_state()==before
    learner.load_state(deepcopy(before));assert learner.to_state()==before
