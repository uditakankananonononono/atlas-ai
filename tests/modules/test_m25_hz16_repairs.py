"""hz16 pins: dedup disk validation, symlink-component containment, bounded
redaction execution. KILL pins fail on the pre-hz16 backend; compat pins
pass on both. All state lives under pytest tmp_path; no network, no host
probes."""
import os
from datetime import datetime, timezone

import pytest

from app.modules.m25_knowledge_copilot_training.pipeline import *
from app.modules.m25_knowledge_copilot_training.schemas import *

NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)


def src(source_id='s1', kind='website', **kw):
    return SourceRegistration(
        source_id=source_id, kind=kind,
        canonical_url=None if kind in {'book', 'file', 'meeting_audio'} else f'https://example.test/{source_id}',
        author='A', published_at=NOW, title='Title',
        consent=ConsentRecord(granted_by='owner', granted_at=NOW,
                              purposes=['knowledge_ingestion'], evidence='consent-1'), **kw)


def pipe(tmp_path, **kw):
    return LocalKnowledgePipeline(tmp_path, 'tenant-a', 'actor-a', clock=lambda: NOW, **kw)


def ingest(p, s=None, text='Alpha fact.\n\nBeta fact.'):
    s = s or src()
    return p.ingest(IngestRequest(source=s, content=text, mime_type='text/plain', actor_id='actor-a'))


def test_hz16_dedup_rejects_corrupted_on_disk_bytes(tmp_path):
    # KILL: old code returns the recorded version without looking at disk.
    p = pipe(tmp_path)
    ingest(p)
    blob = tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin'
    blob.write_bytes(b'tampered bytes that do not hash to the recorded digest')
    with pytest.raises(KnowledgeError, match='dedup validation failed'):
        ingest(p)


def test_hz16_dedup_rejects_missing_on_disk_bytes(tmp_path):
    # KILL: old code serves the version even when its bytes are gone.
    p = pipe(tmp_path)
    ingest(p)
    (tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin').unlink()
    with pytest.raises(KnowledgeError, match='dedup validation failed'):
        ingest(p)


def test_hz16_dedup_honest_path_unchanged(tmp_path):
    # Compat: intact bytes dedup exactly as before (passes old and new).
    p = pipe(tmp_path)
    a = ingest(p)
    b = ingest(p)
    assert (a.number, b.number) == (1, 1)


def test_hz16_dangling_symlink_component_rejected_before_any_write(tmp_path):
    # KILL: old code resolves through the symlink and writes a manifest into
    # the symlink target's lexical location, creating workspace/ghost.
    p = pipe(tmp_path)
    os.symlink(tmp_path / 'tenant-a' / 'ghost', tmp_path / 'tenant-a' / 'evil')
    with pytest.raises(KnowledgeError, match='symlinked path component'):
        p.register(src('evil', 'file'))
    assert not (tmp_path / 'tenant-a' / 'ghost').exists()


def test_hz16_sibling_symlink_does_not_redirect_writes(tmp_path):
    # KILL: old code resolves evil->real and writes evil's manifest INTO the
    # sibling record's directory.
    p = pipe(tmp_path)
    (tmp_path / 'tenant-a' / 'real').mkdir(parents=True)
    os.symlink(tmp_path / 'tenant-a' / 'real', tmp_path / 'tenant-a' / 'evil')
    with pytest.raises(KnowledgeError, match='symlinked path component'):
        p.register(src('evil', 'file'))
    assert not (tmp_path / 'tenant-a' / 'real' / 'manifest.json').exists()


def test_hz16_delete_through_symlinked_component_refused(tmp_path):
    # KILL: old code resolves evil->real and rmtree's the sibling's real
    # data; hz16 refuses before any mutation and real's bytes survive.
    p = pipe(tmp_path)
    p.register(src('real', 'file'))
    p.register(src('evil', 'file'))
    import shutil
    shutil.rmtree(tmp_path / 'tenant-a' / 'evil')
    os.symlink(tmp_path / 'tenant-a' / 'real', tmp_path / 'tenant-a' / 'evil')
    with pytest.raises(KnowledgeError, match='symlinked path component'):
        p.delete_verified('evil')
    assert (tmp_path / 'tenant-a' / 'real' / 'manifest.json').exists()
    assert 'evil' in p.records  # tracking retained on refusal


def test_hz16_redaction_time_budget_rejects_event_unstored(tmp_path):
    # KILL (bounded): old `re` completes this backtracking bomb in ~2.8s
    # without any error; hz16 raises at the 1.0s budget and stores nothing.
    from app.modules.m25_knowledge_copilot.service import Service, Repository
    from app.modules.m25_knowledge_copilot.schemas import (
        CaptureStart, IngestEvent, Redaction, SourceKind)
    svc = Service(Repository())
    started = svc.start_capture('t', 'a', CaptureStart(
        device_id='d1', selected_screen_ids=['scr'],
        redactions=[Redaction(pattern=r'(a|a)*$')]))
    with pytest.raises(ValueError, match='time budget'):
        svc.ingest('t', 'a', started.id, IngestEvent(
            source=SourceKind.SCREEN_OCR, content='a' * 24 + 'b',
            source_ref='screen:ocr', screen_id='scr'))
    assert svc.repo.sessions[started.id].timeline == []  # nothing stored unredacted


def test_hz16_benign_redaction_still_applies(tmp_path):
    # Compat: a linear pattern redacts exactly as before (passes old and
    # new), establishing the engine swap preserves accepted-pattern behavior.
    from app.modules.m25_knowledge_copilot.service import Service, Repository
    from app.modules.m25_knowledge_copilot.schemas import (
        CaptureStart, IngestEvent, Redaction, SourceKind)
    svc = Service(Repository())
    started = svc.start_capture('t', 'a', CaptureStart(
        device_id='d1', selected_screen_ids=['scr'],
        redactions=[Redaction(pattern=r'\b\d{3}-\d{2}-\d{4}\b')]))
    item = svc.ingest('t', 'a', started.id, IngestEvent(
        source=SourceKind.SCREEN_OCR, content='call 123-45-6789 now',
        source_ref='screen:ocr', screen_id='scr'))
    assert '123-45-6789' not in item.content and '[REDACTED]' in item.content
