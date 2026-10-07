"""hz23 pins: failure handling preserves the ORIGINAL exception and exact
state boundaries. Cleanup and the best-effort manifest restore can never
mask the failure they serve; the memory claim and persist are guarded as
one region whose rollback deletes exactly the slices this attempt added.
KILL pins inject deterministic failures through monkeypatched helpers (no
fifo/device/blocking/external probes) and fail behaviorally on the
pre-hz23 backend. Scoped local boundaries - no full-transaction or
atomic-race claim."""
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


def test_hz23_cleanup_error_never_masks_original_failure(tmp_path, monkeypatch):
    # KILL: pre-hz23 the unexpected-failure handlers ran the ownership
    # cleanup unguarded, so an error from the cleanup itself replaced the
    # original exception the caller should see. hz23 routes every cleanup
    # through the never-masking wrapper: the ValueError that actually
    # failed is what propagates.
    p = pipe(tmp_path)
    def boom_write(self, ref, raw, segments_blob):
        raise ValueError('original write failure')
    def boom_cleanup(self, path, dfd):
        raise RuntimeError('cleanup exploded')
    monkeypatch.setattr(LocalKnowledgePipeline, '_write_version_files', boom_write)
    monkeypatch.setattr(LocalKnowledgePipeline, '_rmtree_if_owned', boom_cleanup)
    before = fd_count()
    with pytest.raises(ValueError, match='original write failure'):
        p.ingest(req())
    assert fd_count() == before


def test_hz23_restore_rewrite_error_never_masks_persist_failure(tmp_path, monkeypatch):
    # KILL: pre-hz23 the best-effort manifest restore inside the rollback
    # caught only OSError/ManifestOversizeError, so an unexpected rewrite
    # error masked both the original persist failure and the KnowledgeError
    # the contract promises. hz23 swallows any rewrite error there.
    p = pipe(tmp_path)
    real_persist = LocalKnowledgePipeline._persist_manifest
    state = {'calls': 0}
    def flaky_persist(self, rec):
        state['calls'] += 1
        if state['calls'] == 1:
            return real_persist(self, rec)
        if state['calls'] == 2:
            raise OSError('persist failed')
        raise RuntimeError('restore rewrite exploded')
    monkeypatch.setattr(LocalKnowledgePipeline, '_persist_manifest', flaky_persist)
    before = fd_count()
    with pytest.raises(KnowledgeError, match='manifest persistence failed'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []


def test_hz23_mid_mutation_failure_leaves_no_partial_claim(tmp_path, monkeypatch):
    # KILL: pre-hz23 the memory mutation ran OUTSIDE the guarded region,
    # so an unexpected failure partway through left a partial claim - the
    # version and chunks appended, the edge missing, the version dir on
    # disk. hz23 guards mutation and persist as one region and rolls back
    # every slice this attempt added; the original error propagates.
    p = pipe(tmp_path)
    class FailingEdges(list):
        def append(self, item):
            raise RuntimeError('edge append exploded')
    p.edges = FailingEdges()
    before = fd_count()
    with pytest.raises(RuntimeError, match='edge append exploded'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    assert p.chunks == []
    assert not (tmp_path / 'tenant-a' / 's1' / 'v1').exists()


def test_hz23_rollback_preserves_prior_state_exactly(tmp_path, monkeypatch):
    # Compat: base-slice rollback deletes only what THIS attempt added - a
    # prior successful version and its chunks survive a later failed
    # ingest untouched, on disk as well as in memory.
    p = pipe(tmp_path)
    v1 = p.ingest(req())
    real_persist = LocalKnowledgePipeline._persist_manifest
    def fail_when_claiming_v2(self, rec):
        if len(rec.versions) >= 2:
            raise OSError('persist failed')
        return real_persist(self, rec)
    monkeypatch.setattr(LocalKnowledgePipeline, '_persist_manifest', fail_when_claiming_v2)
    chunks_before = list(p.chunks)
    edges_before = list(p.edges)
    with pytest.raises(KnowledgeError, match='manifest persistence failed'):
        p.ingest(IngestRequest(source=src(), content='Beta fact - distinct content forces a v2 claim.', mime_type='text/plain', actor_id='actor-a'))
    assert [v.number for v in p.records['s1'].versions] == [v1.number]
    assert p.chunks == chunks_before
    assert p.edges == edges_before
    assert (tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin').exists()
