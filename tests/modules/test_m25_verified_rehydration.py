"""Integrator-executed verified rehydration contracts; deterministic offline adapters."""
import hashlib
import json
import os
import shutil
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m25_knowledge_copilot_training.pipeline import *
from app.modules.m25_knowledge_copilot_training.schemas import *
from app.modules.m25_knowledge_copilot_training.recovery import (
    RecoveryError,
    rehydrate,
)

NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)
AUDIO = b'RIFF\x24\x00\x00\x00WAVEfmt \xff\xfe\x00not-utf8-audio'


class FakeTranscriber:
    def transcribe(self, audio):
        return [Segment(text='hello world',
                        anchors=[Anchor(anchor_id='t-1', kind='timestamp', value='0.0-1.0')],
                        start_seconds=0.0, end_seconds=1.0)]


def src(source_id='s1', **consent_kw):
    kw = dict(granted_by='owner', granted_at=NOW,
              purposes=['knowledge_ingestion'], evidence='consent-1')
    kw.update(consent_kw)
    return SourceRegistration(
        source_id=source_id, kind='website', canonical_url=f'https://example.test/{source_id}',
        author='A', published_at=NOW, title='Title', consent=ConsentRecord(**kw))


def pipe(tmp_path, clock=NOW, **kw):
    return LocalKnowledgePipeline(tmp_path, 'tenant-a', 'actor-a', clock=lambda: clock, **kw)


def ingest(p, source_id='s1', content='Alpha fact.', mime='text/plain', **consent_kw):
    return p.ingest(IngestRequest(source=src(source_id, **consent_kw), content=content,
                                  mime_type=mime, actor_id='actor-a'))


def chunk_identity(p):
    return [(c.tenant_id, c.source_id, c.version, c.chunk_id, c.text, c.anchors, c.vector)
            for c in p.chunks]


def tree_hashes(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            with open(full, 'rb') as fh:
                out[os.path.relpath(full, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def load_manifest(tmp_path, source_id='s1'):
    path = tmp_path / 'tenant-a' / source_id / 'manifest.json'
    return path, json.loads(path.read_text())


def save_manifest(path, disk):
    path.write_text(json.dumps(disk, sort_keys=True))


def test_rehydrate_roundtrip_recovers_state(tmp_path):
    p1 = pipe(tmp_path)
    ingest(p1, 's1', 'Alpha fact.')
    ingest(p1, 's1', 'Beta fact.\n\nGamma fact.')
    ingest(p1, 's2', 'Delta fact.')
    before = tree_hashes(tmp_path)
    p2 = pipe(tmp_path)
    report = rehydrate(p2)
    assert {s.source_id: (s.versions, s.chunks) for s in report.sources} == {'s1': (2, 3), 's2': (1, 1)}
    assert [v.content_hash for v in p2.records['s1'].versions] == \
           [v.content_hash for v in p1.records['s1'].versions]
    assert p2.edges == p1.edges
    assert p2.search('alpha', 5), 'recovered pipeline must serve search'
    # Read-only boundary: the on-disk tree is byte-identical afterwards.
    assert tree_hashes(tmp_path) == before


def test_rehydrate_exact_reindex_identity(tmp_path):
    p1 = pipe(tmp_path)
    ingest(p1, 's1', 'Alpha fact.')
    ingest(p1, 's2', 'Beta fact.\n\nGamma fact.')
    p2 = pipe(tmp_path)
    rehydrate(p2)
    # Every deterministic chunk field is exactly what live ingestion built.
    assert chunk_identity(p2) == chunk_identity(p1)
    assert p2.export() == p1.export()


def test_rehydrate_refuses_tampered_source_bytes(tmp_path):
    ingest(pipe(tmp_path))
    (tmp_path / 'tenant-a' / 's1' / 'v1' / 'source.bin').write_bytes(b'Tampered fact.')
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'source-hash'
    assert excinfo.value.source_id == 's1'


def test_rehydrate_refuses_tampered_segments(tmp_path):
    ingest(pipe(tmp_path))
    seg_path = tmp_path / 'tenant-a' / 's1' / 'v1' / 'segments.json'
    stored = json.loads(seg_path.read_text())
    stored[0]['text'] = 'Rewritten fact.'
    seg_path.write_text(json.dumps(stored, sort_keys=True))
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'segments-provenance'


def test_rehydrate_refuses_non_list_segments(tmp_path):
    ingest(pipe(tmp_path))
    (tmp_path / 'tenant-a' / 's1' / 'v1' / 'segments.json').write_text('[1, 2, 3]')
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'segments-schema'


def test_rehydrate_refuses_manifest_tenant_mismatch(tmp_path):
    ingest(pipe(tmp_path))
    path, disk = load_manifest(tmp_path)
    disk['tenant_id'] = 'tenant-b'
    save_manifest(path, disk)
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'tenant'


def test_rehydrate_refuses_manifest_schema_drift(tmp_path):
    ingest(pipe(tmp_path))
    path, disk = load_manifest(tmp_path)
    disk['versions'][0]['hash'] = disk['versions'][0]['hash'].upper()
    save_manifest(path, disk)
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'manifest-schema'


def test_rehydrate_refuses_manifest_extra_top_level_key(tmp_path):
    ingest(pipe(tmp_path))
    path, disk = load_manifest(tmp_path)
    disk['extra'] = 1
    save_manifest(path, disk)
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'manifest-schema'


def test_rehydrate_refuses_source_id_identity_mismatch(tmp_path):
    ingest(pipe(tmp_path))
    path, disk = load_manifest(tmp_path)
    disk['source']['source_id'] = 's9'
    save_manifest(path, disk)
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'identity-source-id'


def test_rehydrate_refuses_expired_consent(tmp_path):
    ingest(pipe(tmp_path), expires_at=NOW + timedelta(hours=1))
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path, clock=NOW + timedelta(hours=2)))
    assert excinfo.value.check == 'consent'


def test_rehydrate_refuses_missing_version_dir(tmp_path):
    ingest(pipe(tmp_path))
    shutil.rmtree(tmp_path / 'tenant-a' / 's1' / 'v1')
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'version-dir'


def test_rehydrate_refuses_non_empty_pipeline(tmp_path):
    p1 = pipe(tmp_path)
    ingest(p1)
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(p1)
    assert excinfo.value.check == 'pipeline-state'


def test_rehydrate_is_all_or_nothing(tmp_path):
    p1 = pipe(tmp_path)
    ingest(p1, 's1', 'Alpha fact.')
    ingest(p1, 's2', 'Beta fact.')
    (tmp_path / 'tenant-a' / 's2' / 'v1' / 'source.bin').write_bytes(b'Tampered.')
    p2 = pipe(tmp_path)
    with pytest.raises(RecoveryError):
        rehydrate(p2)
    # The good source is NOT loaded: a refusal leaves zero state behind.
    assert p2.records == {}
    assert p2.chunks == []
    assert p2.edges == []


def test_rehydrate_refuses_symlinked_source_dir(tmp_path):
    pipe(tmp_path)  # constructs the tenant workspace the symlink lives in
    real = tmp_path / 'elsewhere' / 's3'
    real.mkdir(parents=True)
    os.symlink(real, tmp_path / 'tenant-a' / 's3')
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'workspace-scan'


def test_rehydrate_refuses_stray_workspace_file(tmp_path):
    ingest(pipe(tmp_path))
    (tmp_path / 'tenant-a' / 'stray.txt').write_text('x')
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'workspace-scan'


def test_rehydrate_reports_orphan_residue_without_loading_it(tmp_path):
    p1 = pipe(tmp_path)
    ingest(p1)
    orphan = tmp_path / 'tenant-a' / 's1' / 'v2'
    orphan.mkdir()
    (orphan / 'source.bin').write_bytes(b'orphaned bytes')
    (orphan / 'segments.json').write_text('[]')
    report = rehydrate(pipe(tmp_path))
    assert report.residue == ['s1/v2']
    assert [s.versions for s in report.sources] == [1]


def test_rehydrate_source_ids_subset(tmp_path):
    p1 = pipe(tmp_path)
    ingest(p1, 's1', 'Alpha fact.')
    ingest(p1, 's2', 'Beta fact.')
    p2 = pipe(tmp_path)
    report = rehydrate(p2, source_ids=['s1'])
    assert [s.source_id for s in report.sources] == ['s1']
    assert 's2' not in p2.records
    assert report.residue == ['s2 (not selected)']
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path), source_ids=['missing'])
    assert excinfo.value.check == 'workspace-scan'


