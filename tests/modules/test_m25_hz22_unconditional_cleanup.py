"""hz22 pins: the held dirfd is closed by ONE unconditional finally and
unexpected (non-OSError) failures leave truthful error state. KILL pins
inject deterministic non-OSError failures through the existing patch
points (no fifo/device, blocking, or external probes); they replay the
pre-hz22 leak/false-claim on the old backend behaviorally. Cleanup stays
ownership-checked and best-effort - never a completed rollback - and the
mkdir-to-open acquisition, check-to-rmtree, and rename races stay carried."""
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


def test_hz22_unexpected_write_failure_closes_fd_and_cleans_own_tmp(tmp_path, monkeypatch):
    # KILL: pre-hz22 only OSError was caught between dirfd acquisition and
    # the manifest try, so an unexpected failure from the version write
    # leaked the held descriptor and left this attempt's own tmp dir on
    # disk. hz22 closes the fd unconditionally and removes the (still
    # owned) tmp dir; the original exception propagates unchanged.
    p = pipe(tmp_path)
    def boom(self, ref, raw, segments_blob):
        raise ValueError('unexpected serialization failure')
    monkeypatch.setattr(LocalKnowledgePipeline, '_write_version_files', boom)
    before = fd_count()
    with pytest.raises(ValueError, match='unexpected serialization failure'):
        p.ingest(req())
    assert fd_count() == before
    s1 = tmp_path / 'tenant-a' / 's1'
    assert not any(x.name.startswith('v1.tmp-') for x in s1.iterdir())
    assert p.records['s1'].versions == []


def test_hz22_unexpected_persist_failure_rolls_back_memory_and_cleans_own_target(tmp_path, monkeypatch):
    # KILL: pre-hz22 an unexpected persist failure (not OSError /
    # ManifestOversizeError) escaped the rollback handler, so memory kept
    # claiming a version the manifest never recorded and the renamed
    # version dir stayed on disk. hz22 drops the unrecorded version claim
    # and removes the (still owned) dir; the original exception propagates.
    p = pipe(tmp_path)
    real_persist = LocalKnowledgePipeline._persist_manifest
    state = {'calls': 0}
    def fail_second_persist(self, rec):
        state['calls'] += 1
        if state['calls'] == 1:
            return real_persist(self, rec)
        raise RuntimeError('unexpected persist failure')
    monkeypatch.setattr(LocalKnowledgePipeline, '_persist_manifest', fail_second_persist)
    before = fd_count()
    with pytest.raises(RuntimeError, match='unexpected persist failure'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    assert not (tmp_path / 'tenant-a' / 's1' / 'v1').exists()


def test_hz22_manifest_oserror_rollback_semantics_unchanged(tmp_path, monkeypatch):
    # Compat: the accepted manifest-OSError contract is untouched by the
    # unconditional-finally restructure - memory rolls back, the durable
    # registration is preserved, the wrapped KnowledgeError is raised.
    p = pipe(tmp_path)
    real_persist = LocalKnowledgePipeline._persist_manifest
    state = {'calls': 0}
    def fail_second_persist(self, rec):
        state['calls'] += 1
        if state['calls'] == 1:
            return real_persist(self, rec)
        raise OSError('persist failed')
    monkeypatch.setattr(LocalKnowledgePipeline, '_persist_manifest', fail_second_persist)
    before = fd_count()
    with pytest.raises(KnowledgeError, match='manifest persistence failed'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    assert (tmp_path / 'tenant-a' / 's1' / 'manifest.json').exists()


def test_hz22_successful_ingest_closes_fd_and_records_version(tmp_path):
    # Compat: the happy path is unchanged - the version is recorded in
    # memory and on disk, and the held descriptor is closed.
    p = pipe(tmp_path)
    before = fd_count()
    version = p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions[-1].number == version.number
    assert (tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin').exists()
