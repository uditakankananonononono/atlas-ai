"""hz25 pins: a partway-failed own extend is still rolled back. Chunks are
deleted as the contiguous PREFIX of positions still holding this
attempt's own objects, so an extend that raised after appending some own
chunks (and no foreign ones) leaves no own survivor, while foreign
objects past the prefix are preserved. KILL pins patch _chunk to a
5-object claim and drive a deterministic list subclass (no fifo/device,
blocking, or external probes); both fail behaviorally on the pre-hz25
backend, whose all-or-nothing identity check left the partial own prefix
behind. Bounds unchanged: append-only interleaving within this process -
no concurrency, transaction, or completed-rollback claim; a mismatch
stops the prefix and any non-contiguous own survivors stay carried."""
import os
from pathlib import Path
from datetime import datetime, timezone

import pytest

from app.modules.m25_knowledge_copilot_training.pipeline import *
from app.modules.m25_knowledge_copilot_training.schemas import *

NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)


def src(source_id='s1'):
    return SourceRegistration(
        source_id=source_id, kind='website', canonical_url=f'https://example.test/{source_id}',
        author='A', published_at=NOW, title='Title',
        consent=ConsentRecord(granted_by='owner', granted_at=NOW,
                              purposes=['knowledge_ingestion'], evidence='consent-1'))


def pipe(tmp_path, **kw):
    return LocalKnowledgePipeline(tmp_path, 'tenant-a', 'actor-a', clock=lambda: NOW, **kw)


def req():
    return IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a')


def fd_count():
    return len(os.listdir('/proc/self/fd'))


def five_chunk_claim(monkeypatch):
    # _chunk normally returns 1 object per version here; a 5-object claim
    # makes partial extends distinguishable from full ones.
    monkeypatch.setattr(LocalKnowledgePipeline, '_chunk', lambda self, rec, version: [object() for _ in range(5)])


def test_hz25_partial_own_extend_is_fully_rolled_back(tmp_path, monkeypatch):
    # KILL: pre-hz25 the chunk rollback required ALL claimed chunks to
    # survive the identity check, so an extend that appended 1 of 5 own
    # chunks and then raised left that 1 OWN chunk behind with no foreign
    # mutation anywhere. hz25 deletes the contiguous own prefix: the
    # partial claim is removed, the original ValueError propagates.
    five_chunk_claim(monkeypatch)
    p = pipe(tmp_path)
    class PartialChunks(list):
        def extend(self, items):
            for it in items:
                self.append(it)
                raise ValueError('extend exploded after 1 of 5')
    p.chunks = PartialChunks()
    before = fd_count()
    with pytest.raises(ValueError, match='extend exploded after 1 of 5'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    assert p.chunks == []
    assert p.edges == []
    assert not (tmp_path / 'tenant-a' / 's1' / 'v1').exists()


def test_hz25_foreign_chunk_after_partial_own_extend_survives(tmp_path, monkeypatch):
    # KILL: same partial failure, but a FOREIGN chunk sits right after the
    # own prefix. Pre-hz25 nothing was deleted (all-or-nothing mismatch),
    # leaving the own chunk; the truthful outcome removes only the own
    # prefix and preserves the foreign object.
    five_chunk_claim(monkeypatch)
    p = pipe(tmp_path)
    foreign = object()
    class InterleavingChunks(list):
        def extend(self, items):
            for it in items:
                self.append(it)
                self.append(foreign)
                raise ValueError('extend exploded after own+foreign')
    p.chunks = InterleavingChunks()
    before = fd_count()
    with pytest.raises(ValueError, match=r'extend exploded after own\+foreign'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    assert p.chunks == [foreign]
    assert p.edges == []


def test_hz25_empty_failed_extend_leaves_no_trace(tmp_path, monkeypatch):
    # Compat: an extend that raises before appending anything leaves no
    # chunk state on either backend - the version and edge are still
    # rolled back by identity, and the original error propagates.
    five_chunk_claim(monkeypatch)
    p = pipe(tmp_path)
    class EmptyFailChunks(list):
        def extend(self, items):
            raise ValueError('extend exploded before appending')
    p.chunks = EmptyFailChunks()
    before = fd_count()
    with pytest.raises(ValueError, match='extend exploded before appending'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    assert p.chunks == []
    assert p.edges == []
