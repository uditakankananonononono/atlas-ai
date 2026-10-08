"""Artifact confinement for M13 browser artifacts (best-effort, non-atomic).

Every M13 artifact write (screenshots, HAR recordings, bridged-page PNGs)
goes under one trusted root whose path components are validated and opened
relative to a pinned root descriptor with O_NOFOLLOW | O_DIRECTORY, and
whose kernel-reported location is re-read (/proc/self/fd) immediately
before and after each write.

What this CLOSES - deterministic, pre-write attacks only:

- traversal and dot-only ids ("..") rejected before any filesystem use;
- preexisting symlink components and planted symlink filenames refused;
- a directory swap or rename that has ALREADY happened when the walk or
  the pre/post-write location check runs (the deterministic pre-creation
  rename attack) is refused, and a component renamed away before the walk
  is recreated inside the root so bytes never follow the moved inode.

What is NOT closed - the checks are check-then-act, NOT atomic:

- a rename or bind mount that lands AFTER the final post-write check still
  escapes; the window is small but real;
- the post-write unlink cannot undo bytes another process read from the
  escaped file before the check ran;
- HAR detection happens AFTER the Playwright driver has already written
  audit.har, so escaped HAR bytes are detected, not prevented.

Against a hostile same-UID actor there is no "zero escaped bytes"
guarantee here. Full confinement needs mount namespaces, not path checks.
Do not claim more than this.
"""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path

__all__ = ["ArtifactContainmentError", "validate_segment", "ArtifactRoot"]


class ArtifactContainmentError(ValueError):
    """A path segment or on-disk component would escape the trusted root."""


# Tenant/session/device names observed in the module: alphanumerics plus
# ".", "_", "-" (bridged session ids look like "pc.<device>.<name>") and
# "@"/"+" for OIDC-style tenant subjects. Slashes and dot-only names stay
# forbidden, which is what actually blocks traversal.
_SEGMENT = re.compile(r"^[A-Za-z0-9_.@+-]{1,120}$")

_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_DIR_MODE = 0o700
_FILE_MODE = 0o600


def validate_segment(value: str, what: str = "path segment") -> str:
    """Return ``value`` if it is a safe single path component, else raise.

    Rejects empty, overlong, slashed, control-character and dot-only
    components. "." and ".." are the traversal primitive; a charset check
    alone does not stop them, because both match ``[A-Za-z0-9_.-]+``.
    """
    if not isinstance(value, str) or not _SEGMENT.fullmatch(value):
        raise ArtifactContainmentError(f"invalid {what}: forbidden characters or length")
    if value.strip(".") == "":
        raise ArtifactContainmentError(f"invalid {what}: dot-only names are not allowed")
    return value


def _kernel_path(fd: int) -> "Path | None":
    """Current absolute path of an open descriptor, per the kernel.

    Linux ``/proc/self/fd`` reflects renames: a directory moved out from
    under us shows its new location here. Returns None when the platform
    cannot report it.
    """
    try:
        raw = os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        return None
    if raw.endswith(" (deleted)"):
        return None  # unlinked inode; there is no safe path to validate
    return Path(raw)


