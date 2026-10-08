"""SQL-atomic minimal product notifications and real Redis at-least-once drain."""
import os
import pytest
import sqlalchemy as sa
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.event_outbox import RuntimeEventRow, event_values, drain_events, stream_for
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.schemas import TaskContext, TaskState, ActionRecord

@pytest.fixture
def engine(tmp_path):
    server=pytest.importorskip('pgserver').get_server(tmp_path/'pg',cleanup_mode='stop')
    engine=sa.create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    try:
        GCWRepository(engine).create_schema()
        yield engine
    finally:engine.dispose();server.cleanup()


def repo(engine,tenant='a'):
    return GCWRepository(engine,tenant_id=tenant,enable_event_outbox=True)


def test_product_checkpoint_atomic_event_replay_and_minimal_payload(engine):
    r=repo(engine);runtime=GCWRuntime(r)
    task=runtime.submit_goal('private task text canary',run_immediately=True)
    events=r.list_runtime_events()
    assert len(events)==1
    event=events[0]
    assert set(event)=={'event_id','tenant_id','task_id','state','action_ids','delivered'}
    assert event['task_id']==task.id and event['tenant_id']=='a'
    assert 'private' not in str(event)
    # The same logical checkpoint has one ID and one durable event, not a new UUID.
    r.save_execution(task,[],[])
    assert r.list_runtime_events()==events
    assert repo(engine,'b').list_runtime_events()==[]


