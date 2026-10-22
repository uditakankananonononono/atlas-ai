"""Workspace-fd pinning (M25): after construction, renaming or swapping the
workspace pathname - or any ancestor - must not redirect manifest writes,
ingest writes, or verified removals out of the construction-verified tree.
RED on un-pinned source (by-path opens follow the swap); GREEN once the
workspace descriptor is pinned at construction."""
import os
from datetime import datetime, timezone

import pytest

from app.modules.m25_knowledge_copilot_training.pipeline import *
from app.modules.m25_knowledge_copilot_training.schemas import *

NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)


def src(source_id):
    return SourceRegistration(source_id=source_id, kind='website',
        canonical_url=f'https://example.test/{source_id}', author='A',
        published_at=NOW, title='T',
        consent=ConsentRecord(granted_by='owner', granted_at=NOW,
                              purposes=['knowledge_ingestion'], evidence='c1'))


def make(root):
    p = LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)
    p.ingest(IngestRequest(source=src('s1'), content='Alpha fact.',
                           mime_type='text/plain', actor_id='actor-a'))
    return p


def test_workspace_name_symlink_swap_cannot_redirect_manifest_write(tmp_path):
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    outside = tmp_path / 'outside'; outside.mkdir()
    os.rename(root / 'tenant-a', root / 'tenant-a-real')
    os.symlink(outside, root / 'tenant-a')
    p._persist_manifest(p.records['s1'])
    assert (root / 'tenant-a-real' / 's1' / 'manifest.json').exists()
    assert not (outside / 's1' / 'manifest.json').exists()
    p.close()


def test_ancestor_dir_symlink_swap_cannot_redirect_manifest_write(tmp_path):
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    evilroot = tmp_path / 'evilroot'
    (evilroot / 'tenant-a').mkdir(parents=True)
    os.rename(root, tmp_path / 'root-real')
    os.symlink(evilroot, root)
    p._persist_manifest(p.records['s1'])
    assert (tmp_path / 'root-real' / 'tenant-a' / 's1' / 'manifest.json').exists()
    assert not (evilroot / 'tenant-a' / 's1' / 'manifest.json').exists()
    p.close()


def test_workspace_name_dir_swap_cannot_redirect_verified_removal(tmp_path):
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    os.rename(root / 'tenant-a', root / 'tenant-a-real')
    swapped = tmp_path / 'swapped'; swapped.mkdir()
    os.rename(swapped, root / 'tenant-a')
    out = p.delete_verified('s1')
    assert out['deleted'] is True
    assert not (root / 'tenant-a-real' / 's1').exists()  # removed from the REAL tree
    assert not (root / 'tenant-a-real' / 's1' / 'manifest.json').exists()
    p.close()


def test_ancestor_swap_cannot_redirect_ingest_write(tmp_path):
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    evilroot = tmp_path / 'evilroot'
    (evilroot / 'tenant-a').mkdir(parents=True)
    os.rename(root, tmp_path / 'root-real')
    os.symlink(evilroot, root)
    # Closure property: the swap must NEVER receive bytes. The write either
    # lands in the construction-pinned tree or the operation refuses
    # fail-closed (read-side divergence guard) - split-brain is not allowed.
    try:
        p.ingest(IngestRequest(source=src('s2'), content='Beta fact.',
                               mime_type='text/plain', actor_id='actor-a'))
        assert (tmp_path / 'root-real' / 'tenant-a' / 's2' / 'manifest.json').exists()
    except KnowledgeError:
        pass
    assert not (evilroot / 'tenant-a' / 's2').exists()
    p.close()


def test_close_releases_descriptor_and_context_manager(tmp_path):
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    fd = p._wsfd
    p.close(); p.close()  # idempotent
    with pytest.raises(OSError):
        os.fstat(fd)
    with LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW) as p2:
        assert p2._wsfd is not None
    p3 = LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)
    p3.close()
    p3.close()


def test_helper_refuses_absolute_separator_empty_and_dot_names(tmp_path):
    # RED pin (coordinator #1): delete_verified takes a raw string and the
    # schema pattern admits dot-only names, so the helper itself is the one
    # place that must refuse absolute, separator-bearing, empty and
    # dot-segment components for every caller.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    try:
        for bad in ('a/b', '/etc/passwd', '', '.', '..'):
            with pytest.raises(KnowledgeError):
                p._contained_anchored(bad)
    finally:
        p.close()


def test_delete_with_unvalidated_name_refuses_before_lookup(tmp_path):
    # RED pin (coordinator #1, public raw-string entry point): refusal must
    # be KnowledgeError, surfacing BEFORE the records lookup (KeyError).
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    try:
        with pytest.raises(KnowledgeError):
            p.delete_verified('a/b')
    finally:
        p.close()


def test_operations_after_close_refuse_controlled(tmp_path):
    # RED pin (coordinator #3): after close(), operations must refuse with a
    # controlled KnowledgeError - never a TypeError from dup(None) and never
    # a silent CWD-relative dir_fd=None operation.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    p.close()
    with pytest.raises(KnowledgeError):
        p.ingest(IngestRequest(source=src('s2'), content='Beta fact.',
                               mime_type='text/plain', actor_id='actor-a'))
    with pytest.raises(KnowledgeError):
        p.delete_verified('s1')
    with pytest.raises(KnowledgeError):
        p._persist_manifest(p.records['s1'])


def test_documented_ownership_no_finalizer(tmp_path):
    # Coordinator #2: ownership is documented, NOT a __del__ finalizer - a
    # gc-timed close shifts the process fd count mid-test and breaks the
    # pinned fd-accounting contract in test_m25_hz24_ownership_rollback.
    # Pin: the class has no __del__, close() actually releases, and the
    # context manager releases on exit.
    assert '__del__' not in LocalKnowledgePipeline.__dict__
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    fd = p._wsfd
    p.close()
    with pytest.raises(OSError):
        os.fstat(fd)


def test_mutant1_construction_refuses_workspace_swapped_to_symlink(tmp_path):
    # Kills mutant "drop O_NOFOLLOW from the construction open". Seam: swap
    # the RESOLVED workspace path to a symlink between the constructor's
    # mkdir and its os.open. O_NOFOLLOW must make the constructor refuse;
    # without it the pinned descriptor silently denotes a FOREIGN tree and
    # every anchored write/delete lands outside the verified workspace.
    import unittest.mock as mock
    import pathlib
    root = tmp_path / 'root'; root.mkdir()
    outside = tmp_path / 'outside'; outside.mkdir()
    real_mkdir = pathlib.Path.mkdir
    state = {'armed': True}
    def swapping_mkdir(self, *a, **kw):
        real_mkdir(self, *a, **kw)
        if state['armed'] and self.name == 'tenant-a':
            state['armed'] = False
            os.rename(self, self.parent / 'tenant-a-real')
            os.symlink(outside, self)
    with mock.patch.object(pathlib.Path, 'mkdir', swapping_mkdir):
        with pytest.raises(OSError):
            LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)
    assert not (outside / 's1').exists()


def test_mutant2_symlinked_component_refusal_stays_knowledgeerror(tmp_path):
    # Kills mutant "skip the intermediate lstat walk". Base contract: a
    # symlinked path component is refused with KnowledgeError. Without the
    # walk the refusal still happens but as a raw OSError from the
    # downstream O_NOFOLLOW open - a different, uncontrolled contract.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    try:
        os.rename(root / 'tenant-a' / 's1', root / 'tenant-a' / 's1-real')
        os.symlink(root / 'tenant-a' / 's1-real', root / 'tenant-a' / 's1')
        with pytest.raises(KnowledgeError):
            p._persist_manifest(p.records['s1'])
    finally:
        p.close()


