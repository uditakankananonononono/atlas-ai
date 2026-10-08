"""Reimplementation: bounded on-disk readback before deleting version bytes.
Fault injections use real files, not crash or concurrent-writer proof."""
import json
import pytest
from test_m25_hz27_restore_confirmed import pipe, req
from app.modules.m25_knowledge_copilot_training.pipeline import KnowledgeError

@pytest.mark.parametrize('initial', [OSError, ValueError])
@pytest.mark.parametrize('restore', ['stale', 'corrupt', 'unreadable', 'persist_failure'])
def test_unconfirmed_restore_keeps_bytes_and_reports_unknown(tmp_path, monkeypatch, initial, restore):
    p = pipe(tmp_path)
    p.register(req().source)
    original = p._persist_manifest
    calls = []
    def persist(rec):
        if not calls and not rec.versions: return original(rec)
        calls.append(True)
        if len(calls) == 1:
            original(rec)
            raise initial('post-replace fault')
        if restore == 'persist_failure': raise OSError('restore fault')
        if restore == 'corrupt': (tmp_path/'tenant-a'/'s1'/'manifest.json').write_text('{invalid')
        if restore == 'unreadable': (tmp_path/'tenant-a'/'s1'/'manifest.json').unlink()
        # stale: normal return but original claimed-version bytes remain.
    monkeypatch.setattr(p, '_persist_manifest', persist)
    with pytest.raises(KnowledgeError, match='could not be confirmed restored'):
        p.ingest(req())
    assert p.records['s1'].versions == []
    assert (tmp_path/'tenant-a'/'s1'/'v1'/'source.bin').read_bytes() == b'Alpha fact.'
    assert len(calls) == 2

@pytest.mark.parametrize('initial', [OSError, ValueError])
def test_confirmed_restore_uses_bounded_reader_then_removes_bytes(tmp_path, monkeypatch, initial):
    p = pipe(tmp_path); p.register(req().source)
    original = p._persist_manifest
    read = p._read_bounded_file
    calls = []; reads = []
    def persist(rec):
        if not calls and not rec.versions: return original(rec)
        calls.append(True); original(rec)
        if len(calls) == 1: raise initial('post-replace fault')
    def bounded(path, limit, *args):
        reads.append((path.name, limit)); return read(path, limit, *args)
    monkeypatch.setattr(p, '_persist_manifest', persist)
    monkeypatch.setattr(p, '_read_bounded_file', bounded)
    expected = KnowledgeError if initial is OSError else ValueError
    with pytest.raises(expected): p.ingest(req())
    assert ('manifest.json', p.MANIFEST_MAX_BYTES) in reads
    assert not (tmp_path/'tenant-a'/'s1'/'v1').exists()
    assert json.loads((tmp_path/'tenant-a'/'s1'/'manifest.json').read_text())['versions'] == []
