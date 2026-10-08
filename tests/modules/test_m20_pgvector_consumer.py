"""Actual M20 semantic consumer, atomic SQL authority and authenticated route scope."""
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.vector_store import MemoryEmbeddingRow
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository, FactRow
from app.modules.m20_general_cognitive_worker.schemas import SemanticFact
from app.modules.m20_general_cognitive_worker.pgvector_memory import PgVectorSemanticMemory, vector_id


class Embedder:
    dimensions=1024
    model_id="fixture-v1"
    def embed(self, text):
        return [1.,0.]+[0.]*1022 if 'canary' in text else [0.,1.]+[0.]*1022


@pytest.fixture
def engine(tmp_path):
    server=pytest.importorskip('pgserver').get_server(tmp_path/'pg',cleanup_mode='stop')
    db=sa.create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    try:
        with db.begin() as conn:conn.execute(sa.text('CREATE EXTENSION vector'))
        GCWRepository(db).create_schema()
        MemoryEmbeddingRow.__table__.create(db)
        yield db
    finally:
        db.dispose();server.cleanup()


def make_runtime(engine, tenant):
    return GCWRuntime(GCWRepository(engine,tenant_id=tenant), embedder=Embedder(),semantic_backend='pgvector')


def test_real_product_recall_enters_task_working_memory_after_restart(engine):
    runtime=make_runtime(engine,'a')
    fact=runtime.remember_fact(SemanticFact(content='canary evidence for the goal',provenance={'uri':'fixture://a'}))
    other=make_runtime(engine,'b')
    other.remember_fact(SemanticFact(content='canary private b'))
    restarted=make_runtime(engine,'a')
    task=restarted.submit_goal('canary task',run_immediately=True)
    chunks=restarted.working_memory.focused(partition=task.id)
    assert any(c.content==fact.content and c.source=='semantic_memory' for c in chunks)
    assert all(c.content!='canary private b' for c in chunks)
    persisted=restarted.repo.list_chunks()
    assert any(c.content==fact.content and c.context_id==task.id for c in persisted)
    assert restarted.recall_facts('canary',limit=1)[0][0].provenance=={'uri':'fixture://a'}


def test_vector_failure_rolls_back_new_fact_and_existing_fact_update(engine):
    runtime=make_runtime(engine,'a')
    original=runtime.remember_fact(SemanticFact(content='canary original'))
    def fail(conn,cursor,statement,parameters,context,executemany):
        if 'memory_embeddings' in statement.lower() and statement.lstrip().upper().startswith(('INSERT','UPDATE')):
            raise RuntimeError('injected vector write failure')
    sa.event.listen(engine,'before_cursor_execute',fail)
    try:
        fresh=SemanticFact(content='canary fresh')
        with pytest.raises(RuntimeError,match='vector write'):
            runtime.remember_fact(fresh)
        with pytest.raises(RuntimeError,match='vector write'):
            runtime.remember_fact(original.model_copy(update={'content':'changed'}))
    finally:sa.event.remove(engine,'before_cursor_execute',fail)
    assert [f.content for f in runtime.repo.list_facts()]==['canary original']
    assert runtime.semantic.get(original.id).content=='canary original'
    with sa.orm.Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(MemoryEmbeddingRow))==1
        assert db.get(MemoryEmbeddingRow,vector_id('a',original.id)).text=='canary original'


def test_fail_loudly_for_invalid_backend_embedder_and_unindexed_fact(engine):
    from app.modules.m20_general_cognitive_worker.embeddings import DeterministicEmbedding
    repo=GCWRepository(engine,tenant_id='a')
    with pytest.raises(ValueError,match='1024D'):GCWRuntime(repo,semantic_backend='pgvector')
    with pytest.raises(ValueError,match='1024D'):GCWRuntime(repo,embedder=DeterministicEmbedding(),semantic_backend='pgvector')
    with pytest.raises(ValueError,match='unknown'):GCWRuntime(repo,semantic_backend='typo')
    repo.save_fact(SemanticFact(content='not indexed'))
    with pytest.raises(ValueError,match='reindex'):make_runtime(engine,'a')
    sqlite=sa.create_engine('sqlite://')
    try:
        with pytest.raises(ValueError,match='PostgreSQL'):make_runtime(sqlite,'a')
    finally:sqlite.dispose()


def test_authoritative_sql_divergence_is_not_silently_returned(engine):
    runtime=make_runtime(engine,'a');fact=runtime.remember_fact(SemanticFact(content='canary original'))
    runtime.repo.save_fact(fact.model_copy(update={'content':'unindexed replacement'}))
    with pytest.raises(ValueError,match='diverged'):runtime.recall_facts('canary')
    with pytest.raises(ValueError,match='reindex'):make_runtime(engine,'a')


