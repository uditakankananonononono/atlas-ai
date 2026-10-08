"""Real PG/Redis M20 -> M16 status journey, replay and poison controls."""
import os
import uuid
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.schemas import TaskState
from app.modules.m20_general_cognitive_worker.event_outbox import drain_events, stream_for
from app.modules.m16_executive_dashboard.m20_subscriber import (
    StreamCursorRow,EventReceiptRow,TaskStatusRow,CONSUMER,consume_task_status,read_task_status,InvalidRuntimeEvent)

@pytest.fixture
def setup(tmp_path):
    from redis import Redis
    from app.platform.integrations import RedisStreamBus
    url=os.getenv('ATLAS_ACCEPTANCE_REDIS_URL') or os.getenv('ATLAS_REDIS_URL')
    if not url:pytest.skip('real Redis required')
    client=Redis.from_url(url,decode_responses=True);client.ping()
    server=pytest.importorskip('pgserver').get_server(tmp_path/'pg',cleanup_mode='stop')
    engine=sa.create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    a,b='a-'+str(uuid.uuid4()),'b-'+str(uuid.uuid4())
    try:
        GCWRepository(engine).create_schema()
        for table in (StreamCursorRow.__table__,EventReceiptRow.__table__,TaskStatusRow.__table__):table.create(engine)
        yield engine,RedisStreamBus(url),client,a,b
    finally:
        client.delete(stream_for(a),stream_for(b));engine.dispose();server.cleanup()


def runtime(engine,owner):
    return GCWRuntime(GCWRepository(engine,tenant_id=owner,enable_event_outbox=True))


def cursor(engine,owner):
    with Session(engine) as db:
        row=db.get(StreamCursorRow,(CONSUMER,owner))
        return row.cursor if row else '0-0'


def test_producer_drain_subscriber_http_tenant_isolation_and_duplicate(setup,monkeypatch):
    engine,bus,client,a,b=setup
    ra,rb=runtime(engine,a),runtime(engine,b)
    ta=ra.submit_goal('private a goal',run_immediately=True)
    tb=rb.submit_goal('private b goal',run_immediately=True)
    assert drain_events(engine,bus)=={'delivered':2}
    assert consume_task_status(engine,bus,a)=={'projected':1,'duplicates':0}
    assert consume_task_status(engine,bus,b)=={'projected':1,'duplicates':0}
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.context import require_tenant,TenantContext
    from app.modules.m16_executive_dashboard.routes import router,get_m20_status_engine
    app=FastAPI();app.include_router(router)
    principal=TenantContext(a,'alice')
    app.dependency_overrides[require_tenant]=lambda:principal
    app.dependency_overrides[get_m20_status_engine]=lambda:engine
    with TestClient(app) as http:
        rows=http.get('/executive-dashboard/m20-task-status').json()
        assert rows==[{'task_id':ta.id,'state':ta.state.value,'action_ids':[]}]
        assert set(rows[0])=={'task_id','state','action_ids'} and 'private' not in str(rows)
        principal=TenantContext(b,'bob')
        assert http.get('/executive-dashboard/m20-task-status').json()==[{'task_id':tb.id,'state':tb.state.value,'action_ids':[]}]
    original=bus.read(stream_for(a),last_id='0-0',count=1,block_ms=10)[0]['event']
    # A duplicate advances cursor but does NOT refresh the projection.
    changed=ta.model_copy(update={'state':TaskState.SUCCEEDED});ra.repo.save_task(changed)
    duplicate=bus.publish(stream_for(a),original)
    assert consume_task_status(engine,bus,a)=={'projected':0,'duplicates':1}
    assert cursor(engine,a)==duplicate
    assert read_task_status(engine,a)[0]['state']==ta.state.value


