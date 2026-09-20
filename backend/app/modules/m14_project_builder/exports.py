"""Export system for Atlas Module 14 (Project Builder).

Stdlib-only. Assembles a project directory from artifact payloads, generates
the README the spec requires ("outputs are assembled into a project directory
with README"), builds a SHA-256 export manifest, produces deterministic zip
archives (fixed entry timestamps so identical content yields identical
bytes), and verifies exports against their manifest.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple

from .artifacts import ArtifactRecord
from .milestones import Milestone


class ExportError(ValueError):
    """Base error for export operations."""


@dataclass(frozen=True)
class ExportEntry:
    relative_path: str
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class ExportManifest:
    project_id: str
    generated_at: str  # ISO-8601
    entries: Tuple[ExportEntry, ...]
    total_bytes: int
    content_sha256: str  # hash of the canonical entry listing

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "generated_at": self.generated_at,
            "total_bytes": self.total_bytes,
            "content_sha256": self.content_sha256,
            "entries": [
                {
                    "relative_path": e.relative_path,
                    "sha256": e.sha256,
                    "byte_size": e.byte_size,
                }
                for e in self.entries
            ],
        }


def safe_join(root: Path, relative_path: str) -> Path:
    """Resolve a workspace-relative path inside root, rejecting escapes."""
    if not relative_path or not relative_path.strip():
        raise ExportError("relative path must be non-empty")
    rel = Path(relative_path)
    if rel.is_absolute():
        raise ExportError(f"absolute paths are not allowed: {relative_path!r}")
    if any(part == ".." for part in rel.parts):
        raise ExportError(f"path must not contain '..': {relative_path!r}")
    resolved_root = root.resolve()
    target = (resolved_root / rel).resolve()
    if target != resolved_root and resolved_root not in target.parents:
        raise ExportError(f"path escapes the export root: {relative_path!r}")
    return target


def sha256_file(path: Path) -> str:
    digest = sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_project_files(
    root: Path, files: Mapping[str, bytes], overwrite: bool = False
) -> Tuple[ExportEntry, ...]:
    """Write payload bytes into the project directory, escape-protected."""
    entries = []
    for relative_path in sorted(files):
        payload = files[relative_path]
        if not isinstance(payload, (bytes, bytearray)):
            raise ExportError(f"payload for {relative_path!r} must be bytes")
        target = safe_join(root, relative_path)
        if target.exists() and not overwrite:
            raise ExportError(f"refusing to overwrite existing file: {relative_path!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(payload))
        entries.append(
            ExportEntry(
                relative_path=relative_path,
                sha256=sha256(bytes(payload)).hexdigest(),
                byte_size=len(payload),
            )
        )
    return tuple(entries)


def build_manifest(
    project_id: str,
    entries: Sequence[ExportEntry],
    generated_at: Optional[datetime] = None,
) -> ExportManifest:
    if not project_id:
        raise ExportError("project_id must be non-empty")
    stamp = (generated_at or datetime.now(timezone.utc)).isoformat()
    ordered = tuple(sorted(entries, key=lambda e: e.relative_path))
    canonical = json.dumps(
        [
            [e.relative_path, e.sha256, e.byte_size]
            for e in ordered
        ],
        separators=(",", ":"),
    ).encode("utf-8")
    return ExportManifest(
        project_id=project_id,
        generated_at=stamp,
        entries=ordered,
        total_bytes=sum(e.byte_size for e in ordered),
        content_sha256=sha256(canonical).hexdigest(),
    )


@dataclass(frozen=True)
class ReadmeContext:
    project_id: str
    goal: str
    status: str
    milestones: Tuple[Milestone, ...] = ()
    artifacts: Tuple[ArtifactRecord, ...] = ()
    overall_progress: Optional[float] = None
    assumptions: Tuple[str, ...] = ()
    risks: Tuple[str, ...] = ()
    generated_at: Optional[datetime] = None


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_readme(context: ReadmeContext) -> str:
    """Generate the project README markdown from plan, milestones, artifacts."""
    stamp = (context.generated_at or datetime.now(timezone.utc)).isoformat()
    lines = [
        f"# {_md_escape(context.goal)}",
        "",
        f"- **Project:** `{context.project_id}`",
        f"- **Status:** {context.status}",
    ]
    if context.overall_progress is not None:
        lines.append(f"- **Progress:** {context.overall_progress:.0%}")
    lines += [f"- **Generated:** {stamp}", "", "## Goal", "", context.goal, ""]
    if context.milestones:
        lines += [
            "## Milestones",
            "",
            "| Milestone | Phase | Status | Planned start | Planned end | Progress |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for m in context.milestones:
            start = m.planned_start.date().isoformat() if m.planned_start else "-"
            end = m.planned_end.date().isoformat() if m.planned_end else "-"
            lines.append(
                f"| {_md_escape(m.title)} | {m.phase} | {m.status.value} "
                f"| {start} | {end} | {m.progress:.0%} |"
            )
        lines.append("")
    if context.artifacts:
        lines += [
            "## Artifacts",
            "",
            "| Kind | URI | SHA-256 | Source |",
            "| --- | --- | --- | --- |",
        ]
        for a in context.artifacts:
            source = str(a.provenance.get("source") or a.provenance.get("generator") or "-")
            lines.append(
                f"| {a.kind} | `{_md_escape(a.uri)}` | `{a.sha256[:12]}...` "
                f"| {_md_escape(source)} |"
            )
        lines.append("")
    if context.assumptions:
        lines += ["## Assumptions", ""]
        lines += [f"- {_md_escape(a)}" for a in context.assumptions]
        lines.append("")
    if context.risks:
        lines += ["## Risks", ""]
        lines += [f"- {_md_escape(r)}" for r in context.risks]
        lines.append("")
    lines += [
        "## Verification",
        "",
        "Every file in this export is listed in `export_manifest.json` with its",
        "SHA-256 digest. Recompute digests to verify integrity; the manifest's",
        "`content_sha256` covers the canonical entry listing.",
        "",
    ]
    return "\n".join(lines)


# Deterministic zip timestamp (DOS epoch) so identical content zips identically.
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def create_zip(source_dir: Path, out_path: Path) -> ExportEntry:
    """Zip a directory deterministically; returns the archive's own entry."""
    source = source_dir.resolve()
    if not source.is_dir():
        raise ExportError(f"source directory does not exist: {source_dir}")
    members = sorted(p for p in source.rglob("*") if p.is_file())
    if not members:
        raise ExportError("source directory contains no files")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member in members:
            arcname = member.relative_to(source).as_posix()
            info = zipfile.ZipInfo(arcname, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, member.read_bytes())
    return ExportEntry(
        relative_path=out_path.name,
        sha256=sha256_file(out_path),
        byte_size=out_path.stat().st_size,
    )