def test_mutant4_rmtree_if_owned_never_empties_a_mismatched_held_dir(tmp_path):
    # Kills mutant "skip the fstat-vs-lstat identity check". Held descriptor
    # and path denote DIFFERENT objects (dir swapped between acquisition and
    # cleanup): the held tree's contents must survive exactly.
    a = tmp_path / 'a'; a.mkdir(); (a / 'marker.txt').write_text('real tree')
    b = tmp_path / 'b'; b.mkdir(); (b / 'decoy.txt').write_text('swap-in')
    dfd = os.open(a, os.O_RDONLY | os.O_DIRECTORY)
    try:
        LocalKnowledgePipeline._rmtree_if_owned(b, dfd)
    finally:
        os.close(dfd)
    assert (a / 'marker.txt').read_text() == 'real tree'
    assert (b / 'decoy.txt').read_text() == 'swap-in'


def test_workspace_name_real_dir_swap_cannot_redirect_ingest_write(tmp_path):
    # Pins ingest's write anchor (root_fd dup of the construction-held
    # workspace descriptor): a REAL directory swapped in at the workspace
    # NAME (no symlink anywhere, so the read-side guard is not what protects
    # this) must receive no bytes. A by-path reopen follows the name and
    # lands the version bytes in the replacement tree.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    os.rename(root / 'tenant-a', root / 'tenant-a-real')
    replacement = root / 'tenant-a'
    replacement.mkdir()
    p.ingest(IngestRequest(source=src('s2'), content='Beta fact.',
                           mime_type='text/plain', actor_id='actor-a'))
    real = root / 'tenant-a-real'
    assert (real / 's2' / 'v1' / 'source.bin').read_bytes() == b'Beta fact.'
    assert (real / 's2' / 'v1' / 'segments.json').exists()
    assert (real / 's2' / 'manifest.json').exists()
    assert list(replacement.iterdir()) == []
    p.close()


def test_by_path_remove_child_tree_wrapper_closes_its_parent_fd(tmp_path):
    # The by-path remove_child_tree wrapper owns the parent descriptor it
    # opens: dropping its close leaks one fd per call. The pipeline-level fd
    # accounting pin does not cover the wrapper itself.
    from app.modules.m25_knowledge_copilot_training.fs_safe import remove_child_tree
    parent = tmp_path / 'parent'; parent.mkdir()
    assert remove_child_tree(parent, 'absent-name') is True  # warm up
    before = len(os.listdir('/proc/self/fd'))
    for _ in range(200):
        assert remove_child_tree(parent, 'absent-name') is True
    assert len(os.listdir('/proc/self/fd')) == before


# --- v5 pins (peer audit survivors, 2026-10-22) -------------------------


def test_walk_drop_source_dir_symlink_race_refuses_knowledgeerror(tmp_path):
    # Kills mutant "drop the intermediate anchored-walk loop in
    # _contained_anchored" (pl_walk_drop). Race injection: the source dir is
    # swapped to a symlink AFTER register() completes inside ingest (the
    # by-path _contained check in register still sees the real dir) and
    # BEFORE the anchored helper walks the components. The intermediate
    # lstat under the held descriptor chain must refuse with KnowledgeError
    # carrying the full base message; without the walk the swap surfaces
    # only as a raw OSError from the downstream O_NOFOLLOW open - a
    # different, uncontrolled contract.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    real_register = p.register
    def racing_register(source):
        rec = real_register(source)
        s1 = root / 'tenant-a' / 's1'
        os.rename(s1, root / 'tenant-a' / 's1-real')
        os.symlink(root / 'tenant-a' / 's1-real', s1)
        return rec
    p.register = racing_register
    try:
        with pytest.raises(KnowledgeError) as ei:
            p.ingest(IngestRequest(source=src('s1'), content='Beta fact.',
                                   mime_type='text/plain', actor_id='actor-a'))
        assert str(ei.value) == 'symlinked path component inside workspace; refusing'
    finally:
        p.close()


def test_delete_verified_regular_file_at_name_keeps_truthful_tracking(tmp_path):
    # Kills mutant "verified or True" in delete_verified
    # (pl_delete_verify_drop). A regular file at the source name cannot be
    # removed by the anchored tree removal, so the result must report
    # deleted=False and tracking_retained=True, the record must stay in
    # memory, and the file must be left in place - never a false deletion
    # claim with the tracking silently gone.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    try:
        os.rename(root / 'tenant-a' / 's1', root / 'tenant-a' / 's1-real')
        (root / 'tenant-a' / 's1').write_text('not a directory')
        out = p.delete_verified('s1')
        assert out['deleted'] is False
        assert out['tracking_retained'] is True
        assert 's1' in p.records
        assert (root / 'tenant-a' / 's1').is_file()
    finally:
        p.close()


def test_remove_child_tree_at_fd_refuses_special_and_separator_names(tmp_path):
    # Kills mutant "drop the name validation in remove_child_tree_at_fd"
    # (fs_atfd_name_drop). Direct fs_safe-level pin: '.' would empty the
    # HELD directory itself, '..' would walk into the parent, an empty name
    # or a separator would break the single-component contract. Every
    # refusal returns False and the held tree stays byte-identical.
    from app.modules.m25_knowledge_copilot_training.fs_safe import remove_child_tree_at_fd
    held = tmp_path / 'held'; held.mkdir()
    (held / 'keep.txt').write_text('keep')
    (held / 'sub').mkdir(); (held / 'sub' / 'nested.txt').write_text('n')
    fd = os.open(held, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for bad in ('.', '..', '', 'a/b'):
            assert remove_child_tree_at_fd(fd, bad) is False
            assert (held / 'keep.txt').read_text() == 'keep'
            assert (held / 'sub' / 'nested.txt').read_text() == 'n'
    finally:
        os.close(fd)
    assert sorted(os.listdir(held)) == ['keep.txt', 'sub']


def test_closed_refusal_message_full_text(tmp_path):
    # Pins the exact refusal text after close() - v4 pinned only the
    # exception type (peer survivor #4).
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    p.close()
    with pytest.raises(KnowledgeError) as ei:
        p.delete_verified('s1')
    assert str(ei.value) == 'pipeline is closed'


def test_component_name_refusal_message_full_text(tmp_path):
    # Pins the exact refusal text for unsafe source-id components - v4
    # pinned only the exception type (peer survivor #5).
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    try:
        with pytest.raises(KnowledgeError) as ei:
            p.delete_verified('a/b')
        assert str(ei.value) == 'source id components must be single non-dot names without separators'
    finally:
        p.close()


def test_symlink_refusal_message_full_text_final_component_site(tmp_path):
    # Pins the exact refusal text at the FINAL-component lstat site of
    # _contained_anchored (single-part callers: _persist_manifest,
    # delete_verified). Complements the walk-site pin above so the message
    # literal is pinned at every pipeline site (peer survivor #6).
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    try:
        os.rename(root / 'tenant-a' / 's1', root / 'tenant-a' / 's1-real')
        os.symlink(root / 'tenant-a' / 's1-real', root / 'tenant-a' / 's1')
        with pytest.raises(KnowledgeError) as ei:
            p._persist_manifest(p.records['s1'])
        assert str(ei.value) == 'symlinked path component inside workspace; refusing'
    finally:
        p.close()


def test_symlink_refusal_message_full_text_by_path_site(tmp_path):
    # Pins the exact refusal text at the by-path _contained walk used by
    # register and the read paths (peer survivor #6, third literal site).
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    try:
        os.rename(root / 'tenant-a' / 's1', root / 'tenant-a' / 's1-real')
        os.symlink(root / 'tenant-a' / 's1-real', root / 'tenant-a' / 's1')
        with pytest.raises(KnowledgeError) as ei:
            p._contained('s1', 'manifest.json')
        assert str(ei.value) == 'symlinked path component inside workspace; refusing'
    finally:
        p.close()


# --- v6 pins (peer v5b-audit survivors, 2026-10-22) ---------------------


def test_exit_never_suppresses_block_exceptions(tmp_path):
    # Kills mutant "__exit__ return False -> True" (P3_exit_true): an
    # exception raised inside the with-block must PROPAGATE; a truthy
    # __exit__ silently swallows it.
    root = tmp_path / 'root'; root.mkdir()
    with pytest.raises(ValueError, match='^sentinel$'):
        with LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW):
            raise ValueError('sentinel')
    # the context manager still released the descriptor on the way out
    p2 = LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)
    fd = p2._wsfd
    p2.close()
    with pytest.raises(OSError):
        os.fstat(fd)


