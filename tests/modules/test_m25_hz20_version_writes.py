"""hz20 pins: version-file writes get the manifest's exclusive-write
contract, dirfd-anchored at the opened tmp dir. KILL pins replay write-path
races deterministically with symlink shapes only (no fifo/device or
blocking probes): a link planted inside tmp between mkdir and write, and a
tmp swapped to a symlink after mkdir. Carried: swap above tmp, rename
TOCTOU, fsync/durability."""
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


def test_hz20_planted_source_bin_link_cannot_redirect_write(tmp_path, monkeypatch):
    # KILL: pre-hz20 the version write used plain write_bytes, which follows
    # a symlink planted inside the fresh tmp dir, writing ingest bytes
    # OUTSIDE the workspace. hz20 opens O_EXCL|O_NOFOLLOW anchored at the
    # opened tmp dirfd and refuses. The mkdir mock replays the race
    # deterministically (symlink shape only).
    escaped = tmp_path / 'escaped.bin'
    real_mkdir = Path.mkdir
    def planting_mkdir(self, *a, **kw):
        real_mkdir(self, *a, **kw)
        if self.name.startswith('v1.tmp-'):
            (self / 'source.bin').symlink_to(escaped)
    monkeypatch.setattr(Path, 'mkdir', planting_mkdir)
    p = pipe(tmp_path)
    with pytest.raises(OSError):
        p.ingest(req())
    assert not escaped.exists()


def test_hz20_tmp_swapped_to_symlink_cannot_redirect_write(tmp_path, monkeypatch):
    # KILL: pre-hz20 a tmp swapped to a symlink between mkdir and the writes
    # redirected source.bin into the linked directory and rename then turned
    # v1 itself into that symlink. hz20 opens the tmp dir O_NOFOLLOW and
    # refuses before any write. The mkdir mock replays the swap.
    outside = tmp_path / 'outside'
    outside.mkdir()
    real_mkdir = Path.mkdir
    def swapping_mkdir(self, *a, **kw):
        real_mkdir(self, *a, **kw)
        if self.name.startswith('v1.tmp-'):
            shutil.rmtree(self)
            os.symlink(outside, self)
    monkeypatch.setattr(Path, 'mkdir', swapping_mkdir)
    p = pipe(tmp_path)
    with pytest.raises(OSError):
        p.ingest(req())
    assert not (outside / 'source.bin').exists()
    assert not (tmp_path / 'tenant-a' / 's1' / 'v1').exists()


def test_hz20_version_files_still_written_and_served(tmp_path):
    # Compat: exclusive dirfd-anchored writes keep the normal ingest path
    # byte-identical - dedup still validates on-disk bytes and serves the
    # recorded version, and segments.json is written.
    p = pipe(tmp_path)
    v = p.ingest(req())
    assert v.number == 1
    again = p.ingest(req())
    assert again.number == 1
    assert (tmp_path / 'tenant-a' / 's1' / 'v1' / 'segments.json').exists()
