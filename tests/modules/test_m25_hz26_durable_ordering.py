"""hz26 pins: durability ORDERING for the version-claim path. File data is
fsynced before close, the holding tmp dirfd is fsynced before the rename,
the parent dir is fsynced after the rename, and the manifest is fsynced
before replace with its directory fsynced after - so a returned manifest
never records version bytes that were not made durable first. This is an
ordering contract, NOT a general durability guarantee: filesystem/mount
fsync semantics and crash-orphaned v*.tmp-* dirs stay carried. KILL pins
wrap os.fsync deterministically (recording or failing by fd path; no
fifo/device/blocking/external probes) and fail behaviorally on the
pre-hz26 backend, which never fsynced the claim path at all."""
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


def test_hz26_success_fsyncs_every_ordering_point(tmp_path, monkeypatch):
    # KILL: pre-hz26 nothing on the version-claim path was fsynced - a
    # crash could leave a durable manifest recording version bytes that
    # never reached disk. hz26 fsyncs each ordering point; the recording
    # wrapper delegates to real fsync after capturing the fd's path.
    recorded = []
    real_fsync = os.fsync
    def rec_fsync(fd):
        try:
            recorded.append(os.readlink(f'/proc/self/fd/{fd}'))
        except OSError:
            recorded.append('<unknown>')
        return real_fsync(fd)
    monkeypatch.setattr(os, 'fsync', rec_fsync)
    p = pipe(tmp_path)
    before = fd_count()
    p.ingest(req())
    assert fd_count() == before
    names = [r.rsplit('/', 1)[-1] for r in recorded]
    assert any(n == 'source.bin' for n in names), names
    assert any(n == 'segments.json' for n in names), names
    assert any(n.startswith('v1.tmp-') for n in names), names  # held tmp dirfd, before rename
    assert any(n.startswith('manifest.json.tmp-') for n in names), names
    # The source dir is fsynced at least twice on this path: after the
    # rename (version name durable) and after the manifest replace.
    src_dir = str(tmp_path / 'tenant-a' / 's1')
    assert recorded.count(src_dir) >= 2, recorded


def test_hz26_version_fsync_failure_aborts_before_any_claim(tmp_path, monkeypatch):
    # KILL: pre-hz26 there was no fsync to fail, so the same ingest
    # succeeded. hz26 surfaces the fsync OSError through the ordinary
    # failure lifecycle: no version claim in memory, no version dir or
    # tmp dir on disk, original error propagates.
    real_fsync = os.fsync
    def fail_fsync(fd):
        try:
            name = os.readlink(f'/proc/self/fd/{fd}')
        except OSError:
            name = ''
        if name.endswith('source.bin'):
            raise OSError('fsync failed')
        return real_fsync(fd)
    monkeypatch.setattr(os, 'fsync', fail_fsync)
    p = pipe(tmp_path)
    before = fd_count()
    with pytest.raises(OSError, match='fsync failed'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    s1 = tmp_path / 'tenant-a' / 's1'
    assert not (s1 / 'v1').exists()
    assert not any(x.name.startswith('v1.tmp-') for x in s1.iterdir())


def test_hz26_happy_path_outcome_unchanged(tmp_path):
    # Compat: with no fault injection, a successful ingest records the
    # version and the exact source bytes, same as before. Passes old and
    # new.
    p = pipe(tmp_path)
    before = fd_count()
    version = p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions[-1].number == version.number
    assert (tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin').read_bytes() == b'Alpha fact.'
