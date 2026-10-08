"""Swap-proof artifact confinement for M13 browser artifacts.

Every M13 artifact write (screenshots, HAR recordings, bridged-page PNGs)
lands under one trusted root. Two rules make the containment real rather
than advisory:

1. Path segments are validated before any filesystem use - no empty, dot-only
   (".", "..", "..."), slashed, or overlong component ever reaches the disk.
2. Directories are created and opened relative to a pinned root file
   descriptor, component by component, with O_NOFOLLOW | O_DIRECTORY. A
   component swapped for a symlink - before the walk or during it - is
   refused instead of followed, and bytes written through an already-held
   descriptor cannot be redirected by a later rename or link swap. This
   closes the mkdir-then-write gap where a concurrent swap of the session
   directory sent screenshot bytes outside the root.

Residual, honestly scoped: artifacts this process writes itself (via
``write_bytes``) are fully contained. Artifacts the Playwright *driver*
process writes later from a path string (the per-session ``audit.har``) are
not re-resolvable through our descriptors; those directories are pinned and
re-verified at context creation, but a same-UID local process that swaps the
session directory mid-context could still redirect that one driver write.
Directory modes are 0700 to narrow that window. Do not claim more than this.
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

    def open_dir(self, *segments: str, create: bool = True) -> int:
        """Return a descriptor for ``root/segments...``; caller must close it."""
        fd = self._fd
        held = False
        try:
            for segment in segments:
                nxt = self._step(fd, segment, create)
                if held:
                    os.close(fd)
                fd, held = nxt, True
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
        """Write ``data`` to ``root/<segments...>/<filename>`` swap-proof.

        The final open is O_CREAT | O_EXCL | O_NOFOLLOW relative to the held
        session-directory descriptor: a pre-existing file or a planted
        symlink at the filename is refused, and a directory swap that lands
        after the walk cannot redirect the write, because the bytes go
        through the descriptor, not the path string.
        """
        validate_segment(filename, "artifact filename")
        dir_fd = self.open_dir(*segments, create=True)
        try:
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
                view = memoryview(data)
                while view:
                    written = os.write(file_fd, view)
                    view = view[written:]
            finally:
                os.close(file_fd)
        finally:
            os.close(dir_fd)
        return self._display.joinpath(*segments, filename)

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
