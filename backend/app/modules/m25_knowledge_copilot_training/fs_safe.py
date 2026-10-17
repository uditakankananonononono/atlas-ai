"""Descriptor-anchored removal for tenant workspace cleanup (stdlib only).

Entries are unlinked relative to an open directory descriptor with
O_NOFOLLOW, so symlinks are never followed and a pathname swapped after a
check cannot redirect removal into another object. Best-effort: nothing here
is a completed rollback. Not closed: the final-name rmdir can still hit an
EMPTY directory swapped in after the identity check; components above the
parent are not pinned; crash/fsync durability is not addressed.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY


def empty_directory(fd: int) -> None:
    """Remove every entry under the directory open at fd; errors are skipped."""
    try:
        names = [e.name for e in os.scandir(fd)]
    except OSError:
        return
    for name in names:
        try:
            st = os.lstat(name, dir_fd=fd)
            if stat.S_ISDIR(st.st_mode):
                sub = os.open(name, _FLAGS, dir_fd=fd)
                try:
                    empty_directory(sub)
                finally:
                    os.close(sub)
                os.rmdir(name, dir_fd=fd)
            else:
                os.unlink(name, dir_fd=fd)
        except OSError:
            continue


def remove_child_tree(parent: Path, name: str) -> bool:
    """Remove the real directory ``name`` under ``parent`` without following links.

    Returns True only when the name is verifiably absent afterwards (also when
    it was already absent). A symlink, a regular file or any other non-directory
    at the name is left in place and returns False. Never raises OSError.
    """
    if not name or name in (".", "..") or os.sep in name:
        return False
    try:
        pfd = os.open(parent, _FLAGS)
    except OSError:
        return False
    try:
        try:
            st = os.lstat(name, dir_fd=pfd)
        except FileNotFoundError:
            return True
        except OSError:
            return False
        if not stat.S_ISDIR(st.st_mode):
            return False
        try:
            sub = os.open(name, _FLAGS, dir_fd=pfd)
        except OSError:
            return False
        try:
            held = os.fstat(sub)
            if (held.st_dev, held.st_ino) != (st.st_dev, st.st_ino):
                return False
            try:
                empty_directory(sub)
            except RecursionError:
                return False
            try:
                now = os.lstat(name, dir_fd=pfd)
                if stat.S_ISDIR(now.st_mode) and (now.st_dev, now.st_ino) == (held.st_dev, held.st_ino):
                    os.rmdir(name, dir_fd=pfd)
            except OSError:
                pass
        finally:
            os.close(sub)
        try:
            os.lstat(name, dir_fd=pfd)
            return False
        except FileNotFoundError:
            return True
        except OSError:
            return False
    finally:
        os.close(pfd)


def write_file_in_child_dir(parent: Path, dirname: str, filename: str, blob: bytes) -> None:
    """Atomically replace ``dirname/filename`` under ``parent`` from ``blob``.

    Everything is anchored to descriptors: ``parent`` and the child directory
    are opened O_NOFOLLOW (the child is created via dir_fd when absent), the
    temp file is created O_EXCL|O_NOFOLLOW inside the held child descriptor,
    fsynced, renamed over ``filename`` with both ends on the held descriptor,
    and the held directory is fsynced. A pathname swapped to a symlink or a
    different directory after the caller's containment check cannot redirect
    the write. On failure before the rename the temp file this call created is
    unlinked; the previous ``filename`` is untouched. Raises OSError.
    Not closed: components above ``parent`` are opened by path; durability
    depends on the filesystem; a crash between steps can leave the temp file.
    """
    import uuid

    for part in (dirname, filename):
        if not part or part in (".", "..") or os.sep in part:
            raise OSError("invalid path component")
    pfd = os.open(parent, _FLAGS)
    try:
        try:
            os.mkdir(dirname, dir_fd=pfd)
        except FileExistsError:
            pass
        dfd = os.open(dirname, _FLAGS, dir_fd=pfd)
        try:
            tmp = f"{filename}.tmp-{uuid.uuid4().hex}"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
            renamed = False
            try:
                try:
                    view = memoryview(blob)
                    while view:
                        written = os.write(fd, view)
                        if written <= 0:
                            raise OSError("short write")
                        view = view[written:]
                    os.fsync(fd)
                finally:
                    os.close(fd)
                os.replace(tmp, filename, src_dir_fd=dfd, dst_dir_fd=dfd)
                renamed = True
            finally:
                if not renamed:
                    try:
                        os.unlink(tmp, dir_fd=dfd)
                    except OSError:
                        pass
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        os.close(pfd)


def write_file_at_held_dir(dfd: int, filename: str, blob: bytes) -> None:
    """Atomically replace ``filename`` inside an already-held directory fd.

    Same write contract as write_file_in_child_dir (O_EXCL|O_NOFOLLOW temp,
    fsync, os.replace with both ends on the held descriptor, directory fsync)
    but the caller pins the directory: a path swapped after the caller
    acquired ``dfd`` cannot redirect the write. Use when the caller already
    holds the target directory so the manifest and the bytes it records stay
    in the SAME directory even if the dir's pathname is replaced mid-attempt.
    Raises OSError. Not closed: durability depends on the filesystem; a crash
    between steps can leave the temp file.
    """
    import uuid

    if not filename or filename in (".", "..") or os.sep in filename:
        raise OSError("invalid path component")
    tmp = f"{filename}.tmp-{uuid.uuid4().hex}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
    renamed = False
    try:
        try:
            view = memoryview(blob)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("short write")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, filename, src_dir_fd=dfd, dst_dir_fd=dfd)
        renamed = True
    finally:
        if not renamed:
            try:
                os.unlink(tmp, dir_fd=dfd)
            except OSError:
                pass
    os.fsync(dfd)