@dataclass(frozen=True)
class ExportVerification:
    passed: bool
    missing: Tuple[str, ...]
    mismatched: Tuple[str, ...]
    extra: Tuple[str, ...]


def verify_export(
    root: Path,
    manifest: ExportManifest,
    allow_extra: Tuple[str, ...] = ("export_manifest.json",),
) -> ExportVerification:
    """Recompute digests for every manifest entry under root."""
    missing, mismatched = [], []
    for entry in manifest.entries:
        try:
            target = safe_join(root, entry.relative_path)
        except ExportError:
            # A manifest pointing outside the root is hostile or corrupt;
            # count it as mismatched rather than crashing verification.
            mismatched.append(entry.relative_path)
            continue
        if not target.is_file():
            missing.append(entry.relative_path)
            continue
        if sha256_file(target) != entry.sha256:
            mismatched.append(entry.relative_path)
    expected = {e.relative_path for e in manifest.entries} | set(allow_extra)
    extra = sorted(
        p.relative_to(root.resolve()).as_posix()
        for p in root.resolve().rglob("*")
        if p.is_file() and p.relative_to(root.resolve()).as_posix() not in expected
    )
    return ExportVerification(
        passed=not missing and not mismatched and not extra,
        missing=tuple(missing),
        mismatched=tuple(mismatched),
        extra=tuple(extra),
    )
