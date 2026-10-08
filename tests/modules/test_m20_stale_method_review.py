import pytest
from sqlalchemy import create_engine
from app.modules.m20_general_cognitive_worker.persistence import DurableHTNPlanner
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.schemas import HTNMethod, PlanNode, MethodSource


def test_reviewed_cached_method_cannot_activate_replacement_in_shared_store(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "methods.db"}')
    repo=GCWRepository(engine);repo.create_schema()
    first=DurableHTNPlanner(repo,require_review=True)
    first.register_method(HTNMethod(name='fixture',goal_pattern='fixture',source=MethodSource.LEARNED,proposer_actor_id='fixture-proposer',subtasks=[PlanNode(title='reviewed old')]))
    reviewed=first.method_review_hash(first.methods['fixture'])
    other=DurableHTNPlanner.load(GCWRepository(engine),require_review=True)
    other.register_method(HTNMethod(name='fixture',goal_pattern='fixture',source=MethodSource.LEARNED,proposer_actor_id='fixture-proposer',subtasks=[PlanNode(title='unreviewed replacement')]))
    with pytest.raises(PermissionError,match='revision'):
        first.activate_method('fixture',expected_hash=reviewed,actor_id='fixture-reviewer',roles={'atlas-reviewer'})
    method,status=repo.list_methods()[0]
    assert method.subtasks[0].title=='unreviewed replacement' and status=='proposed'
    engine.dispose()


def test_durable_replacement_between_hash_check_and_update_is_rejected(tmp_path,monkeypatch):
    import sqlalchemy as sa
    from app.modules.m20_general_cognitive_worker.sql_repository import MethodRow
    engine=create_engine(f'sqlite:///{tmp_path / "race.db"}')
    repo=GCWRepository(engine);repo.create_schema();first=DurableHTNPlanner(repo,require_review=True)
    first.register_method(HTNMethod(name='fixture',goal_pattern='fixture',source=MethodSource.LEARNED,proposer_actor_id='fixture-proposer',subtasks=[PlanNode(title='reviewed old')]))
    reviewed=first.method_review_hash(first.methods['fixture'])
    replacement=first.methods['fixture'].model_copy(deep=True)
    replacement.subtasks[0].title='racing replacement'
    changed=[]
    def race(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('UPDATE M20_HTN_METHODS') and not changed:
            changed.append(True)
            # Inject a concurrent-writer-equivalent payload change on the same
            # transaction connection immediately before the guarded UPDATE.
            payload=replacement.model_dump(mode='json');payload['review_status']='proposed'
            conn.execute(sa.update(MethodRow).where(MethodRow.id==replacement.id).values(payload_json=payload,status='proposed'))
    sa.event.listen(engine,'before_cursor_execute',race)
    try:
        with pytest.raises(PermissionError,match='changed during'):
            first.activate_method('fixture',expected_hash=reviewed,actor_id='fixture-reviewer',roles={'atlas-reviewer'})
        assert changed and first.method_status('fixture')=='proposed'
    finally:sa.event.remove(engine,'before_cursor_execute',race)
    assert repo.list_methods()[0][1]=='proposed'
    engine.dispose()
