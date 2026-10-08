"""hz24 pins: rollback is ownership-aware and close can never mask. Each
claimed object is deleted only while identity still matches at its
captured base, so an unrelated append interleaved during the persist
window is preserved; close errors of any type are swallowed so they never
replace an in-flight failure. KILL pins inject deterministic failures
through monkeypatched helpers / os.close wrappers (no fifo/device,
blocking, or external probes) and fail behaviorally on the pre-hz24
backend. Bounds: append-only interleaving within this process - no
concurrency, transaction, or completed-rollback claim; deletion errors
and failed identity matches stay carried. hz25 narrows two comments here
without changing any assertion: the pre-hz24 baseline deleted BOTH own
and foreign suffix objects (not own-survives), the interleave fixture
proves list preservation only (not durable foreign coherence), and the
close mock models Linux semantics (POSIX leaves the fd state on a close
error unspecified, so portable close ambiguity remains carried)."""
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


def req(content='Alpha fact.'):
    return IngestRequest(source=src(), content=content, mime_type='text/plain', actor_id='actor-a')


def fd_count():
    return len(os.listdir('/proc/self/fd'))


def test_hz24_interleaved_appends_survive_rollback(tmp_path, monkeypatch):
    # KILL: the pre-hz24 (hz23 base-slice) suffix rollback deleted BOTH
    # this attempt's own objects AND any foreign objects an interleaved
    # writer appended DURING the persist window; hz22's pop form deleted
    # the foreign tail and kept our claim. hz24 deletes only this
    # attempt's own objects, verified by identity at their captured bases;
    # the foreign version, chunks, and edge all survive. Scope: this
    # fixture proves LIST preservation only - the foreign v99 has no
    # durable bytes and the restore rewrite records it without a v99
    # directory, so durable coherence of foreign state is NOT asserted
    # (carried).
    p = pipe(tmp_path)
    real_persist = LocalKnowledgePipeline._persist_manifest
    state = {'calls': 0}
    foreign = {}
    def interleave_then_fail(self, rec):
        state['calls'] += 1
        if state['calls'] != 2:
            return real_persist(self, rec)
        # Call 2 is the version-claim persist: interleave a foreign write,
        # then fail. Later calls (the best-effort restore rewrite) persist
        # for real so the surviving foreign state is what we assert.
        foreign['v'] = Version(99, 'f' * 64, [], NOW, 'text/plain')
        rec.versions.append(foreign['v'])
        foreign['c'] = [object(), object()]
        self.chunks.extend(foreign['c'])
        foreign['e'] = {'from': 'other-source', 'to': 'z' * 64, 'relation': 'has_version', 'version': 99}
        self.edges.append(foreign['e'])
        raise OSError('persist failed')
    monkeypatch.setattr(LocalKnowledgePipeline, '_persist_manifest', interleave_then_fail)
    before = fd_count()
    with pytest.raises(KnowledgeError, match='manifest persistence failed'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == [foreign['v']]
    assert p.chunks == foreign['c']
    assert p.edges == [foreign['e']]


def test_hz24_unexpected_close_error_never_masks_failure(tmp_path, monkeypatch):
    # KILL: pre-hz24 the unconditional finally swallowed only OSError from
    # close, so an unexpected close error replaced the original failure the
    # caller should see. hz24 swallows close errors of any type. The mock
    # closes the held tmp dirfd for real, then raises - modeling the Linux
    # behavior, where the descriptor is freed even when close reports an
    # error. POSIX leaves the descriptor state on a close error
    # UNSPECIFIED, so portable close-outcome ambiguity remains carried.
    p = pipe(tmp_path)
    def boom_write(self, ref, raw, segments_blob):
        raise OSError('write failed')
    monkeypatch.setattr(LocalKnowledgePipeline, '_write_version_files', boom_write)
    real_close = os.close
    def close_guard(fd):
        target = False
        try:
            # Only the held VERSION tmp dirfd is poisoned; manifest tmp
            # files (manifest.json.tmp-*) and every other fd close normally.
            target = os.path.basename(os.readlink(f'/proc/self/fd/{fd}')).startswith('v1.tmp-')
        except OSError:
            pass
        real_close(fd)
        if target:
            raise RuntimeError('close exploded')
    monkeypatch.setattr(os, 'close', close_guard)
    before = fd_count()
    with pytest.raises(OSError, match='write failed'):
        p.ingest(req())
    assert fd_count() == before


def test_hz24_plain_rollback_removes_whole_claim(tmp_path, monkeypatch):
    # Compat: with no interleaving, the ownership-aware rollback removes
    # exactly this attempt's claim - same outcome as the prior suffix form.
    # Only the claim persist fails; the restore rewrite (hz27) runs for
    # real, so the pre-claim manifest is confirmed restored and the owned
    # version dir is removed.
    p = pipe(tmp_path)
    real_persist = LocalKnowledgePipeline._persist_manifest
    state = {'calls': 0}
    def fail_second_persist(self, rec):
        state['calls'] += 1
        if state['calls'] == 2:
            raise OSError('persist failed')
        return real_persist(self, rec)
    monkeypatch.setattr(LocalKnowledgePipeline, '_persist_manifest', fail_second_persist)
    before = fd_count()
    with pytest.raises(KnowledgeError, match='manifest persistence failed'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    assert p.chunks == []
    assert p.edges == []
    assert not (tmp_path / 'tenant-a' / 's1' / 'v1').exists()


def test_hz24_oversize_refusal_still_preserves_prior_manifest(tmp_path, monkeypatch):
    # Compat: an oversize refusal happens before any manifest mutation, so
    # the recorded manifest bytes survive exactly and memory drops the
    # refused version claim. The bound is sized to admit the v1 manifest
    # but refuse v1+v2.
    p = pipe(tmp_path)
    v1 = p.ingest(req())
    manifest = tmp_path / 'tenant-a' / 's1' / 'manifest.json'
    prior_bytes = manifest.read_bytes()
    monkeypatch.setattr(LocalKnowledgePipeline, 'MANIFEST_MAX_BYTES', len(prior_bytes) + 10)
    before = fd_count()
    with pytest.raises(ManifestOversizeError):
        p.ingest(req('Beta fact - distinct content forces a v2 claim.'))
    assert fd_count() == before
    assert [v.number for v in p.records['s1'].versions] == [v1.number]
    assert manifest.read_bytes() == prior_bytes
