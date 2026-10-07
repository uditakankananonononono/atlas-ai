import pytest
from sqlalchemy import create_engine
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.persistence import DurableRetrospectiveEngine
from app.modules.m20_general_cognitive_worker.reflection import RetrospectiveEngine


def test_snapshot_inputs_outputs_and_retrieval_are_detached():
    engine=RetrospectiveEngine();lessons=['fixture lesson'];report={'nested':{'unknown':1}}
    retro=engine.write('fixture',went_well=[],went_poorly=[],lessons=lessons,execution_report=report)
    lessons[0]='caller mutation';report['nested']['unknown']=99
    retro.lessons[0]='result mutation';retro.execution_report['nested']['unknown']=88
    retrieved=engine.lessons_for('fixture lesson')[0][0]
    assert retrieved.lessons==['fixture lesson'] and retrieved.execution_report=={'nested':{'unknown':1}}
    retrieved.lessons[0]='retrieval mutation'
    assert engine.lessons_for('fixture lesson')[0][0].lessons==['fixture lesson']


def test_durable_write_failure_never_publishes_lesson(tmp_path,monkeypatch):
    db=create_engine(f'sqlite:///{tmp_path / "retros.db"}');repo=GCWRepository(db);repo.create_schema()
    engine=DurableRetrospectiveEngine(repo)
    def fail(*args):raise RuntimeError('fixture unavailable durable store')
    monkeypatch.setattr(repo,'save_retrospective',fail)
    with pytest.raises(RuntimeError):engine.write('fixture',went_well=[],went_poorly=[],lessons=['uncommitted lesson'])
    assert len(engine)==0 and engine.lessons_for('uncommitted lesson')==[] and repo.list_retrospectives()==[]
    db.dispose()


def test_restart_preserves_identity_timestamp_and_local_execution_report(tmp_path):
    url=f'sqlite:///{tmp_path / "retros.db"}';db=create_engine(url);repo=GCWRepository(db);repo.create_schema()
    engine=DurableRetrospectiveEngine(repo)
    retro=engine.write('fixture',went_well=[],went_poorly=[],lessons=['fixture lesson'],execution_report={'local_unknown_count':1,'external_outcomes_verified':False})
    db.dispose();fresh=create_engine(url)
    restored=DurableRetrospectiveEngine.load(GCWRepository(fresh)).lessons_for('fixture lesson')[0][0]
    assert restored.id==retro.id and restored.task_id==retro.task_id and restored.created_at==retro.created_at
    assert restored.execution_report==retro.execution_report
    fresh.dispose()
