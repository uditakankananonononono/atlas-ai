"""hz21 pins: destructive cleanup requires fd-proven ownership - the held
dirfd pins the created dir's inode against delete-then-recreate reuse, and
the pathname must still denote the SAME (dev,ino), a real directory, not a
link. KILL pins replay replacement races deterministically (regular dirs
and symlink shapes only; no fifo/device or blocking probes); the mocks
accept either write-helper signature so the kills stay behavioral on the
pre-hz21 backend. The replace race is narrowed, not atomically closed."""
import os
import shutil
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


def tmp_path_of(ref):
    # hz21 passes the held dirfd; the pre-hz21 backend passes the path.
    return Path(os.readlink(f'/proc/self/fd/{ref}')) if isinstance(ref, int) else ref


def test_hz21_tmp_replacement_is_not_deleted(tmp_path, monkeypatch):
    # KILL: pre-hz21 the write-failure cleanup ran rmtree by pathname, so a
    # DIFFERENT real directory swapped into the tmp pathname after the
    # failure was deleted as if it were this attempt's own. hz21 removes
    # only the inode the held dirfd pins; a replacement is left.
    p = pipe(tmp_path)
    marker = {}
    def fail_and_replace(self, ref, raw, segments_blob):
        tmp = tmp_path_of(ref)
        shutil.rmtree(tmp)
        tmp.mkdir()
        marker['path'] = tmp / 'keep-me'
        marker['path'].write_text('not yours')
        raise OSError('write failed')
    monkeypatch.setattr(LocalKnowledgePipeline, '_write_version_files', fail_and_replace)
    before = len(os.listdir('/proc/self/fd'))
    with pytest.raises(OSError, match='write failed'):
        p.ingest(req())
    assert len(os.listdir('/proc/self/fd')) == before
    assert marker['path'].exists()


def test_hz21_target_replacement_is_not_rolled_back(tmp_path, monkeypatch):
    # KILL: pre-hz21 the persist-failure rollback ran rmtree(target) by
    # pathname; a different real directory swapped into the version
    # pathname after the rename was deleted as if it were this attempt's
    # own. hz21 leaves it, and memory still drops the unrecorded version.
    p = pipe(tmp_path)
    real_persist = LocalKnowledgePipeline._persist_manifest
    state = {'calls': 0}
    marker = {}
    def fail_second_persist(self, rec):
        state['calls'] += 1
        if state['calls'] == 1:
            return real_persist(self, rec)
        target = tmp_path / 'tenant-a' / 's1' / 'v1'
        shutil.rmtree(target)
        target.mkdir()
        marker['path'] = target / 'keep-me'
        marker['path'].write_text('not yours')
        raise OSError('persist failed')
    monkeypatch.setattr(LocalKnowledgePipeline, '_persist_manifest', fail_second_persist)
    before = len(os.listdir('/proc/self/fd'))
    with pytest.raises(KnowledgeError, match='manifest persistence failed'):
        p.ingest(req())
    assert len(os.listdir('/proc/self/fd')) == before
    assert marker['path'].exists()
    assert p.records['s1'].versions == []


def test_hz21_own_tmp_still_cleaned_on_write_failure(tmp_path, monkeypatch):
    # Compat: a write failure still removes the tmp dir THIS attempt
    # created - the ownership check passes for the fd-pinned (dev,ino).
    p = pipe(tmp_path)
    def boom(self, ref, raw, segments_blob):
        raise OSError('write failed')
    monkeypatch.setattr(LocalKnowledgePipeline, '_write_version_files', boom)
    before = len(os.listdir('/proc/self/fd'))
    with pytest.raises(OSError, match='write failed'):
        p.ingest(req())
    assert len(os.listdir('/proc/self/fd')) == before
    s1 = tmp_path / 'tenant-a' / 's1'
    assert not any(x.name.startswith('v1.tmp-') for x in s1.iterdir())
