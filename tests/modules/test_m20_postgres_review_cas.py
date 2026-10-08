"""Scratch real-PostgreSQL compare-and-set evidence, not deployment clearance."""
import pytest
import sqlalchemy as sa
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository,MethodRow
from app.modules.m20_general_cognitive_worker.persistence import DurableHTNPlanner
from app.modules.m20_general_cognitive_worker.schemas import HTNMethod,PlanNode,MethodSource
from app.modules.m20_general_cognitive_worker.risk_register import DurableRiskRegister

@pytest.fixture
def engine(tmp_path):
    pgserver=pytest.importorskip('pgserver');pytest.importorskip('psycopg')
    server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
    engine=sa.create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    GCWRepository(engine,tenant_id='fixture').create_schema()
    yield engine
    engine.dispose()


def planner(engine):
    repo=GCWRepository(engine,tenant_id='fixture')
    first=DurableHTNPlanner(repo,require_review=True)
    first.register_method(HTNMethod(name='fixture',goal_pattern='fixture',source=MethodSource.LEARNED,proposer_actor_id='fixture-proposer',subtasks=[PlanNode(title='reviewed')]))
    return repo,first


def test_postgres_review_activation_matches_snapshot_and_rejects_stale_replacement(engine):
    repo,first=planner(engine)
    reviewed=first.method_review_hash(first.methods['fixture'])
    assert first.activate_method('fixture',expected_hash=reviewed,actor_id='fixture-reviewer',roles={'atlas-reviewer'})
    other=DurableHTNPlanner.load(GCWRepository(engine,tenant_id='fixture'),require_review=True)
    replacement=other.methods['fixture'].model_copy(deep=True)
    replacement.subtasks[0].title='replacement'
    other.register_method(replacement)
    with pytest.raises(PermissionError,match='revision'):
        first.activate_method('fixture',expected_hash=reviewed,actor_id='fixture-reviewer',roles={'atlas-reviewer'})
    assert repo.list_methods()[0][1]=='proposed'


def test_postgres_separate_writer_between_check_and_update_rejected(engine):
    repo,first=planner(engine)
    reviewed=first.method_review_hash(first.methods['fixture'])
    replacement=first.methods['fixture'].model_copy(deep=True)
    replacement.subtasks[0].title='separately committed replacement'
    changed=[]
    def race(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('UPDATE M20_HTN_METHODS') and not changed:
            changed.append(True)
            with engine.begin() as other:
                payload=replacement.model_dump(mode='json');payload['review_status']='proposed'
                other.execute(sa.update(MethodRow).where(MethodRow.id==replacement.id).values(payload_json=payload,status='proposed'))
    sa.event.listen(engine,'before_cursor_execute',race)
    try:
        with pytest.raises(PermissionError,match='changed during'):
            first.activate_method('fixture',expected_hash=reviewed,actor_id='fixture-reviewer',roles={'atlas-reviewer'})
    finally:
        sa.event.remove(engine,'before_cursor_execute',race)
    assert changed and first.method_status('fixture')=='proposed'
    method,status=repo.list_methods()[0]
    assert method.subtasks[0].title==replacement.subtasks[0].title and status=='proposed'


def test_postgres_two_risk_revision_writers_exactly_one_commits(engine):
    repo=GCWRepository(engine,tenant_id='fixture');register=DurableRiskRegister(repo)
    risk={'id':'r','cause':'fixture','severity':5,'occurrence':3,'detection':2,'owner':'','mitigation':'','test':'','evidence':[]}
    first=register.create(goal='fixture',risks=[risk]);barrier=Barrier(2)
    def write(owner):
        local=DurableRiskRegister(GCWRepository(engine,tenant_id='fixture'))
        barrier.wait(timeout=10)
        try:
            local.revise(first['id'],expected_revision=1,risks=[{**risk,'owner':owner}])
            return 'committed',owner
        except ValueError as exc:
            assert 'revision conflict' in str(exc)
            return 'conflict',owner
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(write,['one','two']))
    assert sorted(status for status,_ in results)==['committed','conflict']
    assert [row['revision'] for row in register.history(first['id'])]==[1,2]
    assert register.get(first['id'])['report']['risks'][0]['owner']==next(owner for status,owner in results if status=='committed')
