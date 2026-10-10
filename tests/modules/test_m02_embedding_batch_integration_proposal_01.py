"""UNAPPLIED integration acceptance tests, authored-not-run.

Require peer wiring patch. Fail explicitly if absent, never silently skip.
ProfileCorpus constructor is bypassed to isolate method-level transaction
entry; constructor metadata.create_all remains outside this narrow unit.
"""
import asyncio
from types import SimpleNamespace
import pytest


class Provider:
    def __init__(self, batch):
        self.batch, self.calls = batch, 0
    async def embed(self, texts):
        self.calls += 1
        return self.batch


class GuardSessions:
    def __init__(self):
        self.entries = 0
    def begin(self):
        self.entries += 1
        raise AssertionError('transaction entered for rejected batch')
    def __call__(self):
        self.entries += 1
        raise AssertionError('session opened for rejected query')


def corpus(batch, sessions):
    from app.modules.m02_competition_manager import profile_corpus as module
    assert hasattr(module, 'validate_embedding_batch'), 'Peer wiring proposal is not applied'
    instance = object.__new__(module.ProfileCorpus)
    instance.tenant_id, instance.embedder, instance.sessions = 'owner-a', Provider(batch), sessions
    return instance


@pytest.mark.parametrize('batch', [[], [[1, 2]], [[1, 2], [3]],
                                  [[1, 2], [3, True]], [[1, 2]] * 3])
def test_ingest_rejection_never_enters_transaction(batch):
    sessions = GuardSessions()
    instance = corpus(batch, sessions)
    with pytest.raises(ValueError):
        asyncio.run(instance.ingest([SimpleNamespace(text='a'), SimpleNamespace(text='b')]))
    assert sessions.entries == 0


def test_empty_sources_rejected_before_provider_or_transaction():
    sessions = GuardSessions()
    instance = corpus([], sessions)
    with pytest.raises(ValueError):
        asyncio.run(instance.ingest([]))
    assert instance.embedder.calls == 0 and sessions.entries == 0


@pytest.mark.parametrize('batch', [[], [[1], [2]], [[]], [[float('nan')]], [[True]]])
def test_invalid_query_batch_rejected_before_read_session(batch):
    sessions = GuardSessions()
    instance = corpus(batch, sessions)
    with pytest.raises(ValueError):
        asyncio.run(instance.retrieve('query'))
    assert sessions.entries == 0


class ReadSession:
    def __init__(self, rows): self.rows = rows
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def scalars(self, statement): return self.rows


def test_stored_vector_must_match_query_before_ranking():
    instance = corpus([[1, 2]], lambda: ReadSession([SimpleNamespace(embedding=[1])]))
    with pytest.raises(ValueError):
        asyncio.run(instance.retrieve('query'))


def test_empty_corpus_remains_empty_with_valid_query():
    instance = corpus([[1, 2]], lambda: ReadSession([]))
    assert asyncio.run(instance.retrieve('query')) == []