def test_stale_event_refreshes_authoritative_current_state_not_historical_state(setup):
    engine,bus,client,a,b=setup;r=runtime(engine,a)
    task=r.submit_goal('private',run_immediately=True)
    historical=r.repo.list_runtime_events()[0]
    r.repo.save_task(task.model_copy(update={'state':TaskState.SUCCEEDED}))
    drain_events(engine,bus)
    consume_task_status(engine,bus,a)
    assert historical['state']!=TaskState.SUCCEEDED.value
    assert read_task_status(engine,a)[0]['state']==TaskState.SUCCEEDED.value


@pytest.mark.parametrize('mutation',[
    lambda e:{**e,'goal':'private'},
    lambda e:{**e,'tenant_id':'foreign'},
    lambda e:{**e,'state':'invented'},
    lambda e:{**e,'event_id':'0'*64},
    lambda e:{**e,'action_ids':['forged']},
])
def test_poison_no_cursor_or_projection_commit_then_manual_repair(setup,mutation):
    engine,bus,client,a,b=setup;r=runtime(engine,a)
    r.submit_goal('private',run_immediately=True)
    payload={k:v for k,v in r.repo.list_runtime_events()[0].items() if k!='delivered'}
    ident=bus.publish(stream_for(a),mutation(payload))
    with pytest.raises(InvalidRuntimeEvent):consume_task_status(engine,bus,a)
    assert cursor(engine,a)=='0-0' and read_task_status(engine,a)==[]
    # Explicit operator repair of precisely this bad Redis entry, then replay
    # the SQL-authoritative payload. No code silently skips it.
    assert client.xdel(stream_for(a),ident)==1
    repaired=bus.publish(stream_for(a),payload)
    assert consume_task_status(engine,bus,a)=={'projected':1,'duplicates':0}
    assert cursor(engine,a)==repaired


def test_projection_failure_rolls_back_cursor_and_receipt(setup):
    engine,bus,client,a,b=setup;r=runtime(engine,a)
    r.submit_goal('private',run_immediately=True);drain_events(engine,bus)
    def fail(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('INSERT INTO M16_M20_TASK_STATUS'):
            raise RuntimeError('projection failure')
    sa.event.listen(engine,'before_cursor_execute',fail)
    try:
        with pytest.raises(RuntimeError,match='projection'):consume_task_status(engine,bus,a)
    finally:sa.event.remove(engine,'before_cursor_execute',fail)
    assert cursor(engine,a)=='0-0'
    with Session(engine) as db:assert db.scalar(sa.select(sa.func.count()).select_from(EventReceiptRow))==0
    assert consume_task_status(engine,bus,a)=={'projected':1,'duplicates':0}


def test_subscriber_migration_reversible_preserves_unrelated_table(tmp_path):
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec=importlib.util.spec_from_file_location('subscriber_migration','migrations/versions/20261008_m16_m20_subscriber.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    server=pytest.importorskip('pgserver').get_server(tmp_path/'pg',cleanup_mode='stop')
    engine=sa.create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    try:
        with engine.begin() as conn:
            conn.execute(sa.text('CREATE TABLE unrelated_canary (id INTEGER PRIMARY KEY)'))
            migration.op=Operations(MigrationContext.configure(conn))
            migration.upgrade();assert len(sa.inspect(conn).get_table_names())==4
            migration.downgrade();assert sa.inspect(conn).get_table_names()==['unrelated_canary']
            migration.upgrade();assert len(sa.inspect(conn).get_table_names())==4
    finally:engine.dispose();server.cleanup()


def test_concurrent_same_tenant_subscribers_commit_once(setup):
    from concurrent.futures import ThreadPoolExecutor
    engine,bus,client,a,b=setup;r=runtime(engine,a)
    r.submit_goal('private',run_immediately=True);drain_events(engine,bus)
    with ThreadPoolExecutor(2) as pool:
        futures=[pool.submit(consume_task_status,engine,bus,a) for _ in range(2)]
        results=[f.result(timeout=10) for f in futures]
    assert sum(result['projected'] for result in results)==1
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(EventReceiptRow))==1