def test_walk_missing_middle_component_ends_walk_and_returns_final(tmp_path):
    # Kills mutant "walk FileNotFoundError break -> continue"
    # (P10_break_to_continue). A missing component ENDS the walk: the
    # original stops and returns the final component; with 'continue' the
    # walk proceeds to lstat a LATER component and refuses on the planted
    # symlink - a behavior change. (Direct helper call with 3 parts: every
    # in-class caller passes <=2, so only the helper surface observes this.)
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    try:
        os.symlink(root / 'tenant-a' / 's1', root / 'tenant-a' / 'linktrap')
        out = p._contained_anchored('missing', 'linktrap', 'final-name')
        assert out == 'final-name'
    finally:
        p.close()


# --- v7 pin (peer v6-audit survivor, 2026-10-22) ------------------------


def test_context_manager_exit_closes_its_own_fd_and_refuses_after(tmp_path):
    # Kills mutant "__exit__ drops self.close()": the pin must cover the
    # ACTUAL context's descriptor (the v6 fd assertion used a second
    # pipeline). After exit, the entered pipeline's fd is closed and its
    # operations refuse with the controlled error.
    root = tmp_path / 'root'; root.mkdir()
    with LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW) as p:
        p.ingest(IngestRequest(source=src('s1'), content='Alpha fact.',
                               mime_type='text/plain', actor_id='actor-a'))
        fd = p._wsfd
    with pytest.raises(OSError):
        os.fstat(fd)
    assert p._wsfd is None
    with pytest.raises(KnowledgeError) as ei:
        p.delete_verified('s1')
    assert str(ei.value) == 'pipeline is closed'


# --- v8 pins (peer v7-audit survivors, 2026-10-22) ----------------------


def test_register_persists_manifest_to_disk(tmp_path):
    # Kills del-Expr / wsfd->None at pipeline.py L782 (_persist_manifest
    # else-branch): register() must durably persist manifest.json through
    # the by-name route under the held workspace descriptor.
    root = tmp_path / 'root'; root.mkdir()
    p = LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)
    try:
        p.register(src('sreg'))
        assert (root / 'tenant-a' / 'sreg' / 'manifest.json').is_file()
    finally:
        p.close()


def test_written_files_are_owner_only_mode(tmp_path):
    # Kills the 0o600 mode variants (fs_safe.py L159 and the held-dir twin
    # L202): written files must land owner-read/write-only. umask is forced
    # to 0 for the duration so the CREATED mode is observed exactly.
    import stat as _st
    from app.modules.m25_knowledge_copilot_training import fs_safe
    old_umask = os.umask(0)
    try:
        parent = tmp_path / 'p'; parent.mkdir()
        fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')
        assert _st.S_IMODE((parent / 'child' / 'out.txt').stat().st_mode) == 0o600
        dfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fs_safe.write_file_at_held_dir(dfd, 'held.txt', b'data')
        finally:
            os.close(dfd)
        assert _st.S_IMODE((parent / 'held.txt').stat().st_mode) == 0o600
    finally:
        os.umask(old_umask)


def test_write_refuses_special_and_separator_components_exact(tmp_path):
    # Kills the '.'/'..' refusal mutants at fs_safe.py L150/L151 (str
    # variants, boolop, del-Raise) and pins the exact refusal text. Both
    # component slots of write_file_in_child_dir_at_fd, plus the held-dir
    # variant's filename guard.
    from app.modules.m25_knowledge_copilot_training import fs_safe
    parent = tmp_path / 'p'; parent.mkdir()
    for bad in ('.', '..', '', 'a/b'):
        with pytest.raises(OSError) as ei:
            fs_safe.write_file_in_child_dir(parent, bad, 'out.txt', b'x')
        assert str(ei.value) == 'invalid path component'
        with pytest.raises(OSError) as ei:
            fs_safe.write_file_in_child_dir(parent, 'child', bad, b'x')
        assert str(ei.value) == 'invalid path component'
    dfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(OSError) as ei:
            fs_safe.write_file_at_held_dir(dfd, '..', b'x')
        assert str(ei.value) == 'invalid path component'
    finally:
        os.close(dfd)


def test_short_write_refusal_exact_text(tmp_path, monkeypatch):
    # Pins the exact 'short write' refusal (fs_safe.py L167). The first
    # os.write returns 0 (then delegates), so a '< 0' comparison mutant
    # would complete instead of hanging.
    from app.modules.m25_knowledge_copilot_training import fs_safe
    calls = {'n': 0}
    real_write = os.write
    def flaky(fd, data):
        calls['n'] += 1
        if calls['n'] == 1:
            return 0
        return real_write(fd, data)
    monkeypatch.setattr(os, 'write', flaky)
    parent = tmp_path / 'p'; parent.mkdir()
    with pytest.raises(OSError) as ei:
        fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')
    assert str(ei.value) == 'short write'
    assert list(parent.rglob('*.tmp-*')) == []
    assert not (parent / 'child' / 'out.txt').exists()


def test_failed_write_cleanup_removes_temp_in_held_dir(tmp_path, monkeypatch):
    # Kills kw-drop dir_fd at fs_safe.py L177 (cleanup unlink): with the
    # rename forced to fail, the temp file must be removed from the HELD
    # directory - a CWD-relative unlink silently leaves it behind.
    from app.modules.m25_knowledge_copilot_training import fs_safe
    def boom(*a, **k):
        raise OSError('replace boom')
    monkeypatch.setattr(os, 'replace', boom)
    parent = tmp_path / 'p'; parent.mkdir()
    with pytest.raises(OSError) as ei:
        fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')
    assert str(ei.value) == 'replace boom'
    assert list((parent / 'child').glob('*.tmp-*')) == []


def test_cleanup_swallows_only_oserror(tmp_path, monkeypatch):
    # Kills except OSError -> BaseException at fs_safe.py L178: a NON-OSError
    # from the cleanup unlink must propagate, not be swallowed.
    from app.modules.m25_knowledge_copilot_training import fs_safe
    def boom_replace(*a, **k):
        raise OSError('replace boom')
    def boom_unlink(*a, **k):
        raise ValueError('unlink-sentinel')
    monkeypatch.setattr(os, 'replace', boom_replace)
    monkeypatch.setattr(os, 'unlink', boom_unlink)
    parent = tmp_path / 'p'; parent.mkdir()
    with pytest.raises(ValueError, match='^unlink-sentinel$'):
        fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')


def test_replace_targets_held_directory_not_cwd(tmp_path, monkeypatch):
    # Kills kw-drop dst_dir_fd at fs_safe.py L172: the rename's destination
    # must resolve inside the held directory even when the process CWD is
    # elsewhere - without dst_dir_fd the file lands in the CWD.
    from app.modules.m25_knowledge_copilot_training import fs_safe
    parent = tmp_path / 'p'; parent.mkdir()
    cwd = tmp_path / 'cwd'; cwd.mkdir()
    monkeypatch.chdir(cwd)
    fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')
    assert (parent / 'child' / 'out.txt').read_bytes() == b'data'
    assert not (cwd / 'out.txt').exists()
    assert not (cwd / 'child').exists()


def test_temp_name_shape_in_child_dir_write(tmp_path, monkeypatch):
    # Pins the '.tmp-' infix of the write temp name (fs_safe.py L158): the
    # rename source must be exactly '<filename>.tmp-<32 lowercase hex>'.
    from app.modules.m25_knowledge_copilot_training import fs_safe
    seen = []
    real_replace = os.replace
    def spy(src, dst, **kw):
        seen.append(src)
        return real_replace(src, dst, **kw)
    monkeypatch.setattr(os, 'replace', spy)
    parent = tmp_path / 'p'; parent.mkdir()
    fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')
    import re as _re
    assert len(seen) == 1
    assert _re.fullmatch(r'out\.txt\.tmp\-[0-9a-f]{32}', seen[0]), seen[0]


