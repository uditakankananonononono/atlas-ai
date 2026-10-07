import importlib.util
import pytest
from sqlalchemy import create_engine,inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.schemas import ActionRecord


def test_action_migration_preserves_unknown_payload_roundtrip(tmp_path):
    spec=importlib.util.spec_from_file_location('migration','migrations/versions/20261007_m20_action_records.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine(f'sqlite:///{tmp_path / "actions.db"}')
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):module.upgrade()
    repo=GCWRepository(engine,tenant_id='fixture')
    action=ActionRecord(tool='fixture',succeeded=False,outcome_unknown=True,result_summary='unknown fixture')
    repo.save_action(action);repo.save_action(action)
    assert repo.list_actions()[0].model_dump(mode='json')==action.model_dump(mode='json')
    assert repo.action_summary()['local_unknown_count']==1
    assert GCWRepository(engine,tenant_id='other').list_actions()==[]
    changed=action.model_copy(update={'outcome_unknown':False})
    with pytest.raises(PermissionError):repo.save_action(changed)
    engine.dispose()