def test_exact_batch_truthful_count_and_tenant_provenance(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.integrations.google_grounding import GroundedSource
    from app.modules.m02_competition_manager.profile_corpus import ProfileDocumentRow
    engine = create_engine(f"sqlite:///{tmp_path / 'batch.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    owner = corpus([[1, 0], [0, 1]], factory)
    sources = [GroundedSource('google_doc', str(i), f'docs/{i}', f'text {i}',
                             {'title': f'title {i}', 'revision_id': 'r1'}) for i in range(2)]
    assert asyncio.run(owner.ingest(sources)) == {'indexed': 2, 'created': 2}
    assert asyncio.run(owner.ingest(sources)) == {'indexed': 2, 'created': 0}
    owner.embedder.batch = [[1, 0]]
    result = asyncio.run(owner.retrieve('query'))
    assert result[0]['source_id'] == '0' and result[0]['provenance']['revision_id'] == 'r1'
    other = corpus([[1, 0]], factory)
    other.tenant_id = 'owner-b'
    assert asyncio.run(other.retrieve('query')) == []
    engine.dispose()


def test_stored_mismatch_refused_before_any_cosine_or_sort(monkeypatch):
    from app.modules.m02_competition_manager import profile_corpus as module
    from app.modules.m02_competition_manager.embedding_batch_validation_01 import EmbeddingBatchValidationError
    class RankingStarted(RuntimeError):
        pass
    def ranking_bomb(*args):
        raise RankingStarted('cosine reached during sort before full stored validation')
    monkeypatch.setattr(module, 'cos', ranking_bomb)
    rows = [SimpleNamespace(embedding=[1, 0]), SimpleNamespace(embedding=[1])]
    instance = corpus([[1, 0]], lambda: ReadSession(rows))
    with pytest.raises(EmbeddingBatchValidationError, match='dimensions'):
        asyncio.run(instance.retrieve('query'))


def test_retrieve_scores_and_order_are_not_constant_zero():
    def row(ident, vector):
        return SimpleNamespace(id=ident, embedding=vector, source_type='google_doc',
                               source_id=str(ident), locator=f'docs/{ident}',
                               title=f'title {ident}', text='source', provenance={'revision_id': 'r1'})
    rows = [row(1, [0, 1]), row(2, [-1, 0]), row(3, [1, 0])]
    instance = corpus([[1, 0]], lambda: ReadSession(rows))
    result = asyncio.run(instance.retrieve('query'))
    assert [item['id'] for item in result] == [3, 1, 2]
    assert [item['score'] for item in result] == [1.0, 0.0, -1.0]


@pytest.mark.parametrize('endpoint,payload', [
    ('google-docs', {'document_ids': ['doc-a']}),
    ('google-sheets', {'spreadsheet_id': 'sheet-a', 'ranges': ['A1:B2']}),
    ('retrieve', {'query': 'query'})])
def test_profile_http_422_and_google_client_close(monkeypatch, endpoint, payload):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m02_competition_manager import profile_routes as routes
    from app.modules.m02_competition_manager.embedding_batch_validation_01 import EmbeddingBatchValidationError
    assert hasattr(routes, 'EmbeddingBatchValidationError'), 'Peer route wiring not applied'
    clients = []
    class Grounder:
        def __init__(self):
            self.closed = 0
            clients.append(self)
        async def document(self, ident):
            return SimpleNamespace(text='doc text')
        async def sheet(self, ident, ranges):
            return [SimpleNamespace(text='sheet text')]
        async def close(self):
            self.closed += 1
    def make_corpus(tenant, provider):
        return corpus([[float('nan')]], GuardSessions())
    monkeypatch.setattr(routes, 'GoogleWorkspaceGrounder', Grounder)
    monkeypatch.setattr(routes, 'corpus', make_corpus)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.require_tenant] = lambda: SimpleNamespace(tenant_id='owner-a')
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(f'/competition-manager/profile-corpus/{endpoint}', json=payload)
    assert response.status_code == 422
    assert 'finite' in response.json()['detail']
    assert len(clients) == (0 if endpoint == 'retrieve' else 1)
    assert all(client.closed == 1 for client in clients)


@pytest.mark.parametrize('endpoint,payload', [
    ('google-docs', {'document_ids': ['doc-a']}),
    ('google-sheets', {'spreadsheet_id': 'sheet-a', 'ranges': ['A1:B2']})])
def test_google_client_closes_when_grounding_itself_fails(monkeypatch, endpoint, payload):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m02_competition_manager import profile_routes as routes
    clients = []
    class Grounder:
        def __init__(self):
            self.closed = 0
            clients.append(self)
        async def document(self, ident):
            raise RuntimeError('grounding failed')
        async def sheet(self, ident, ranges):
            raise RuntimeError('grounding failed')
        async def close(self):
            self.closed += 1
    monkeypatch.setattr(routes, 'GoogleWorkspaceGrounder', Grounder)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.require_tenant] = lambda: SimpleNamespace(tenant_id='owner-a')
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(f'/competition-manager/profile-corpus/{endpoint}', json=payload)
    assert response.status_code == 500
    assert len(clients) == 1 and clients[0].closed == 1