def test_ingest_temp_version_dir_name_shape(tmp_path, monkeypatch):
    # Pins the '.tmp-' infix of the ingest version temp dir (pipeline.py
    # L313): the rename source must be exactly '<target>.tmp-<32 hex>'.
    seen = []
    real_rename = os.rename
    def spy(src, dst, *a, **kw):
        seen.append((src, dst))
        return real_rename(src, dst, *a, **kw)
    monkeypatch.setattr(os, 'rename', spy)
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    try:
        import re as _re
        assert len(seen) == 1
        src_name, dst_name = seen[0]
        assert dst_name == 'v1'
        assert _re.fullmatch(r'v1\.tmp\-[0-9a-f]{32}', src_name), src_name
    finally:
        p.close()


# ====================== v10: A51 in-scope survivor pins ======================
# 65 unique physical mutants (73 list entries minus 8 label duplicates).
# 44 get executed behavioral kills below; 21 are adjudicated equivalent over
# the public input domain with executed battery witnesses (runner + vectors
# delivered alongside; each witness prints the mutated source sha256).

def _fd_count():
    return len(os.listdir('/proc/self/fd'))


def _fs():
    from app.modules.m25_knowledge_copilot_training import fs_safe
    return fs_safe


def _victim_parent(tmp_path, kind='dir'):
    parent = tmp_path / 'p'; parent.mkdir()
    if kind == 'dir':
        (parent / 'victim').mkdir()
    else:
        (parent / 'victim').write_text('x')
    return parent


def _open_dir(path):
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY)


def test_remove_first_lstat_non_oserror_propagates(tmp_path, monkeypatch):
    # Kills except-type->BaseException L78 (mutant: return True) and L80
    # (mutant: return False): a non-OSError BaseException from the FIRST
    # lstat must propagate, never be swallowed.
    fs_safe = _fs()
    real = os.lstat
    def ki(nm, *a, **k):
        if nm == 'victim':
            raise KeyboardInterrupt()
        return real(nm, *a, **k)
    monkeypatch.setattr(os, 'lstat', ki)
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    try:
        with pytest.raises(KeyboardInterrupt):
            fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)


def test_remove_regular_file_name_exact_false_and_never_opens(tmp_path, monkeypatch):
    # Kills cond-False L82 (the not-a-directory guard must skip the os.open:
    # original never calls open for a regular file, mutant attempts it).
    fs_safe = _fs()
    parent = _victim_parent(tmp_path, kind='file')
    pfd = _open_dir(parent)
    opened = []
    real_open = os.open
    def spy_open(*a, **k):
        opened.append(a[0] if a else k.get('path'))
        return real_open(*a, **k)
    monkeypatch.setattr(os, 'open', spy_open)
    try:
        r = fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)
    assert r is False
    assert opened == []


def test_remove_first_lstat_oserror_returns_exact_false(tmp_path, monkeypatch):
    # Kills return-None L81 and return-bool-flip L81: an OSError from the
    # first lstat yields exact False.
    fs_safe = _fs()
    real = os.lstat
    def ep(nm, *a, **k):
        if nm == 'victim':
            raise OSError('perm')
        return real(nm, *a, **k)
    monkeypatch.setattr(os, 'lstat', ep)
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    try:
        r = fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)
    assert r is False


def test_remove_open_oserror_returns_exact_false(tmp_path, monkeypatch):
    # Kills return-None L87 and return-bool-flip L87.
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    real_open = os.open
    def boom(nm, *a, **k):
        if nm == 'victim':
            raise OSError('open refused')
        return real_open(nm, *a, **k)
    monkeypatch.setattr(os, 'open', boom)
    try:
        r = fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)
    assert r is False


def test_remove_open_non_oserror_propagates(tmp_path, monkeypatch):
    # Kills except-type->BaseException L86 (mutant: return False).
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    real_open = os.open
    def ki(nm, *a, **k):
        if nm == 'victim':
            raise KeyboardInterrupt()
        return real_open(nm, *a, **k)
    monkeypatch.setattr(os, 'open', ki)
    try:
        with pytest.raises(KeyboardInterrupt):
            fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)


def _lstat_fake_ino(monkeypatch, name, fake_on_call):
    # The Nth lstat of `name` returns a fabricated stat with st_ino+1.
    real = os.lstat
    calls = {'n': 0}
    def fake(nm, *a, **k):
        st = real(nm, *a, **k)
        if nm == name:
            calls['n'] += 1
            if calls['n'] == fake_on_call:
                return os.stat_result((st.st_mode, st.st_ino + 1) + tuple(st[2:]))
        return st
    monkeypatch.setattr(os, 'lstat', fake)
    return calls


def test_remove_identity_mismatch_refuses_exact_false(tmp_path, monkeypatch):
    # Kills cond-False L90 (mutant proceeds to empty+rmdir the REAL dir),
    # return-None L91 and return-bool-flip L91: a dev/ino divergence between
    # the lstat and the held descriptor must refuse with exact False and
    # leave the directory in place. The fabricated first lstat stands in for
    # the lstat->open swap race (deterministic).
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    _lstat_fake_ino(monkeypatch, 'victim', 1)
    try:
        r = fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)
    assert r is False
    assert (parent / 'victim').is_dir()


def test_remove_recursion_error_returns_exact_false(tmp_path, monkeypatch):
    # Kills return-None L95 and return-bool-flip L95: when the recursive
    # emptying raises RecursionError the result is exact False (not removed).
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    def boom(fd):
        raise RecursionError()
    monkeypatch.setattr(fs_safe, 'empty_directory', boom)
    try:
        r = fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)
    assert r is False
    assert (parent / 'victim').is_dir()


def test_remove_recursion_other_baseexception_propagates(tmp_path, monkeypatch):
    # Kills except-type->BaseException L94: only RecursionError is caught.
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    def ki(fd):
        raise KeyboardInterrupt()
    monkeypatch.setattr(fs_safe, 'empty_directory', ki)
    try:
        with pytest.raises(KeyboardInterrupt):
            fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)


def test_remove_rmdir_skipped_when_recheck_diverges(tmp_path, monkeypatch):
    # Kills cond-True L98 and boolop L98 (and->or): when the pre-rmdir
    # re-lstat no longer matches the held descriptor identity, rmdir must
    # NOT run: original returns exact False with the dir intact; mutants
    # remove the real directory and return True.
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    _lstat_fake_ino(monkeypatch, 'victim', 2)
    try:
        r = fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)
    assert r is False
    assert (parent / 'victim').is_dir()


def test_remove_recheck_non_oserror_propagates(tmp_path, monkeypatch):
    # Kills except-type->BaseException L100 (mutant swallows, returns False).
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    real = os.lstat
    calls = {'n': 0}
    def ki2(nm, *a, **k):
        if nm == 'victim':
            calls['n'] += 1
            if calls['n'] == 2:
                raise KeyboardInterrupt()
        return real(nm, *a, **k)
    monkeypatch.setattr(os, 'lstat', ki2)
    try:
        with pytest.raises(KeyboardInterrupt):
            fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)


def test_remove_closes_held_sub_fd(tmp_path):
    # Kills del-Expr L103 (os.close(sub) dropped): no fd may leak.
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    before = _fd_count()
    try:
        r = fs_safe.remove_child_tree_at_fd(pfd, 'victim')
        leaked = _fd_count() - before
    finally:
        os.close(pfd)
    assert r is True
    assert leaked == 0


def test_remove_rmdir_oserror_returns_exact_false(tmp_path, monkeypatch):
    # Kills return-None L106 and return-bool-flip L106.
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    real_rmdir = os.rmdir
    def boom(nm, *a, **k):
        if nm == 'victim':
            raise OSError('Directory not empty')
        return real_rmdir(nm, *a, **k)
    monkeypatch.setattr(os, 'rmdir', boom)
    try:
        r = fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)
    assert r is False
    assert (parent / 'victim').is_dir()


