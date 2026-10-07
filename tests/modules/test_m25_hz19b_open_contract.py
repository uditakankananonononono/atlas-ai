"""hz19b pins: opened-descriptor type contract, non-blocking open, error/FD
lifecycle, and writer-side manifest bound. KILL pins fail on hz19
(fc6f2749); the stat/open swap pin fails there by BLOCKING inside os.open
(the alarm converts the hang into the detected failure). Race/TOCTOU
residuals (parent-component swap, post-open content drift, fsync and
durability) stay carried, not claimed."""
import os
import stat
import signal
from pathlib import Path
from datetime import datetime, timezone

import pytest

from app.modules.m25_knowledge_copilot_training.pipeline import *
from app.modules.m25_knowledge_copilot_training.schemas import *

NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)


def src(source_id='s1', **kw):
    fields = dict(
        source_id=source_id, kind='website', canonical_url=f'https://example.test/{source_id}',
        author='A', published_at=NOW, title='Title',
        consent=ConsentRecord(granted_by='owner', granted_at=NOW,
                              purposes=['knowledge_ingestion'], evidence='consent-1'))
    fields.update(kw)
    return SourceRegistration(**fields)


def pipe(tmp_path, **kw):
    return LocalKnowledgePipeline(tmp_path, 'tenant-a', 'actor-a', clock=lambda: NOW, **kw)


def ingest_alpha(p):
    p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))


def test_hz19b_stat_open_swap_to_fifo_cannot_block(tmp_path, monkeypatch):
    # KILL: hz19 checked blob.stat() BEFORE open; a swap to a fifo between
    # check and open blocked the open(2) itself (no O_NONBLOCK). hz19b opens
    # O_NONBLOCK and applies the regular-file contract by fstat on the
    # OPENED descriptor, refusing without blocking. The stat mock replays
    # the stale 'regular' verdict; on hz19 the alarm fires inside os.open,
    # which is the failure this pin detects there.
    p = pipe(tmp_path)
    ingest_alpha(p)
    blob = tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin'
    blob.unlink()
    os.mkfifo(blob)
    orig_stat = Path.stat
    def stale_regular(self, *a, **kw):
        if self == blob:
            return os.stat_result((stat.S_IFREG | 0o644, 1, 1, 1, 0, 0, 100, 0, 0, 0))
        return orig_stat(self, *a, **kw)
    monkeypatch.setattr(Path, 'stat', stale_regular)
    class Blocked(Exception): pass
    def on_alarm(signum, frame): raise Blocked()
    previous = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(3)
    try:
        with pytest.raises(KnowledgeError, match='not a regular file'):
            ingest_alpha(p)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def test_hz19b_fdopen_failure_maps_and_closes_fd(tmp_path, monkeypatch):
    # KILL: hz19 surfaced a raw OSError from a failing fdopen and leaked the
    # os.open descriptor; hz19b maps it to the refusal contract and closes
    # the descriptor on every path.
    p = pipe(tmp_path)
    ingest_alpha(p)
    fds_before = len(os.listdir('/proc/self/fd'))
    def boom(fd, *a, **kw): raise OSError('fdopen boom')
    monkeypatch.setattr(os, 'fdopen', boom)
    with pytest.raises(KnowledgeError, match='unreadable'):
        ingest_alpha(p)
    assert len(os.listdir('/proc/self/fd')) == fds_before


def test_hz19b_read_oserror_maps_to_refusal_contract(tmp_path, monkeypatch):
    # KILL: hz19 let an OSError from the buffered read escape raw; hz19b
    # maps it to the refusal contract. The fdopen mock returns a stand-in,
    # so this pin intentionally does not assert descriptor counts.
    p = pipe(tmp_path)
    ingest_alpha(p)
    class FailingRead:
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def read(self, n=-1): raise OSError('read boom')
        def close(self): pass
    monkeypatch.setattr(os, 'fdopen', lambda fd, *a, **kw: FailingRead())
    with pytest.raises(KnowledgeError, match='unreadable'):
        ingest_alpha(p)


def test_hz19b_oversize_manifest_write_refused_before_mutation(tmp_path):
    # KILL: hz19's writer had no bound - unbounded metadata or version
    # growth serialized a manifest the bounded reader would then refuse.
    # hz19b fails the write BEFORE any mutation; the prior manifest bytes
    # survive untouched. Mechanism-level pin on the persist helper.
    p = pipe(tmp_path)
    rec = Record(src(), 'tenant-a')
    p._persist_manifest(rec)
    path = tmp_path / 'tenant-a' / 's1' / 'manifest.json'
    before = path.read_bytes()
    rec.versions = [Version(i + 1, 'h' * 64, [], NOW, 'text/plain') for i in range(15_000)]
    with pytest.raises(KnowledgeError, match='exceed the manifest bound'):
        p._persist_manifest(rec)
    assert path.read_bytes() == before


def test_hz19b_oversize_register_leaves_no_memory_record(tmp_path):
    # KILL (public flow): an oversize registration refuses before any
    # manifest mutation and must not leave a memory record claiming state
    # the disk does not hold.
    p = pipe(tmp_path)
    big = src(metadata={'blob': 'x' * 1_100_000})
    with pytest.raises(KnowledgeError, match='exceed the manifest bound'):
        p.register(big)
    assert 's1' not in p.records
    assert not (tmp_path / 'tenant-a' / 's1' / 'manifest.json').exists()
