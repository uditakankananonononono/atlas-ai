"""hz17 pins: register-time manifest-vs-bytes, guarded byte reads, redaction
error mapping and expansion bound. KILL pins fail on the hz16 backend;
compat/characterization pins pass on both. The timeout contract check uses
a deterministic mock per routing - no costly regex attack run."""
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


def test_hz17_register_rejects_tampered_recorded_bytes(tmp_path):
    # KILL: hz16 register compared manifest to memory only; the tampered
    # source.bin passed. hz17 hashes every manifest-recorded version.
    p = pipe(tmp_path)
    ingest(p)
    (tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin').write_bytes(b'tampered')
    with pytest.raises(KnowledgeError, match='version 1 diverge'):
        p.register(src())


def test_hz17_register_rejects_missing_recorded_bytes(tmp_path):
    # KILL: hz16 register passed with the bytes gone.
    p = pipe(tmp_path)
    ingest(p)
    (tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin').unlink()
    with pytest.raises(KnowledgeError, match='version 1 unreadable'):
        p.register(src())


def test_hz17_register_intact_bytes_unchanged(tmp_path):
    # Compat: intact state registers exactly as before (old and new).
    p = pipe(tmp_path)
    ingest(p)
    rec = p.register(src())
    assert rec.versions[0].number == 1


def test_hz17_segments_json_not_byte_verified(tmp_path):
    # Characterization (passes old and new): tampered segments.json with
    # intact source.bin still registers - establishes source.bin byte
    # verification only, NOT segments.json or whole-store integrity.
    p = pipe(tmp_path)
    ingest(p)
    (tmp_path / 'tenant-a' / 's1' / 'v1' / 'segments.json').write_text('[{"tampered": true}]', encoding='utf-8')
    rec = p.register(src())
    assert rec.versions[0].number == 1


def test_hz17_dedup_rejects_symlinked_source_bin(tmp_path):
    # KILL: hz16 read_bytes followed the symlink and silently served through
    # it (hash of the linked bytes matches); hz17 rejects the symlinked
    # component before reading.
    p = pipe(tmp_path)
    ingest(p)
    blob = tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin'
    clone = tmp_path / 'tenant-a' / 'clone.bin'
    clone.write_bytes(blob.read_bytes())
    blob.unlink()
    os.symlink(clone, blob)
    with pytest.raises(KnowledgeError, match='symlinked path component'):
        ingest(p)


def test_hz17_oversize_bytes_rejected_before_any_read(tmp_path, monkeypatch):
    # KILL (ordering): hz16 read the whole oversized file before rejecting;
    # hz17 stat-guards first. Making read_bytes unusable kills hz16 and
    # proves guard-before-read ordering - this is an ordering pin, not a
    # timing claim.
    p = pipe(tmp_path)
    ingest(p)
    (tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin').write_bytes(b'x' * 80001)
    from pathlib import Path
    monkeypatch.setattr(Path, 'read_bytes',
                        lambda self, *a, **k: (_ for _ in ()).throw(AssertionError('read attempted')))
    with pytest.raises(KnowledgeError, match='exceed the ingest bound'):
        ingest(p)


def test_hz17_invalid_replacement_reference_maps_to_domain_error(tmp_path):
    # KILL: hz16 let regex.error escape unmapped (routes would 500); hz17
    # raises ValueError and stores nothing.
    from app.modules.m25_knowledge_copilot.service import Service, Repository
    from app.modules.m25_knowledge_copilot.schemas import (
        CaptureStart, IngestEvent, Redaction, SourceKind)
    svc = Service(Repository())
    started = svc.start_capture('t', 'a', CaptureStart(
        device_id='d1', selected_screen_ids=['scr'],
        redactions=[Redaction(pattern='(a)', replacement='\\9')]))
    with pytest.raises(ValueError, match='invalid redaction replacement'):
        svc.ingest('t', 'a', started.id, IngestEvent(
            source=SourceKind.SCREEN_OCR, content='a', source_ref='screen:ocr', screen_id='scr'))
    assert svc.repo.sessions[started.id].timeline == []


def test_hz17_redaction_expansion_cap_rejects_event(tmp_path):
    # KILL: hz16 stored the 60000-char expanded item; hz17 rejects the event
    # once expansion passes the output bound.
    from app.modules.m25_knowledge_copilot.service import Service, Repository
    from app.modules.m25_knowledge_copilot.schemas import (
        CaptureStart, IngestEvent, Redaction, SourceKind)
    svc = Service(Repository())
    started = svc.start_capture('t', 'a', CaptureStart(
        device_id='d1', selected_screen_ids=['scr'],
        redactions=[Redaction(pattern='a', replacement='aaaa')]))
    with pytest.raises(ValueError, match='expansion exceeds'):
        svc.ingest('t', 'a', started.id, IngestEvent(
            source=SourceKind.SCREEN_OCR, content='a' * 15000, source_ref='screen:ocr', screen_id='scr'))
    assert svc.repo.sessions[started.id].timeline == []


def test_hz17_replacement_length_bounded_at_schema():
    # KILL: hz16 accepted unbounded replacements.
    from pydantic import ValidationError
    from app.modules.m25_knowledge_copilot.schemas import Redaction
    with pytest.raises(ValidationError):
        Redaction(pattern='a', replacement='x' * 201)


def test_hz17_timeout_contract_via_deterministic_mock(tmp_path, monkeypatch):
    # Contract check via deterministic mock (no costly attack run): a
    # timeout rejects the event and stores nothing. Passes on hz16 and hz17.
    import app.modules.m25_knowledge_copilot.service as svc_mod
    from app.modules.m25_knowledge_copilot.service import Service, Repository
    from app.modules.m25_knowledge_copilot.schemas import (
        CaptureStart, IngestEvent, Redaction, SourceKind)
    def _boom(*a, **k):
        raise TimeoutError('mock budget exceeded')
    monkeypatch.setattr(svc_mod._regex, 'sub', _boom)
    svc = Service(Repository())
    started = svc.start_capture('t', 'a', CaptureStart(
        device_id='d1', selected_screen_ids=['scr'],
        redactions=[Redaction(pattern='secret')]))
    with pytest.raises(ValueError, match='time budget'):
        svc.ingest('t', 'a', started.id, IngestEvent(
            source=SourceKind.SCREEN_OCR, content='a secret here', source_ref='screen:ocr', screen_id='scr'))
    assert svc.repo.sessions[started.id].timeline == []