def test_remove_final_lstat_non_oserror_propagates(tmp_path, monkeypatch):
    # Kills except-type->BaseException L107 (mutant: return True) and L109
    # (mutant: return False).
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    real = os.lstat
    calls = {'n': 0}
    def ki3(nm, *a, **k):
        if nm == 'victim':
            calls['n'] += 1
            if calls['n'] == 3:
                raise KeyboardInterrupt()
        return real(nm, *a, **k)
    monkeypatch.setattr(os, 'lstat', ki3)
    try:
        with pytest.raises(KeyboardInterrupt):
            fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)


def test_remove_final_lstat_oserror_returns_exact_false(tmp_path, monkeypatch):
    # Kills return-None L110 and return-bool-flip L110.
    fs_safe = _fs()
    parent = _victim_parent(tmp_path)
    pfd = _open_dir(parent)
    real = os.lstat
    calls = {'n': 0}
    def ep3(nm, *a, **k):
        if nm == 'victim':
            calls['n'] += 1
            if calls['n'] == 3:
                raise OSError('perm')
        return real(nm, *a, **k)
    monkeypatch.setattr(os, 'lstat', ep3)
    try:
        r = fs_safe.remove_child_tree_at_fd(pfd, 'victim')
    finally:
        os.close(pfd)
    assert r is False


def test_by_path_write_closes_parent_fd(tmp_path):
    # Kills del-Expr L135 (os.close(pfd) dropped in write_file_in_child_dir).
    fs_safe = _fs()
    parent = tmp_path / 'p'; parent.mkdir()
    before = _fd_count()
    fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')
    assert _fd_count() == before
    assert (parent / 'child' / 'out.txt').read_bytes() == b'data'


def test_write_mkdir_non_oserror_propagates(tmp_path, monkeypatch):
    # Kills except-type->BaseException L154 (mutant swallows and proceeds).
    fs_safe = _fs()
    parent = tmp_path / 'p'; parent.mkdir(); (parent / 'child').mkdir()
    real_mkdir = os.mkdir
    def ki(nm, *a, **k):
        if nm == 'child':
            raise KeyboardInterrupt()
        return real_mkdir(nm, *a, **k)
    monkeypatch.setattr(os, 'mkdir', ki)
    with pytest.raises(KeyboardInterrupt):
        fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')


def test_write_preexisting_temp_refuses_fileexistsexact(tmp_path, monkeypatch):
    # Kills bitor-left L159 idx259 (O_EXCL|O_NOFOLLOW dropped): with the temp
    # name fixed and pre-created, the original refuses with FileExistsError;
    # the mutant opens the existing file and overwrites its prefix.
    import types
    import uuid
    fs_safe = _fs()
    monkeypatch.setattr(uuid, 'uuid4', lambda: types.SimpleNamespace(hex='f' * 32))
    parent = tmp_path / 'p'; parent.mkdir(); (parent / 'child').mkdir()
    tmpf = parent / 'child' / ('out.txt.tmp-' + 'f' * 32)
    tmpf.write_bytes(b'SENTINEL-PRESERVED-TAIL')
    with pytest.raises(FileExistsError):
        fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')
    assert tmpf.read_bytes() == b'SENTINEL-PRESERVED-TAIL'


def test_write_single_byte_blob_completes(tmp_path):
    # Kills int+1/int->0 L166 (written <= 0 -> <= 1): a one-byte write is a
    # successful full write, not a short write.
    fs_safe = _fs()
    parent = tmp_path / 'p'; parent.mkdir()
    fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'x')
    assert (parent / 'child' / 'out.txt').read_bytes() == b'x'


def test_write_fsyncs_file_then_directory(tmp_path, monkeypatch):
    # Kills del-Expr L169 (os.fsync(fd)) and del-Expr L180 (os.fsync(dfd)):
    # exactly two fsyncs, file first (not a dir) then the holding directory.
    fs_safe = _fs()
    import stat as _st
    calls = []
    real_fsync = os.fsync
    def spy(fd):
        calls.append(_st.S_ISDIR(os.fstat(fd).st_mode))
        return real_fsync(fd)
    monkeypatch.setattr(os, 'fsync', spy)
    parent = tmp_path / 'p'; parent.mkdir()
    fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')
    assert calls == [False, True]


def test_at_fd_write_closes_file_and_dir_fds(tmp_path):
    # Kills del-Expr L171 (os.close(fd)) and del-Expr L182 (os.close(dfd)).
    fs_safe = _fs()
    parent = tmp_path / 'p'; parent.mkdir()
    pfd = _open_dir(parent)
    before = _fd_count()
    try:
        fs_safe.write_file_in_child_dir_at_fd(pfd, 'child', 'out.txt', b'data')
        assert _fd_count() == before
    finally:
        os.close(pfd)
    assert (parent / 'child' / 'out.txt').read_bytes() == b'data'


def test_successful_write_never_calls_unlink(tmp_path, monkeypatch):
    # Kills del-Assign L173, bool-flip L173 and cond-True L175: after a
    # successful replace the cleanup unlink must NOT run (mutants attempt it;
    # the resulting FileNotFoundError is swallowed, so only the call itself
    # distinguishes).
    fs_safe = _fs()
    unlinked = []
    real_unlink = os.unlink
    def spy(*a, **k):
        unlinked.append(a[0] if a else k.get('path'))
        return real_unlink(*a, **k)
    monkeypatch.setattr(os, 'unlink', spy)
    parent = tmp_path / 'p'; parent.mkdir()
    fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', b'data')
    assert unlinked == []
    assert (parent / 'child' / 'out.txt').read_bytes() == b'data'


def test_construction_workspace_must_be_a_directory(tmp_path, monkeypatch):
    # Kills bitor-left L74 idx421 (O_DIRECTORY dropped): a workspace path
    # that is a REGULAR FILE at open time must fail construction. The
    # patched Path.mkdir stands in for the mkdir->open swap race
    # (deterministic); original raises OSError(ENOTDIR), mutant opens the
    # file and constructs.
    from pathlib import Path as _P
    root = tmp_path / 'root'; root.mkdir()
    (root / 'tenant-a').write_text('not a dir')
    monkeypatch.setattr(_P, 'mkdir', lambda *a, **k: None)
    with pytest.raises(OSError):
        LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)


def test_close_non_oserror_propagates(tmp_path, monkeypatch):
    # Kills except-type->BaseException pipeline L81: close() swallows only
    # OSError. The fake really closes, then raises.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    target = p._wsfd
    real_close = os.close
    def ki_close(fd):
        real_close(fd)
        if fd == target:
            raise KeyboardInterrupt()
    monkeypatch.setattr(os, 'close', ki_close)
    with pytest.raises(KeyboardInterrupt):
        p.close()


def test_ingest_walk_lstat_non_oserror_propagates(tmp_path, monkeypatch):
    # Kills except-type->BaseException pipeline L122 (walk lstat): a
    # non-OSError BaseException mid-walk must propagate out of ingest.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    real = os.lstat
    def ki(nm, *a, **k):
        if nm == 's2':
            raise KeyboardInterrupt()
        return real(nm, *a, **k)
    monkeypatch.setattr(os, 'lstat', ki)
    with pytest.raises(KeyboardInterrupt):
        p.ingest(IngestRequest(source=src('s2'), content='B.', mime_type='text/plain', actor_id='actor-a'))
    p.close()


def test_ingest_skipped_final_check_ignores_root_symlink_v1(tmp_path):
    # Kills cond-True pipeline L127, kw-drop _check_final L298 and
    # bool-flip L298: ingest deliberately skips the helper-side final check
    # (_check_final=False; its own existence lstat runs later at the held
    # source-dir descriptor). Forcing it makes the walk lstat 'v1' at the
    # WORKSPACE ROOT (no descent at depth 2): a symlink sitting there must
    # NOT turn a legitimate ingest into a KnowledgeError.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    os.symlink(tmp_path, root / 'tenant-a' / 'v1')
    v = p.ingest(IngestRequest(source=src('s2'), content='B.', mime_type='text/plain', actor_id='actor-a'))
    assert v.number == 1
    assert (root / 'tenant-a' / 's2' / 'v1' / 'source.bin').read_bytes() == b'B.'
    p.close()