class ArtifactRoot:
    """A pinned trusted root; all artifact writes go through its descriptor."""

    def __init__(self, root: str | Path):
        if not _O_NOFOLLOW or not _O_DIRECTORY:
            raise ArtifactContainmentError(
                "artifact confinement needs O_NOFOLLOW and O_DIRECTORY support")
        requested = Path(root)
        requested.mkdir(parents=True, exist_ok=True)
        # Resolve once so a symlinked configured root points at its real
        # target, then pin that target by descriptor for the object lifetime.
        self._display = requested.resolve()
        self._fd = os.open(self._display, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW)
        try:
            if not stat.S_ISDIR(os.fstat(self._fd).st_mode):
                raise ArtifactContainmentError("artifact root is not a directory")
        except BaseException:
            os.close(self._fd)
            raise

    # -- descriptor-walking primitives -------------------------------------

    def _step(self, fd: int, name: str, create: bool) -> int:
        """Open one component below ``fd``; optionally mkdir it first.

        The mkdir and the open are both relative to the held parent
        descriptor, so a symlink swapped in above this component is already
        irrelevant, and a symlink *at* this component fails the O_NOFOLLOW
        open instead of being followed.
        """
        validate_segment(name)
        if create:
            try:
                os.mkdir(name, _DIR_MODE, dir_fd=fd)
            except FileExistsError:
                pass
        try:
            return os.open(name, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW, dir_fd=fd)
        except OSError as error:
            raise ArtifactContainmentError(
                f"artifact path component is missing or not a real directory: {name!r}") from error

    def _assert_fd_contained(self, fd: int, what: str) -> None:
        """Refuse if the kernel-reported path of ``fd`` has left the root.

        This is the rename pin: a descriptor pins an inode, and a same-UID
        rename can move that inode outside the root after the walk. The
        kernel still reports the moved location, so check it.
        """
        reported = _kernel_path(fd)
        if reported is None:
            raise ArtifactContainmentError(
                f"cannot re-verify the location of {what}; refusing the write")
        try:
            resolved = reported.resolve(strict=False)
        except OSError as error:
            raise ArtifactContainmentError(f"cannot resolve the location of {what}") from error
        if resolved != self._display and self._display not in resolved.parents:
            raise ArtifactContainmentError(
                f"{what} was moved outside the trusted root before the write")

    def assert_dir_intact(self, *segments: str) -> None:
        """Verify ``root/segments...`` still exists, is real, and is contained."""
        fd = self.open_dir(*segments, create=False)
        try:
            self._assert_fd_contained(fd, "artifact directory")
        finally:
            os.close(fd)

    def open_dir(self, *segments: str, create: bool = True) -> int:
        """Return a descriptor for ``root/segments...``; caller must close it.

        The returned descriptor's kernel-reported path is verified inside
        the root before return.
        """
        fd = self._fd
        held = False
        try:
            for segment in segments:
                nxt = self._step(fd, segment, create)
                if held:
                    os.close(fd)
                fd, held = nxt, True
            if segments:
                self._assert_fd_contained(fd, "artifact directory")
            return fd
        except BaseException:
            if held:
                os.close(fd)
            raise

    def prepare_dir(self, *segments: str) -> Path:
        """Pinned-create ``root/segments...`` and return its display path.

        The returned string is safe to hand to APIs that need a path (HAR
        recording): every component was opened as a real directory during
        this call, and the path is re-verified against the pinned root
        before return.
        """
        fd = self.open_dir(*segments, create=True)
        os.close(fd)
        target = self._display.joinpath(*segments)
        self.verify_contained(target)
        return target

    def verify_contained(self, path: str | Path) -> Path:
        """Resolve ``path`` and require it to live under the pinned root."""
        resolved = Path(path).resolve()
        if resolved != self._display and self._display not in resolved.parents:
            raise ArtifactContainmentError("artifact path escapes the trusted root")
        return resolved

    # -- the atomic write ----------------------------------------------------

    def write_bytes(self, segments: tuple[str, ...] | list[str], filename: str, data: bytes) -> Path:
        """Write ``data`` to ``root/<segments...>/<filename>`` with best-effort
        containment (see the module docstring for exactly what is and is not
        closed; the checks are non-atomic).

        The final open is O_CREAT | O_EXCL | O_NOFOLLOW relative to the held
        session-directory descriptor: a pre-existing file or a planted
        symlink at the filename is refused, and a directory already swapped
        or renamed when the checks run cannot redirect the write, because
        the bytes go through the descriptor, not the path string.
        """
        validate_segment(filename, "artifact filename")
        dir_fd = self.open_dir(*segments, create=True)
        try:
            self.write_fd(dir_fd, filename, data)
        finally:
            os.close(dir_fd)
        return self._display.joinpath(*segments, filename)

    def write_fd(self, dir_fd: int, filename: str, data: bytes) -> None:
        """Contained write of ``data`` to ``filename`` below a held dir fd.

        Safe against the held-fd rename attack: a descriptor pins the inode,
        not the path, so the kernel-reported location of the directory is
        re-validated immediately before the file create, and the file's own
        location is re-validated before and after the bytes are written. On
        a post-write violation the file is unlinked through the same fd and
        the write is refused.
        """
        validate_segment(filename, "artifact filename")
        self._assert_fd_contained(dir_fd, "artifact directory")
        try:
            file_fd = os.open(
                filename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW,
                _FILE_MODE,
                dir_fd=dir_fd,
            )
        except OSError as error:
            raise ArtifactContainmentError(
                f"artifact filename refuses a safe create: {filename!r}") from error
        try:
            self._assert_fd_contained(file_fd, "artifact file")
            view = memoryview(data)
            while view:
                written = os.write(file_fd, view)
                view = view[written:]
            # Post-write re-check: if a rename raced the write, the bytes
            # escaped through no fault of the walk - unwind what we can
            # and refuse loudly rather than claim containment.
            try:
                self._assert_fd_contained(file_fd, "artifact file")
            except ArtifactContainmentError:
                try:
                    os.unlink(filename, dir_fd=dir_fd)
                except OSError:
                    pass
                raise
        finally:
            os.close(file_fd)

    def write_path(self, path: str | Path, data: bytes) -> Path:
        """Write ``data`` at ``path``, which must resolve inside the root.

        Duck-type compatibility for callers that still pass a full path:
        containment is verified first, then the write goes through the same
        descriptor walk as ``write_bytes``.
        """
        target = self.verify_contained(path)
        relative = target.relative_to(self._display)
        *segments, filename = relative.parts
        return self.write_bytes(tuple(segments), filename, data)

    def close(self) -> None:
        if getattr(self, "_fd", None) is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "ArtifactRoot":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