def test_event_write_failure_rolls_back_task_checkpoint(engine):
    r=repo(engine);task=TaskContext(goal='private',tenant_id='a')
    r.save_task(task)
    changed=task.model_copy(update={'state':TaskState.SUCCEEDED})
    def fail(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('INSERT INTO M20_RUNTIME_EVENT_OUTBOX'):
            raise RuntimeError('event write failed')
    sa.event.listen(engine,'before_cursor_execute',fail)
    try:
        with pytest.raises(RuntimeError,match='event write'):r.save_execution(changed,[],[])
    finally:sa.event.remove(engine,'before_cursor_execute',fail)
    assert r.load_task(task.id).state==TaskState.PENDING
    assert r.list_runtime_events()==[]


def test_event_identity_stable_for_action_order_and_distinct_for_state_or_action():
    t=TaskContext(goal='private')
    class A:
        def __init__(self,id):self.id=id
    a,b=A('a'),A('b')
    first=event_values('owner',t,[a,b])
    assert first==event_values('owner',t,[b,a,a])
    assert first['event_id']!=event_values('owner',t,[a])['event_id']
    assert first['event_id']!=event_values('other',t,[a,b])['event_id']
    assert first['event_id']!=event_values('owner',t.model_copy(update={'state':TaskState.RUNNING}),[a,b])['event_id']
    assert set(first)=={'event_id','tenant_id','task_id','state','action_ids'}


def test_real_redis_delivery_failure_retry_and_duplicate_event_id(engine):
    from app.platform.integrations import RedisStreamBus
    from redis import Redis
    url=os.getenv('ATLAS_ACCEPTANCE_REDIS_URL') or os.getenv('ATLAS_REDIS_URL')
    if not url:pytest.skip('real Redis URL required')
    client=Redis.from_url(url,decode_responses=True);client.ping()
    import uuid
    owner='outbox-'+str(uuid.uuid4());r=repo(engine,owner)
    runtime=GCWRuntime(r);task=runtime.submit_goal('private canary',run_immediately=True)
    stream=stream_for(owner);bus=RedisStreamBus(url)
    try:
        class Failed:
            def publish(self,*args):raise ConnectionError('unavailable')
        with pytest.raises(ConnectionError):drain_events(engine,Failed())
        assert r.list_runtime_events()[0]['delivered'] is False
        # Publish succeeds, DB mark fails: retry repeats the same event_id.
        def fail(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('UPDATE M20_RUNTIME_EVENT_OUTBOX'):
                raise RuntimeError('mark failed')
        sa.event.listen(engine,'before_cursor_execute',fail)
        try:
            with pytest.raises(RuntimeError,match='mark failed'):drain_events(engine,bus)
        finally:sa.event.remove(engine,'before_cursor_execute',fail)
        assert r.list_runtime_events()[0]['delivered'] is False
        assert drain_events(engine,bus)=={'delivered':1}
        assert drain_events(engine,bus)=={'delivered':0}
        rows=bus.read(stream,last_id='0-0',count=10,block_ms=10)
        assert len(rows)==2
        assert rows[0]['event']==rows[1]['event']
        assert set(rows[0]['event'])=={'event_id','tenant_id','task_id','state','action_ids'}
        assert rows[0]['event']['event_id']==r.list_runtime_events()[0]['event_id']
        assert 'private' not in str(rows)
    finally:client.delete(stream)


def test_event_route_filters_principal_and_does_not_allow_payload_growth(engine,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.context import require_tenant,TenantContext
    from app.modules.m20_general_cognitive_worker import runtime_routes as routes
    monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    monkeypatch.setattr(routes,'_runtimes',{})
    a,b=GCWRuntime(repo(engine,'a')),GCWRuntime(repo(engine,'b'))
    routes.bind_runtime(a);routes.bind_runtime(b)
    a.submit_goal('private canary',run_immediately=True)
    principal=TenantContext('a','alice')
    app=FastAPI();app.include_router(routes.router);app.dependency_overrides[require_tenant]=lambda:principal
    with TestClient(app) as client:
        rows=client.get('/api/modules/20/runtime/events').json()
        assert len(rows)==1 and set(rows[0])=={'event_id','tenant_id','task_id','state','action_ids','delivered'}
        principal=TenantContext('b','bob')
        assert client.get('/api/modules/20/runtime/events').json()==[]
        assert client.get('/api/modules/20/runtime/events?limit=1001').status_code==422


def test_disabled_or_unsupported_outbox_fails_loudly():
    from app.workers.tasks import drain_runtime_events
    engine=sa.create_engine('sqlite://')
    try:
        with pytest.raises(ValueError,match='PostgreSQL'):repo(engine)
    finally:engine.dispose()
    if os.getenv('ATLAS_M20_EVENT_OUTBOX')!='1':
        with pytest.raises(ValueError,match='enabled'):drain_runtime_events()


def test_additive_migration_upgrade_downgrade_roundtrip(tmp_path):
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec=importlib.util.spec_from_file_location('outbox_migration','migrations/versions/20261008_m20_event_outbox.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    server=pytest.importorskip('pgserver').get_server(tmp_path/'pg',cleanup_mode='stop')
    db=sa.create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    try:
        with db.begin() as conn:
            conn.execute(sa.text('CREATE TABLE unrelated_canary (id INTEGER PRIMARY KEY)'))
            migration.op=Operations(MigrationContext.configure(conn))
            migration.upgrade()
            assert 'm20_runtime_event_outbox' in sa.inspect(conn).get_table_names()
            migration.downgrade()
            assert sa.inspect(conn).get_table_names()==['unrelated_canary']
            migration.upgrade()
            assert 'm20_runtime_event_outbox' in sa.inspect(conn).get_table_names()
    finally:db.dispose();server.cleanup()


def test_concurrent_drainers_skip_locked_event_without_duplicate_publish(engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    r=repo(engine);GCWRuntime(r).submit_goal('test only',run_immediately=True)
    entered,released=Event(),Event()
    seen=[]
    class Bus:
        def publish(self,stream,event):
            seen.append(event['event_id']);entered.set()
            assert released.wait(timeout=10)
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(drain_events,engine,Bus())
        try:
            assert entered.wait(timeout=10)
            second=pool.submit(drain_events,engine,Bus())
            assert second.result(timeout=5)=={'delivered':0}
        finally:released.set()
        assert first.result(timeout=5)=={'delivered':1}
    assert len(seen)==1


def test_missing_migrated_outbox_table_fails_enabled_binding(tmp_path):
    server=pytest.importorskip('pgserver').get_server(tmp_path/'pg',cleanup_mode='stop')
    db=sa.create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    try:
        with pytest.raises(sa.exc.DBAPIError):repo(db)
    finally:db.dispose();server.cleanup()