def test_delete_final_lstat_non_oserror_propagates(tmp_path, monkeypatch):
    # Kills except-type->BaseException pipeline L129 (final-check lstat):
    # the mutant swallows and proceeds to delete the record and the tree.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    real = os.lstat
    calls = {'n': 0}
    def ki(nm, *a, **k):
        if nm == 's1':
            calls['n'] += 1
            if calls['n'] == 1:
                raise KeyboardInterrupt()
        return real(nm, *a, **k)
    monkeypatch.setattr(os, 'lstat', ki)
    with pytest.raises(KeyboardInterrupt):
        p.delete_verified('s1')
    assert 's1' in p.records
    p.close()


def test_contained_walk_closes_dup_fd(tmp_path):
    # Kills del-Expr pipeline L133 (_os.close(fd) in the anchored walk
    # finally): delete_verified must not leak the duplicated descriptor.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    before = _fd_count()
    p.delete_verified('s1')
    assert _fd_count() == before
    p.close()


def test_version_target_lstat_anchored_to_held_dir_not_cwd(tmp_path, monkeypatch):
    # Kills kw-drop dir_fd pipeline L346: the version-target existence lstat
    # is relative to the held source-dir descriptor; a decoy file named 'v1'
    # in the process CWD must not refuse the ingest.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    canary = tmp_path / 'canary'; canary.mkdir()
    (canary / 'v1').write_text('decoy')
    monkeypatch.chdir(canary)
    v = p.ingest(IngestRequest(source=src('s2'), content='B.', mime_type='text/plain', actor_id='actor-a'))
    assert v.number == 1
    assert (root / 'tenant-a' / 's2' / 'v1' / 'source.bin').read_bytes() == b'B.'
    p.close()


# ---------------------------------------------------------------------------
# v11 pins: direct-helper descend-branch kills + public reachability kills
# for the 22 v10-challenged survivors. Base outcomes below were measured on
# pristine ce19b328 (see v11 records); each test FAILS on its mutant.
# ---------------------------------------------------------------------------

def _helper_tree(ws):
    # a/b (real dirs) with c -> ws symlink inside b; d/e with lnk -> ws inside
    # d; g with l2 -> ws; regular file 'file'; 'top' -> ws at root; x under d/e
    os.makedirs(ws / 'a' / 'b')
    os.symlink(ws, ws / 'a' / 'b' / 'c')
    os.makedirs(ws / 'd' / 'e')
    os.symlink(ws, ws / 'd' / 'lnk')
    os.makedirs(ws / 'g')
    os.symlink(ws, ws / 'g' / 'l2')
    (ws / 'file').write_text('x')
    os.symlink(ws, ws / 'top')


def _helper_pipe(tmp_path):
    root = tmp_path / 'root'; root.mkdir()
    p = LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)
    _helper_tree(p.workspace)
    return p


def test_ingest_walk_lstat_permissionerror_propagates(tmp_path, monkeypatch):
    # Kills except-type->BaseException pipeline L122 (idx520), PUBLIC ingest:
    # the walk-loop lstat of the source component runs on every ingest
    # (_contained_anchored(source_id, 'v1')). A PermissionError at exactly
    # that first anchored lstat must propagate; the mutant's BaseException
    # clause swallows it and the ingest completes.
    root = tmp_path / 'root'; root.mkdir()
    p = make(root)
    real = os.lstat
    import inspect
    def pe(nm, *a, **k):
        # only the walk-loop lstat inside _contained_anchored: it is the
        # lstat whose name is one of the INTERMEDIATE parts (parts[:-1]).
        # The final-check lstat reads parts[-1] and every later 's2' lstat
        # in ingest/fs_safe is unguarded; both must stay real. Targeting
        # f_locals keeps this robust to line shifts in pipeline.py.
        fr = inspect.currentframe().f_back
        if nm == 's2' and 'dir_fd' in k and fr.f_code.co_name == '_contained_anchored':
            if nm in tuple(fr.f_locals.get('parts', ()))[:-1]:
                raise PermissionError('denied')
        return real(nm, *a, **k)
    monkeypatch.setattr(os, 'lstat', pe)
    with pytest.raises(PermissionError):
        p.ingest(IngestRequest(source=src('s2'), content='B.', mime_type='text/plain', actor_id='actor-a'))
    p.close()


def test_helper_descend_only_to_parent_of_final_a_top(tmp_path):
    # Kills cond-True / Lt->LtE / int-1 / int->0 at pipeline L124
    # (idx441, 522, 650, 651): with 2 parts the base never descends, so the
    # final lstat of 'top' runs at the WORKSPACE fd and refuses the symlink.
    # Each mutant descends into 'a' first, lstats 'top' there, misses it and
    # returns 'top' with no refusal.
    p = _helper_pipe(tmp_path)
    with pytest.raises(KnowledgeError):
        p._contained_anchored('a', 'top')
    p.close()


def test_helper_descend_exactly_to_parent_of_final_d_lnk_x(tmp_path):
    # Kills cond-False / Lt->Gt / int+1 at pipeline L124 (idx442, 523, 649):
    # with 3 parts the base descends exactly once (i=0), so the walk lstat of
    # 'lnk' runs INSIDE 'd' and refuses the symlink. Each mutant never
    # descends, lstats 'lnk' at the workspace root (absent), breaks the walk
    # and returns 'x'.
    p = _helper_pipe(tmp_path)
    with pytest.raises(KnowledgeError):
        p._contained_anchored('d', 'lnk', 'x')
    p.close()


def test_helper_descend_open_assignment_kept(tmp_path):
    # Kills del-Assign pipeline L125 (idx524): deleting the descend open must
    # not turn a clean 3-part walk into an error. Base returns 'c'; the
    # mutant raises OSError(9) from the stale/closed descriptor.
    p = _helper_pipe(tmp_path)
    assert p._contained_anchored('a', 'b', 'c') == 'c'
    p.close()


def test_helper_descend_fd_rebind_kept(tmp_path):
    # Kills del-Assign pipeline L126 'fd=nfd' (idx526): base descends into
    # 'a' and returns 'c'; the mutant keeps the stale descriptor and errors.
    p = _helper_pipe(tmp_path)
    assert p._contained_anchored('a', 'b', 'c') == 'c'
    p.close()


def test_helper_descend_open_stays_anchored(tmp_path):
    # Kills kw-drop dir_fd pipeline L125 (idx588): the descend open must stay
    # anchored to the held descriptor; the mutant opens CWD-relative and
    # raises FileNotFoundError for 'a'. Base returns 'c'.
    p = _helper_pipe(tmp_path)
    assert p._contained_anchored('a', 'b', 'c') == 'c'
    p.close()


def test_helper_descend_open_requires_directory(tmp_path):
    # Kills bitor-left pipeline L125 O_DIRECTORY drop (idx652): descending
    # into the regular file 'file' must fail AT THE OPEN with
    # NotADirectoryError naming 'file'; the mutant opens it and only fails
    # one component later, naming 'x'.
    p = _helper_pipe(tmp_path)
    with pytest.raises(NotADirectoryError) as ei:
        p._contained_anchored('file', 'x', 'y')
    assert ei.value.filename == 'file'
    p.close()


def _race_swap(ws, outside, monkeypatch):
    # Arms a one-shot swap: the next anchored open of intermediate 'a' first
    # replaces the real dir with a symlink to an outside directory.
    real_open = os.open
    state = {'armed': True}
    def racy(path, flags, *a, **k):
        if state['armed'] and path == 'a' and 'dir_fd' in k:
            os.rename(ws / 'a', ws / 'a_gone')
            os.symlink(outside, ws / 'a')
            state['armed'] = False
        return real_open(path, flags, *a, **k)
    monkeypatch.setattr(os, 'open', racy)


def test_helper_descend_open_nofollow_race_refused(tmp_path, monkeypatch):
    # Kills bitor-right outer pipeline L125 (idx653: flags become
    # O_DIRECTORY only) and bitor-left inner (idx694: flags become
    # O_RDONLY|O_DIRECTORY) - both drop O_NOFOLLOW. A symlink swapped in
    # between the walk lstat and the descend open must be refused with
    # NotADirectoryError; each mutant follows the symlink out of the
    # workspace and returns 'c'.
    root = tmp_path / 'root'; root.mkdir()
    p = LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)
    _helper_tree(p.workspace)
    outside = tmp_path / 'outside'; outside.mkdir()
    _race_swap(p.workspace, outside, monkeypatch)
    with pytest.raises(NotADirectoryError):
        p._contained_anchored('a', 'b', 'c')
    p.close()


