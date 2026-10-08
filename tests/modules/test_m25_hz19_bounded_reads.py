"""hz19 pins: bounded reads despite stat/read change, manifest input
bounds/failure handling. KILL pins fail on hz18; compat pins pass on both.
No fifo/device probes (blocking reads) - directory and symlink shapes only.
Race/TOCTOU limitations stay explicit; no whole-persistence claim."""
import json
import os
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


def test_hz19_symlinked_manifest_rejected_even_with_valid_linked_content(tmp_path):
    # KILL: hz18 read the manifest through the symlink (valid JSON, matching
    # content) and registered silently; hz19 rejects the symlinked component
    # before any read.
    p = pipe(tmp_path)
    p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))
    manifest = tmp_path / 'tenant-a' / 's1' / 'manifest.json'
    clone = tmp_path / 'tenant-a' / 'clone-manifest.json'
    clone.write_bytes(manifest.read_bytes())
    manifest.unlink()
    os.symlink(clone, manifest)
    with pytest.raises(KnowledgeError, match='symlinked path component'):
        p.register(src())


def test_hz19_oversize_manifest_refused_with_bound_message(tmp_path):
    # KILL (message contract): hz18 attempted an unbounded read of the whole
    # file and rejected only at JSON decode ('unreadable'); hz19 refuses at
    # the manifest bound. The unbounded-allocation aspect is not observable
    # in a cheap test - this pins the bound contract by its message.
    p = pipe(tmp_path)
    p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))
    (tmp_path / 'tenant-a' / 's1' / 'manifest.json').write_bytes(b' ' * 1_000_001)
    with pytest.raises(KnowledgeError, match='exceed the manifest bound'):
        p.register(src())


def test_hz19_non_regular_source_bin_refused_without_blocking(tmp_path):
    # KILL: hz18 raised only the generic OSError 'unreadable' mapping for a
    # directory-shaped source.bin; hz19 names the not-a-regular-file
    # contract. Directory shape keeps this cheap - no fifo/device blocking
    # probe.
    p = pipe(tmp_path)
    p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))
    blob = tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin'
    blob.unlink()
    blob.mkdir()
    with pytest.raises(KnowledgeError, match='not a regular file'):
        p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))


def test_hz19_valid_manifest_still_registers(tmp_path):
    # Compat: an intact manifest registers on hz18 and hz19.
    p = pipe(tmp_path)
    p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))
    assert p.register(src()).versions[0].number == 1


def test_hz19_garbage_manifest_still_fails_closed(tmp_path):
    # Compat: sub-bound garbage fails closed with the unreadable contract on
    # hz18 and hz19 (message preserved through the bounded read).
    p = pipe(tmp_path)
    p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))
    (tmp_path / 'tenant-a' / 's1' / 'manifest.json').write_bytes(b'\xff\xfe bad')
    with pytest.raises(KnowledgeError, match='unreadable'):
        p.register(src())
