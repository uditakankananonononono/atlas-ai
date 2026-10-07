"""hz27 pins: truthful on-disk outcomes for the failure paths hz26 added.
(1) The durability fsyncs happen in the required ORDER, not just the
required presence. (2) A post-rename / pre-claim failure removes the
RENAMED target (the only object the attempt still owns), not the
long-gone tmp name. (3) A post-replace persist failure whose restore
rewrite is unconfirmed PRESERVES the version's bytes - deleting bytes a
live manifest may still reference would strand a recorded hash with no
content. Deletion requires a confirmed restore. KILL pins wrap
os.fsync/os.rename/os.replace deterministically (record or fail by fd
path and armed sequence flags; no fifo/device/blocking/external probes).
Complete rollback remains unproved and is not claimed; no orphan sweep."""
import os
import json
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


def test_hz27_durable_events_happen_in_order(tmp_path, monkeypatch):
    # ORDER LOCK: the hz26 presence pin sampled which fsyncs happen; this
    # pin locks their sequence: file data fsyncs -> tmp dirfd fsync ->
    # rename -> parent dir fsync -> claim manifest fsync -> replace ->
    # post-replace dir fsync. Passes on hz26 code (the order was already
    # correct); fails on pre-hz26 code where the events do not exist.
    events = []
    real_fsync, real_rename, real_replace = os.fsync, os.rename, os.replace
    def rec_fsync(fd):
        try:
            events.append(('fsync', os.readlink(f'/proc/self/fd/{fd}')))
        except OSError:
            events.append(('fsync', '<unknown>'))
        return real_fsync(fd)
    def rec_rename(a, b):
        events.append(('rename', str(a), str(b)))
        return real_rename(a, b)
    def rec_replace(a, b):
        events.append(('replace', str(a), str(b)))
        return real_replace(a, b)
    monkeypatch.setattr(os, 'fsync', rec_fsync)
    monkeypatch.setattr(os, 'rename', rec_rename)
    monkeypatch.setattr(os, 'replace', rec_replace)
    p = pipe(tmp_path)
    before = fd_count()
    p.ingest(req())
    assert fd_count() == before
    src_dir = str(tmp_path / 'tenant-a' / 's1')
    def idx(pred, start=0):
        return next(i for i, e in enumerate(events) if i >= start and pred(e))
    i_data = idx(lambda e: e[0] == 'fsync' and e[1].endswith('source.bin'))
    i_seg = idx(lambda e: e[0] == 'fsync' and e[1].endswith('segments.json'))
    i_dirfd = idx(lambda e: e[0] == 'fsync' and e[1].rsplit('/', 1)[-1].startswith('v1.tmp-'))
    i_ren = idx(lambda e: e[0] == 'rename' and e[2].endswith('/v1'))
    i_par = idx(lambda e: e[0] == 'fsync' and e[1] == src_dir, i_ren)
    i_mfs = idx(lambda e: e[0] == 'fsync' and e[1].rsplit('/', 1)[-1].startswith('manifest.json.tmp-'), i_par)
    i_rep = idx(lambda e: e[0] == 'replace' and e[2].endswith('manifest.json'), i_mfs)
    i_dir2 = idx(lambda e: e[0] == 'fsync' and e[1] == src_dir, i_rep)
    assert i_data < i_dirfd < i_ren < i_par < i_mfs < i_rep < i_dir2
    assert i_seg < i_dirfd