def test_helper_descend_closes_swapped_fd(tmp_path):
    # Kills del-Expr pipeline L126 '_os.close(fd)' (idx525): a 3-part walk
    # that descends once must return its descriptor count to baseline; the
    # mutant leaks the swapped-out fd.
    p = _helper_pipe(tmp_path)
    before = _fd_count()
    assert p._contained_anchored('a', 'b', 'c') == 'c'
    assert _fd_count() == before
    p.close()


def test_helper_final_lstat_reads_last_component(tmp_path):
    # Kills int-1/int->0 at pipeline L128 parts[-1] (idx706 and its
    # byte-identical sibling 707): the FINAL component must be lstat-ed, so
    # symlink 'top' refuses; the mutant lstats parts[0] instead, never looks
    # at 'top', and returns it.
    p = _helper_pipe(tmp_path)
    with pytest.raises(KnowledgeError):
        p._contained_anchored('x', 'top')
    p.close()


# ---------------------------------------------------------------------------
# v11 executed-witness pins: these PASS on base AND on their mutant; their
# green state under the mutated suite is the executed equivalence witness.
# ---------------------------------------------------------------------------

def test_witness_separator_id_refused_delete(tmp_path):
    # Witness for cmp In->NotIn pipeline L116 '_os.altsep in part'
    # (idx575): on POSIX altsep is None so the term short-circuits in both
    # versions; a separator-bearing raw id is refused identically via the
    # os.sep term, and a plain missing id raises KeyError identically.
    p = _helper_pipe(tmp_path)
    with pytest.raises(KnowledgeError) as ei:
        p.delete_verified('a/b')
    assert 'separators' in str(ei.value)
    with pytest.raises(KeyError):
        p.delete_verified('zz')
    p.close()


    # PLATFORM CONDITION: equivalence holds under Linux/POSIX semantics (O_RDONLY == 0).
def test_witness_ctor_open_flags_exact(tmp_path, monkeypatch):
    # Witness for bitor-right pipeline L74 '_os.O_RDONLY|_os.O_NOFOLLOW'
    # (idx506): O_RDONLY == 0, so the mutated expression computes the
    # identical flags value; capture the actual constructor open flags.
    seen = []
    real_open = os.open
    def cap(path, flags, *a, **k):
        seen.append((str(path), int(flags)))
        return real_open(path, flags, *a, **k)
    monkeypatch.setattr(os, 'open', cap)
    root = tmp_path / 'root'; root.mkdir()
    p = LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)
    ws_opens = [f for path, f in seen if path.endswith('tenant-a')]
    assert ws_opens == [os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY]
    p.close()


    # PLATFORM CONDITION: equivalence holds under Linux/POSIX semantics (O_CREAT|O_EXCL refuses any existing path, including symlinks).
def test_witness_write_tmp_symlink_refused_fileexists(tmp_path, monkeypatch):
    # Witness for bitor-left fs_safe L159 (idx167, O_NOFOLLOW drop): O_EXCL
    # is retained, so a pre-existing symlink at the temp name refuses with
    # FileExistsError in both versions.
    from app.modules.m25_knowledge_copilot_training import fs_safe
    import uuid, types
    d = tmp_path / 'w'; d.mkdir(); (d / 'sub').mkdir()
    fixed = uuid.UUID('12345678-1234-5678-1234-567812345678')
    monkeypatch.setattr(uuid, 'uuid4', lambda: fixed)
    os.symlink('/etc/hostname', d / 'sub' / f'f.tmp-{fixed.hex}')
    with pytest.raises(FileExistsError):
        fs_safe.write_file_in_child_dir(d, 'sub', 'f', b'data')


def test_witness_context_manager_protocol(tmp_path):
    # Witness for return-None pipeline L83 __exit__ (idx360): the with
    # protocol reads only truthiness - exceptions propagate unsuppressed and
    # a normal exit closes the pipeline, identically for False and None.
    root = tmp_path / 'root'; root.mkdir()
    with LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW) as p:
        pass
    with pytest.raises(KnowledgeError):
        p.ingest(IngestRequest(source=src('s9'), content='B.', mime_type='text/plain', actor_id='actor-a'))
    root2 = tmp_path / 'root2'; root2.mkdir()
    with pytest.raises(ValueError):
        with LocalKnowledgePipeline(root2, 'tenant-a', 'actor-a', clock=lambda: NOW):
            raise ValueError('boom')


    # PLATFORM CONDITION: equivalence argued for the POSIX descriptor flow; guard ordering is platform-independent but fd semantics are Linux/POSIX.
def test_witness_closed_ingest_refused_exact(tmp_path):
    # Witness for del-Expr pipeline L338 '_require_open' (idx445): ingest's
    # earlier _contained_anchored call refuses a closed pipeline with the
    # controlled KnowledgeError before the L338 guard is ever reached.
    root = tmp_path / 'root'; root.mkdir()
    p = LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)
    p.close()
    with pytest.raises(KnowledgeError) as ei:
        p.ingest(IngestRequest(source=src('s1'), content='A.', mime_type='text/plain', actor_id='actor-a'))
    assert str(ei.value) == 'pipeline is closed'


    # PLATFORM CONDITION: equivalence holds under Linux/POSIX semantics (O_RDONLY == 0; kernel ENOTDIR/ELOOP behavior per race pin).
def test_witness_descend_open_flags_exact(tmp_path, monkeypatch):
    # Witness for bitor-right inner pipeline L125 (idx695): dropping
    # O_RDONLY (== 0) leaves the descend-open flags value identical; capture
    # the actual flags passed for intermediate 'a'.
    p = _helper_pipe(tmp_path)
    seen = []
    real_open = os.open
    def cap(path, flags, *a, **k):
        if path == 'a' and 'dir_fd' in k:
            seen.append(int(flags))
        return real_open(path, flags, *a, **k)
    monkeypatch.setattr(os, 'open', cap)
    assert p._contained_anchored('a', 'b', 'c') == 'c'
    assert seen == [os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY]
    p.close()


# ---------------------------------------------------------------------------
# v12 pins: comparison cross-product kills (altsep class, inode-recheck race,
# is-not loop bound) + __exit__ exact return. Base outcomes measured on
# pristine ce19b328 before each kill claim (see v12 records).
# ---------------------------------------------------------------------------

def test_delete_altsep_separator_id_refused(tmp_path, monkeypatch):
    # Kills cmp In->NotIn pipeline L116 altsep term (idx575) and the
    # cmpX In->Gt / In->GtE / In->Eq / In->Is cross-product mutants on the
    # same term: with os.altsep set (Windows semantics simulated), a raw id
    # containing the alt separator must be refused. Base: KnowledgeError;
    # each mutant lets it through and dies on the missing record.
    monkeypatch.setattr(os, 'altsep', '\\')
    p = _helper_pipe(tmp_path)
    with pytest.raises(KnowledgeError) as ei:
        p.delete_verified('a\\b')
    assert 'separators' in str(ei.value)
    p.close()


def test_delete_altsep_set_clean_id_misses(tmp_path, monkeypatch):
    # Kills cmpX In->Lt / In->LtE / In->NotEq / In->IsNot on the pipeline
    # L116 altsep term: with os.altsep set, a CLEAN id contains no separator,
    # so the guard must stay quiet and the miss surface as KeyError; each of
    # these mutants evaluates the altsep comparison as True and refuses.
    monkeypatch.setattr(os, 'altsep', '\\')
    p = _helper_pipe(tmp_path)
    with pytest.raises(KeyError):
        p.delete_verified('ab')
    p.close()


