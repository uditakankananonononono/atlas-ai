"""Bounded document exports with atomic filesystem writes."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import tempfile
from typing import Callable, Mapping

from .lane_models import DocumentError, ExportFormat, GroundedDocument
from .lane_renderers import render_html, render_json, render_markdown, render_text


_RENDERERS: Mapping[ExportFormat, Callable[[GroundedDocument], str]] = {
    ExportFormat.MARKDOWN: render_markdown,
    ExportFormat.HTML: render_html,
    ExportFormat.TEXT: render_text,
    ExportFormat.JSON: render_json,
}
_EXTENSIONS = {
    ExportFormat.MARKDOWN: ".md", ExportFormat.HTML: ".html",
    ExportFormat.TEXT: ".txt", ExportFormat.JSON: ".json",
}
_CONTENT_TYPES = {
    ExportFormat.MARKDOWN: "text/markdown; charset=utf-8",
    ExportFormat.HTML: "text/html; charset=utf-8",
    ExportFormat.TEXT: "text/plain; charset=utf-8",
    ExportFormat.JSON: "application/json; charset=utf-8",
}


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    filename: str
    content_type: str
    data: bytes
    sha256: str

    @property
    def size(self) -> int:
        return len(self.data)


class DocumentExporter:
    def __init__(self, *, max_bytes: int = 10 * 1024 * 1024) -> None:
        if max_bytes < 1:
            raise ValueError("max export size must be positive")
        self.max_bytes = max_bytes

    def export(self, grounded: GroundedDocument, format: ExportFormat | str) -> ExportArtifact:
        try:
            fmt = ExportFormat(format)
        except ValueError as exc:
            raise DocumentError(f"unsupported export format: {format}") from exc
        data = _RENDERERS[fmt](grounded).encode("utf-8")
        if len(data) > self.max_bytes:
            raise DocumentError(
                f"rendered document is {len(data)} bytes; limit is {self.max_bytes}"
            )
        filename = f"{self._slug(grounded.document.title)}{_EXTENSIONS[fmt]}"
        return ExportArtifact(filename, _CONTENT_TYPES[fmt], data, sha256(data).hexdigest())

    def write(self, artifact: ExportArtifact, directory: str | Path, *, overwrite: bool = False) -> Path:
        root = Path(directory).resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = (root / artifact.filename).resolve()
        if root not in target.parents:
            raise DocumentError("export filename escapes destination directory")
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        fd, temporary = tempfile.mkstemp(prefix=".atlas-export-", dir=root)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(artifact.data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        return target

    @staticmethod
    def _slug(value: str) -> str:
        slug = "".join(char.lower() if char.isalnum() else "-" for char in value)
        slug = "-".join(filter(None, slug.split("-")))
        return slug[:100] or "document"
