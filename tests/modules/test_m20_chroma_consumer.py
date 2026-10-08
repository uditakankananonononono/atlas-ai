"""Real persistent Chroma consumer with SQL pending-index truth and crash retry."""
import os
import subprocess
import sys
import pytest
import sqlalchemy as sa
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.schemas import SemanticFact
from app.modules.m20_general_cognitive_worker.chroma_memory import ChromaIndexJob,FactIndexPending,collection_identity

class Embedder:
    dimensions=8;model_id='fixture-v1'
    def embed(self,text):return [1.]+[0.]*7

@pytest.fixture
def setup(tmp_path):
    server=pytest.importorskip('pgserver').get_server(tmp_path/'pg',cleanup_mode='stop')
    engine=sa.create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    try:
        GCWRepository(engine).create_schema();ChromaIndexJob.__table__.create(engine,checkfirst=True)
        yield engine,str(tmp_path/'chroma')
    finally:engine.dispose();server.cleanup()


def runtime(engine,path,tenant='a'):
    return GCWRuntime(GCWRepository(engine,tenant_id=tenant),semantic_backend='chroma',chroma_path=path,embedder=Embedder())


def test_pending_distinct_from_absent_then_real_chroma_recall_enters_working_memory(setup):
    engine,path=setup;r=runtime(engine,path)
    assert r.recall_facts('query')==[]
    fact=r.remember_fact(SemanticFact(content='private canary a',provenance={'uri':'fixture://a'}))
    with pytest.raises(FactIndexPending):r.recall_facts('query')
    assert r.repo.list_facts()[0].content==fact.content
    assert r.semantic.index_pending()=={'indexed':1}
    restarted=runtime(engine,path)
    task=restarted.submit_goal('canary task',run_immediately=True)
    assert any(c.content==fact.content and c.source=='semantic_memory' for c in restarted.working_memory.focused(partition=task.id))
    assert any(c.content==fact.content for c in restarted.repo.list_chunks())
    other=runtime(engine,path,'b')
    other.remember_fact(SemanticFact(content='private canary b'));other.semantic.index_pending()
    assert other.semantic.collection.name!=restarted.semantic.collection.name
    assert [f.content for f,_ in restarted.recall_facts('query')]==['private canary a']
    assert collection_identity('a','fixture-v1')!=collection_identity('b','fixture-v1')
    assert collection_identity('a','fixture-v1')!=collection_identity('a','fixture-v2')


def test_chroma_failure_never_loses_fact_and_retry_marks_only_after_readback(setup,monkeypatch):
    engine,path=setup;r=runtime(engine,path);fact=r.remember_fact(SemanticFact(content='durable'))
    def fail(**kw):raise ConnectionError('Chroma unavailable')
    monkeypatch.setattr(r.semantic.collection,'upsert',fail)
    with pytest.raises(ConnectionError):r.semantic.index_pending()
    assert r.repo.list_facts()[0].id==fact.id
    with pytest.raises(FactIndexPending):runtime(engine,path).recall_facts('query')
    monkeypatch.undo()
    assert r.semantic.index_pending()=={'indexed':1}
    assert r.recall_facts('query')[0][0].id==fact.id
    r.remember_fact(fact.model_copy(update={'content':'new snapshot'}))
    with pytest.raises(FactIndexPending):r.recall_facts('query')
    assert r.semantic.index_pending()=={'indexed':1}
    assert r.recall_facts('query')[0][0].content=='new snapshot'