def test_exit_returns_exact_false(tmp_path):
    # Kills return-None pipeline L83 (idx360): __exit__ must return exactly
    # False so the with-protocol non-suppression contract is inspectable;
    # the mutant returns None.
    root = tmp_path / 'root'; root.mkdir()
    p = LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: NOW)
    assert p.__exit__(None, None, None) is False


def test_remove_held_inode_recheck_exact(tmp_path, monkeypatch):
    # Kills cmpX NotEq->Lt fs_safe L90: after the child dir is opened, the
    # held descriptor's (dev, ino) MUST be compared for INEQUALITY against
    # the pre-open lstat - the inode-swap race. The '<' mutant only refuses
    # when the held tuple sorts below the lstat tuple. Executed witness:
    # fstat reports an inode one ABOVE the lstat-ed one (deterministic swap
    # simulation); base refuses and keeps the tree, mutant empties+removes it.
    from app.modules.m25_knowledge_copilot_training import fs_safe
    import stat as _stat
    root = tmp_path / 'root'; (root / 'victim' / 'sub').mkdir(parents=True)
    pfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    vino = os.lstat(root / 'victim').st_ino
    real_fstat = os.fstat
    def fake_fstat(fd):
        st = real_fstat(fd)
        if _stat.S_ISDIR(st.st_mode) and st.st_ino == vino:
            return os.stat_result((st[0], st[1] + 1, st[2], *st[3:]))
        return st
    monkeypatch.setattr(os, 'fstat', fake_fstat)
    try:
        assert fs_safe.remove_child_tree_at_fd(pfd, 'victim') is False
        assert (root / 'victim' / 'sub').is_dir()
    finally:
        os.close(pfd)


def test_remove_final_recheck_exact(tmp_path, monkeypatch):
    # Kills cmpX Eq->LtE fs_safe L98: after empty_directory the entry must be
    # re-identified by EQUAL (dev, ino) before rmdir - a directory swapped in
    # after emptying must survive. The '<=' mutant rmdirs when the swapped
    # inode sorts below the held one. Executed witness: the post-empty lstat
    # reports an inode one BELOW held (deterministic swap simulation); base
    # skips the rmdir, mutant removes the directory.
    from app.modules.m25_knowledge_copilot_training import fs_safe
    root = tmp_path / 'root'; (root / 'victim' / 'sub').mkdir(parents=True)
    pfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    real_lstat = os.lstat
    calls = []
    def fake_lstat(nm, *a, **k):
        st = real_lstat(nm, *a, **k)
        if nm == 'victim' and 'dir_fd' in k:
            calls.append(1)
            if len(calls) == 2:
                return os.stat_result((st[0], st[1] - 1, st[2], *st[3:]))
        return st
    monkeypatch.setattr(os, 'lstat', fake_lstat)
    try:
        assert fs_safe.remove_child_tree_at_fd(pfd, 'victim') is False
        assert (root / 'victim').is_dir()
    finally:
        os.close(pfd)


def _remove_deep(ws, n, name):
    # recursion-safe teardown: re-walk to the current bottom and rmdir it,
    # one level per pass; pytest's own tmp cleanup uses recursive rmtree,
    # which overflows on trees this deep if any of the chain is left behind
    for depth in range(n, 0, -1):
        fd = os.open(ws, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for _ in range(depth - 1):
                nfd = os.open(name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)
                os.close(fd)
                fd = nfd
            os.rmdir(name, dir_fd=fd)
        finally:
            os.close(fd)


def _build_deep(ws, n, name):
    fd = os.open(ws, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for _ in range(n):
            os.mkdir(name, dir_fd=fd)
            nfd = os.open(name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = nfd
    finally:
        os.close(fd)


def test_helper_descend_bound_259_components(tmp_path, monkeypatch):
    # Kills cmpX Lt->IsNot pipeline L124 (mx159): `i is not len(parts)-2`
    # coincides with `<` only while the compared ints are identity-cached
    # (<=256); at 259 components the base stops descending after 257 opens
    # but the mutant descends once more. Open-count is the executed witness.
    p = _helper_pipe(tmp_path)
    _build_deep(p.workspace, 259, 'z')
    real_open = os.open
    opens = []
    def cap(path, flags, *a, **k):
        if path == 'z' and 'dir_fd' in k:
            opens.append(1)
        return real_open(path, flags, *a, **k)
    monkeypatch.setattr(os, 'open', cap)
    try:
        assert p._contained_anchored(*(('z',) * 259)) == 'z'
        assert len(opens) == 257
    finally:
        _remove_deep(p.workspace, 259, 'z')
    p.close()


def test_helper_descend_bound_2048_components(tmp_path, monkeypatch):
    # Same kill at 2048 components (loop-bound hygiene): base opens exactly
    # 2046 times; the is-not mutant opens once more.
    p = _helper_pipe(tmp_path)
    _build_deep(p.workspace, 2048, 'z')
    real_open = os.open
    opens = []
    def cap(path, flags, *a, **k):
        if path == 'z' and 'dir_fd' in k:
            opens.append(1)
        return real_open(path, flags, *a, **k)
    monkeypatch.setattr(os, 'open', cap)
    try:
        assert p._contained_anchored(*(('z',) * 2048)) == 'z'
        assert len(opens) == 2046
    finally:
        _remove_deep(p.workspace, 2048, 'z')
    p.close()


def test_witness_descend_bound_exact_count(tmp_path, monkeypatch):
    # Witness for cmpX Lt->NotEq pipeline L124 (mx157): over the loop's i
    # range [0, len(parts)-2] the '<' and '!=' bounds coincide; a 4-part walk
    # descends exactly twice and returns the final component. Green under the
    # mutant = executed witness.
    p = _helper_pipe(tmp_path)
    real_open = os.open
    opens = []
    def cap(path, flags, *a, **k):
        if 'dir_fd' in k and path in ('a', 'b'):
            opens.append(1)
        return real_open(path, flags, *a, **k)
    monkeypatch.setattr(os, 'open', cap)
    assert p._contained_anchored('a', 'b', 'zz', 'top') == 'top'
    assert len(opens) == 2
    p.close()


def test_write_successful_partial_writes_complete(tmp_path, monkeypatch):
    # Kills fs_safe.py L168 assign-value->None (view = view[written:] ->
    # view = None): SUCCESSFUL partial writes must still deliver the whole
    # blob. os.write is frame-targeted to the fs_safe write loop and returns
    # kernel-legal partial writes of at most 3 bytes. Payload is built at
    # runtime, not a literal. Hang guard: one 60-second SIGALRM (at most 60s,
    # no short wall-clock alarm); the PRIOR SIGALRM handler and the
    # PRIOR itimer value (captured via getitimer at entry) are both restored
    # in finally. Platform: POSIX/Linux
    # os.write + signal semantics.
    fs_safe = _fs()
    import signal as _sig
    import sys as _sys
    data = bytes(bytearray((0x30 + i) & 0x7F for i in range(16)))
    assert len(data) == 16
    calls = []
    real_write = os.write
    def partial(fd, buf):
        if not _sys._getframe(1).f_code.co_filename.endswith('fs_safe.py'):
            return real_write(fd, buf)
        chunk = bytes(buf[:3])
        n = real_write(fd, chunk)
        calls.append(n)
        return n
    def _boom(signum, frame):
        raise TimeoutError('write loop hang guard fired (60s)')
    old_handler = _sig.signal(_sig.SIGALRM, _boom)
    old_timer = _sig.getitimer(_sig.ITIMER_REAL)
    _sig.setitimer(_sig.ITIMER_REAL, 60.0)
    monkeypatch.setattr(os, 'write', partial)
    parent = tmp_path / 'p'; parent.mkdir()
    try:
        fs_safe.write_file_in_child_dir(parent, 'child', 'out.txt', data)
    finally:
        _sig.setitimer(_sig.ITIMER_REAL, 0.0)
        _sig.signal(_sig.SIGALRM, old_handler)
        _sig.setitimer(_sig.ITIMER_REAL, *old_timer)
    assert len(calls) >= 2 and all(0 < n <= 3 for n in calls)
    assert (parent / 'child' / 'out.txt').read_bytes() == data