def test_hz27_post_rename_failure_cleans_renamed_target(tmp_path, monkeypatch):
    # KILL: on hz26 a parent-dir fsync failure AFTER the rename ran the
    # pre-rename cleanup against tmp - a name that no longer exists - so a
    # COMPLETE version dir with no manifest record was left behind. hz27
    # tracks the rename and removes the owned renamed target; no live
    # manifest references these bytes pre-claim, so removal is truthful.
    state = {'renamed': False, 'failed': False}
    real_rename, real_fsync = os.rename, os.fsync
    def rename_watch(a, b):
        state['renamed'] = True
        return real_rename(a, b)
    src_dir = str(tmp_path / 'tenant-a' / 's1')
    def fail_parent_fsync(fd):
        try:
            name = os.readlink(f'/proc/self/fd/{fd}')
        except OSError:
            name = ''
        if state['renamed'] and not state['failed'] and name == src_dir:
            state['failed'] = True
            raise OSError('parent dir fsync failed')
        return real_fsync(fd)
    monkeypatch.setattr(os, 'rename', rename_watch)
    monkeypatch.setattr(os, 'fsync', fail_parent_fsync)
    p = pipe(tmp_path)
    before = fd_count()
    with pytest.raises(OSError, match='parent dir fsync failed'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    s1 = tmp_path / 'tenant-a' / 's1'
    assert not (s1 / 'v1').exists()
    assert not any(x.name.startswith('v1.tmp-') for x in s1.iterdir())


def test_hz27_unconfirmed_restore_preserves_referenced_bytes(tmp_path, monkeypatch):
    # KILL: the claim persist fails AFTER os.replace (post-replace dir
    # fsync) and the restore rewrite then fails too (manifest file fsync).
    # On hz26 the rollback deleted the version dir anyway, leaving the
    # LIVE manifest recording a version whose bytes were gone. hz27
    # removes bytes only after a confirmed restore: v1 is preserved, the
    # live manifest still records it, and the error says the restore was
    # not confirmed.
    state = {'renamed': False, 'claim_replaced': False}
    real_rename, real_replace, real_fsync = os.rename, os.replace, os.fsync
    def rename_watch(a, b):
        state['renamed'] = True
        return real_rename(a, b)
    def replace_watch(a, b):
        if state['renamed'] and str(b).endswith('manifest.json'):
            state['claim_replaced'] = True
        return real_replace(a, b)
    src_dir = str(tmp_path / 'tenant-a' / 's1')
    def fail_late_fsync(fd):
        try:
            name = os.readlink(f'/proc/self/fd/{fd}')
        except OSError:
            name = ''
        if state['claim_replaced'] and (name == src_dir or name.rsplit('/', 1)[-1].startswith('manifest.json.tmp-')):
            raise OSError('late fsync failed')
        return real_fsync(fd)
    monkeypatch.setattr(os, 'rename', rename_watch)
    monkeypatch.setattr(os, 'replace', replace_watch)
    monkeypatch.setattr(os, 'fsync', fail_late_fsync)
    p = pipe(tmp_path)
    before = fd_count()
    with pytest.raises(KnowledgeError, match='could not be confirmed restored'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    kept = tmp_path / 'tenant-a' / 's1' / 'v1'
    assert (kept / 'source.bin').read_bytes() == b'Alpha fact.'
    manifest = json.loads((tmp_path / 'tenant-a' / 's1' / 'manifest.json').read_text())
    assert [v['number'] for v in manifest['versions']] == [1]


def test_hz27_confirmed_restore_still_removes_owned_target(tmp_path, monkeypatch):
    # Compat: a PRE-replace claim persist failure (manifest file fsync)
    # leaves the registration manifest live; the restore rewrite succeeds,
    # so the owned version dir is removed and the original contract holds.
    # Passes on hz26 and hz27.
    state = {'renamed': False, 'failed': False}
    real_rename, real_fsync = os.rename, os.fsync
    def rename_watch(a, b):
        state['renamed'] = True
        return real_rename(a, b)
    def fail_claim_file_fsync(fd):
        try:
            name = os.readlink(f'/proc/self/fd/{fd}')
        except OSError:
            name = ''
        if state['renamed'] and not state['failed'] and name.rsplit('/', 1)[-1].startswith('manifest.json.tmp-'):
            state['failed'] = True
            raise OSError('manifest file fsync failed')
        return real_fsync(fd)
    monkeypatch.setattr(os, 'rename', rename_watch)
    monkeypatch.setattr(os, 'fsync', fail_claim_file_fsync)
    p = pipe(tmp_path)
    before = fd_count()
    with pytest.raises(KnowledgeError, match='manifest persistence failed'):
        p.ingest(req())
    assert fd_count() == before
    assert p.records['s1'].versions == []
    assert not (tmp_path / 'tenant-a' / 's1' / 'v1').exists()
    manifest = json.loads((tmp_path / 'tenant-a' / 's1' / 'manifest.json').read_text())
    assert manifest['versions'] == []