def test_rehydrate_audio_requires_original_transcriber(tmp_path):
    p1 = pipe(tmp_path, transcriber=FakeTranscriber())
    ingest(p1, 's1', AUDIO, 'audio/wav')
    with pytest.raises(RecoveryError) as excinfo:
        rehydrate(pipe(tmp_path))
    assert excinfo.value.check == 'segments-provenance'
    assert 'transcriber' in str(excinfo.value)


def test_rehydrate_audio_recovers_with_same_transcriber(tmp_path):
    p1 = pipe(tmp_path, transcriber=FakeTranscriber())
    ingest(p1, 's1', AUDIO, 'audio/wav')
    p2 = pipe(tmp_path, transcriber=FakeTranscriber())
    report = rehydrate(p2)
    assert [s.versions for s in report.sources] == [1]
    assert p2.records['s1'].versions[0].mime_type == 'audio/wav'
    assert chunk_identity(p2) == chunk_identity(p1)


def test_rehydrate_recovers_registered_source_with_zero_versions(tmp_path):
    p1 = pipe(tmp_path)
    p1.register(src('s0'))
    report = rehydrate(pipe(tmp_path))
    assert [(s.source_id, s.versions, s.chunks) for s in report.sources] == [('s0', 0, 0)]


def test_explicit_restore_method_requires_adapter_attestation(tmp_path):
    ingest(pipe(tmp_path))
    fresh=pipe(tmp_path)
    with pytest.raises(RecoveryError):fresh.restore_verified()
    assert fresh.records=={}
    report=fresh.restore_verified(same_adapters_attested=True)
    assert report.sources[0].source_id=='s1'


def test_duplicate_manifest_keys_refuse(tmp_path):
    ingest(pipe(tmp_path))
    path,disk=load_manifest(tmp_path)
    raw=path.read_text().replace('"tenant_id":', '"tenant_id":"bad","tenant_id":',1)
    path.write_text(raw)
    with pytest.raises(RecoveryError) as exc:rehydrate(pipe(tmp_path))
    assert exc.value.check=='manifest-schema'


def test_invalid_subset_shape_refuses(tmp_path):
    with pytest.raises(RecoveryError):rehydrate(pipe(tmp_path),source_ids='s1')