def test_http_memory_routes_use_authenticated_tenant_not_body_owner(engine,monkeypatch):
    from app.auth.context import require_tenant, TenantContext
    from app.modules.m20_general_cognitive_worker import runtime_routes as routes
    monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    monkeypatch.setattr(routes,'_runtimes',{})
    routes.bind_runtime(make_runtime(engine,'a'));routes.bind_runtime(make_runtime(engine,'b'))
    app=FastAPI();app.include_router(routes.router)
    principal=TenantContext('a','alice')
    app.dependency_overrides[require_tenant]=lambda:principal
    with TestClient(app) as client:
        result=client.post('/api/modules/20/runtime/memory/facts',json={'content':'canary a'})
        assert result.status_code==201,result.text
        ident=result.json()['id']
        assert client.post('/api/modules/20/runtime/memory/facts',json={'content':'bad owner','tenant_id':'b'}).status_code==422
        assert client.post('/api/modules/20/runtime/memory/facts',json={'content':''}).status_code==422
        principal=TenantContext('b','bob')
        assert client.post('/api/modules/20/runtime/memory/recall',json={'query':'canary'}).json()==[]
        assert client.post('/api/modules/20/runtime/memory/facts',json={'id':ident,'content':'canary overwrite'}).status_code==403
        principal=TenantContext('a','alice')
        hits=client.post('/api/modules/20/runtime/memory/recall',json={'query':'canary'}).json()
        assert hits[0]['fact']['content']=='canary a'
        assert client.post('/api/modules/20/runtime/memory/recall',json={'query':'canary','limit':51}).status_code==422
    # This tests the authenticated dependency seam, not an OIDC verifier deployment.


def test_embedding_failure_and_model_change_fail_without_writes(engine):
    runtime=make_runtime(engine,'a')
    original=runtime.remember_fact(SemanticFact(content='canary original'))
    class Changed(Embedder):model_id='fixture-v2'
    with pytest.raises(ValueError,match='reindex'):
        GCWRuntime(runtime.repo,embedder=Changed(),semantic_backend='pgvector')
    for vector in ([0.]*1024, [float('nan')]+[0.]*1023, [True]+[0.]*1023, [1.,0.]):
        runtime.semantic.embedder.embed=lambda text:vector
        with pytest.raises(ValueError):runtime.remember_fact(SemanticFact(content='bad'))
    assert [f.id for f in runtime.repo.list_facts()]==[original.id]


def test_extreme_finite_embeddings_normalize_to_finite_nonzero_pgvector(engine):
    runtime=make_runtime(engine,'a')
    for value in (1e-100, 1e100):
        runtime.semantic.embedder.embed=lambda text:[value]+[0.]*1023
        fact=runtime.remember_fact(SemanticFact(content='extreme'))
        hits=runtime.recall_facts('query')
        assert all(__import__('math').isfinite(score) for _,score in hits)
        assert any(found.id==fact.id and score==pytest.approx(1.) for found,score in hits)
    runtime.semantic.embedder.embed=lambda text:[0.]*1024
    with pytest.raises(ValueError):runtime.remember_fact(fact.model_copy(update={'content':'bad update'}))
    assert runtime.repo.list_facts()[-1].content=='extreme'


def test_missing_vector_table_or_extension_fails_binding(tmp_path):
    server=pytest.importorskip('pgserver').get_server(tmp_path/'pg',cleanup_mode='stop')
    db=sa.create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    try:
        GCWRepository(db).create_schema()
        with pytest.raises(ValueError,match='extension'):make_runtime(db,'a')
        with db.begin() as conn:conn.execute(sa.text('CREATE EXTENSION vector'))
        with pytest.raises(sa.exc.DBAPIError):make_runtime(db,'a')
    finally:db.dispose();server.cleanup()


def test_extra_or_missing_vector_identity_refused_after_binding(engine):
    runtime=make_runtime(engine,'a');fact=runtime.remember_fact(SemanticFact(content='canary'))
    with sa.orm.Session(engine) as db:
        row=db.get(MemoryEmbeddingRow,vector_id('a',fact.id))
        db.add(MemoryEmbeddingRow(id='arbitrary',tenant_id='a',namespace=row.namespace,
                                 text=row.text,metadata_json=row.metadata_json,embedding=row.embedding))
        db.commit()
    with pytest.raises(ValueError,match='identity'):runtime.recall_facts('canary')
    with pytest.raises(ValueError,match='identity'):make_runtime(engine,'a')
    with sa.orm.Session(engine) as db:
        db.delete(db.get(MemoryEmbeddingRow,'arbitrary'));db.delete(db.get(MemoryEmbeddingRow,vector_id('a',fact.id)));db.commit()
    with pytest.raises(ValueError,match='identity'):runtime.recall_facts('canary')