def test_kill_after_chroma_write_before_sql_completion_then_fresh_process_retry(setup):
    engine,path=setup;r=runtime(engine,path);fact=r.remember_fact(SemanticFact(content='crash canary'))
    code='''
import os,sys,sqlalchemy as sa
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
class E:
 dimensions=8;model_id='fixture-v1'
 def embed(self,text):return [1.]+[0.]*7
engine=sa.create_engine(sys.argv[1]);r=GCWRuntime(GCWRepository(engine,tenant_id='a'),semantic_backend='chroma',chroma_path=sys.argv[2],embedder=E())
def kill(conn,cursor,statement,parameters,context,executemany):
 if statement.lstrip().upper().startswith('UPDATE M20_CHROMA_INDEX_JOBS'):os._exit(71)
if sys.argv[3]=='kill':sa.event.listen(engine,'before_cursor_execute',kill)
r.semantic.index_pending()
assert r.recall_facts('query')[0][0].content=='crash canary'
task=r.submit_goal('crash canary task',run_immediately=True)
assert any(c.content=='crash canary' and c.source=='semantic_memory' for c in r.working_memory.focused(partition=task.id))
engine.dispose()
'''
    result=subprocess.run([sys.executable,'-c',code,str(engine.url),path,'kill'],capture_output=True,text=True,timeout=30)
    assert result.returncode==71,result.stderr
    assert r.semantic.collection.get(ids=[fact.id])['ids']==[fact.id] # write landed
    with pytest.raises(FactIndexPending):r.recall_facts('query')
    assert r.repo.list_facts()[0].id==fact.id
    result=subprocess.run([sys.executable,'-c',code,str(engine.url),path,'retry'],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert runtime(engine,path).recall_facts('query')[0][0].id==fact.id


def test_no_automatic_reindex_for_existing_fact_or_changed_model(setup):
    engine,path=setup;r=runtime(engine,path)
    r.repo.save_fact(SemanticFact(content='old unindexed'))
    with pytest.raises(ValueError,match='reindex'):runtime(engine,path)
    assert r.repo.list_facts()[0].content=='old unindexed'


def test_http_pending_error_is_not_absent_response(setup,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.context import require_tenant,TenantContext
    from app.modules.m20_general_cognitive_worker import runtime_routes as routes
    engine,path=setup;r=runtime(engine,path)
    monkeypatch.setattr(routes,'_runtimes',{})
    routes.bind_runtime(r);app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[require_tenant]=lambda:TenantContext('a','alice')
    with TestClient(app) as http:
        assert http.post('/api/modules/20/runtime/memory/recall',json={'query':'query'}).json()==[]
        assert http.post('/api/modules/20/runtime/memory/facts',json={'content':'pending'}).status_code==201
        response=http.post('/api/modules/20/runtime/memory/recall',json={'query':'query'})
        assert response.status_code==409 and response.json()['detail']['status']=='facts_pending_index'
        r.semantic.index_pending()
        assert http.post('/api/modules/20/runtime/memory/recall',json={'query':'query'}).status_code==200


def test_job_write_failure_rolls_back_fact_and_wrong_index_snapshot_stays_pending(setup,monkeypatch):
    engine,path=setup;r=runtime(engine,path)
    def fail(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('INSERT INTO M20_CHROMA_INDEX_JOBS'):raise RuntimeError('job failed')
    sa.event.listen(engine,'before_cursor_execute',fail)
    try:
        with pytest.raises(RuntimeError,match='job failed'):r.remember_fact(SemanticFact(content='lost candidate'))
    finally:sa.event.remove(engine,'before_cursor_execute',fail)
    assert r.repo.list_facts()==[]
    fact=r.remember_fact(SemanticFact(content='durable'))
    monkeypatch.setattr(r.semantic.collection,'get',lambda **kw:{'ids':[fact.id],'documents':['wrong'],'metadatas':[{}]})
    with pytest.raises(ValueError,match='readback'):r.index_pending_facts()
    with pytest.raises(FactIndexPending):r.recall_facts('query')
    assert r.repo.list_facts()[0].content=='durable'


def test_missing_chroma_candidate_is_error_not_absent(setup):
    engine,path=setup;r=runtime(engine,path);fact=r.remember_fact(SemanticFact(content='canary'))
    r.index_pending_facts();r.semantic.collection.delete(ids=[fact.id])
    with pytest.raises(ValueError,match='identity'):r.recall_facts('query')


def test_registered_index_worker_requires_explicit_tenant_binding(setup,monkeypatch):
    from app.modules.m20_general_cognitive_worker import runtime_routes
    from app.workers.tasks import index_chroma_facts
    engine,path=setup;r=runtime(engine,path)
    monkeypatch.setattr(runtime_routes,'_runtimes',{'a':r})
    r.remember_fact(SemanticFact(content='worker fixture'))
    assert index_chroma_facts('a')=={'indexed':1}
    with pytest.raises(ValueError,match='bound'):index_chroma_facts('b')


def test_chroma_job_migration_reversible_preserves_fact_authority(tmp_path):
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec=importlib.util.spec_from_file_location('chroma_migration','migrations/versions/20261008_m20_chroma_jobs.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    server=pytest.importorskip('pgserver').get_server(tmp_path/'pg',cleanup_mode='stop')
    db=sa.create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    try:
        with db.begin() as conn:
            conn.execute(sa.text('CREATE TABLE fact_canary (id INTEGER PRIMARY KEY)'))
            conn.execute(sa.text('INSERT INTO fact_canary VALUES (1)'))
            migration.op=Operations(MigrationContext.configure(conn));migration.upgrade();migration.downgrade()
            assert conn.scalar(sa.text('SELECT count(*) FROM fact_canary'))==1
            assert 'm20_chroma_index_jobs' not in sa.inspect(conn).get_table_names()
            migration.upgrade()
    finally:db.dispose();server.cleanup()
