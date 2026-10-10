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
