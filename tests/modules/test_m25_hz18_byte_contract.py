"""hz18 pins: consistent encoded-byte/read contract for valid accepted data.

KILL pins fail on hz17, whose 20000-byte guard rejected valid ingests
(20000 CHARACTERS can encode to up to 80000 UTF-8 bytes). Compat pins pass
on hz17 and hz18."""
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


def test_hz18_multibyte_content_dedups_and_registers(tmp_path):
    # KILL: hz17 rejected this valid accepted ingest at dedup/register time
    # ('exceed the ingest bound') - 15000 e-acute characters are 30000
    # UTF-8 bytes on disk, inside the 20000-character schema bound.
    p = pipe(tmp_path)
    text = '\u00e9' * 15000
    first = p.ingest(IngestRequest(source=src(), content=text, mime_type='text/plain', actor_id='actor-a'))
    second = p.ingest(IngestRequest(source=src(), content=text, mime_type='text/plain', actor_id='actor-a'))
    assert (first.number, second.number) == (1, 1)
    rec = p.register(src())
    assert rec.versions[0].number == 1


def test_hz18_valid_range_bytes_are_read_not_rejected(tmp_path, monkeypatch):
    # KILL (contract boundary): a 25000-byte on-disk file is inside the
    # encoded-byte bound, so hz18 attempts the read (surfacing the injected
    # failure); hz17 rejected it unread. Proves the read contract admits
    # valid-range bytes - an ordering/contract pin, not a timing claim.
    p = pipe(tmp_path)
    p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))
    (tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin').write_bytes(b'x' * 25000)
    from pathlib import Path
    monkeypatch.setattr(Path, 'read_bytes',
                        lambda self, *a, **k: (_ for _ in ()).throw(AssertionError('read attempted')))
    with pytest.raises(AssertionError, match='read attempted'):
        p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))


def test_hz18_beyond_encoded_bound_still_rejected_before_read(tmp_path, monkeypatch):
    # Compat (hz17 and hz18 both reject without reading): past the largest
    # encoded size of any accepted ingest, the file is divergence.
    p = pipe(tmp_path)
    p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))
    (tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin').write_bytes(b'x' * 80001)
    from pathlib import Path
    monkeypatch.setattr(Path, 'read_bytes',
                        lambda self, *a, **k: (_ for _ in ()).throw(AssertionError('read attempted')))
    with pytest.raises(KnowledgeError, match='exceed the ingest bound'):
        p.ingest(IngestRequest(source=src(), content='Alpha fact.', mime_type='text/plain', actor_id='actor-a'))
