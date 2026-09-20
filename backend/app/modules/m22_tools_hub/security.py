from __future__ import annotations

import hashlib
import io
import re
import stat
import zipfile
from dataclasses import dataclass

from .models import ScanFinding, ScanReport, ToolManifest


class ArtifactRejected(ValueError):
    pass


@dataclass(frozen=True)
class ScanPolicy:
    max_artifact_bytes: int = 50 * 1024 * 1024
    max_unpacked_bytes: int = 200 * 1024 * 1024
    max_files: int = 10_000
    max_compression_ratio: float = 100.0


_SUSPICIOUS = (
    ("dynamic-exec", re.compile(rb"\b(?:eval|exec)\s*\("), "high", "dynamic code execution"),
    ("shell-process", re.compile(rb"\b(?:os\.system|subprocess\.(?:run|Popen|call)|child_process\.(?:exec|spawn))\b"), "high", "shell/process execution"),
    ("credential-access", re.compile(rb"(?:\.aws/credentials|\.ssh/id_(?:rsa|ed25519)|/etc/shadow)"), "critical", "credential or system secret access"),
    ("reverse-shell", re.compile(rb"(?:/dev/tcp/|nc\s+-e\s+|bash\s+-i\s+>&)"), "critical", "reverse shell pattern"),
)


class SecurityScanner:
    def __init__(self, policy: ScanPolicy | None = None):
        self.policy = policy or ScanPolicy()

    def scan(self, artifact: bytes, manifest: ToolManifest) -> ScanReport:
        if len(artifact) > self.policy.max_artifact_bytes:
            raise ArtifactRejected("artifact exceeds configured byte limit")
        artifact_sha256 = hashlib.sha256(artifact).hexdigest()
        if artifact_sha256 != manifest.provenance.artifact_sha256:
            raise ArtifactRejected("artifact digest does not match provenance")
        findings: list[ScanFinding] = []
        scanned_bytes = 0
        seen: set[str] = set()
        try:
            archive = zipfile.ZipFile(io.BytesIO(artifact))
            infos = archive.infolist()
        except zipfile.BadZipFile as exc:
            raise ArtifactRejected("artifact must be a valid ZIP archive") from exc
        if len(infos) > self.policy.max_files:
            raise ArtifactRejected("archive contains too many files")
        for info in infos:
            path = info.filename
            normalized = _safe_archive_path(path)
            if normalized in seen:
                raise ArtifactRejected(f"duplicate archive member: {normalized}")
            seen.add(normalized)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ArtifactRejected(f"symbolic links are forbidden: {path}")
            if info.is_dir():
                continue
            scanned_bytes += info.file_size
            if scanned_bytes > self.policy.max_unpacked_bytes:
                raise ArtifactRejected("archive exceeds unpacked byte limit")
            if info.compress_size == 0 and info.file_size > 0:
                raise ArtifactRejected(f"invalid compression accounting: {path}")
            if info.compress_size and info.file_size / info.compress_size > self.policy.max_compression_ratio:
                raise ArtifactRejected(f"suspicious compression ratio: {path}")
            with archive.open(info) as handle:
                data = handle.read(self.policy.max_unpacked_bytes + 1)
            expected = manifest.files.get(normalized)
            actual = hashlib.sha256(data).hexdigest()
            if expected is None:
                findings.append(ScanFinding("unmanifested-file", "high", normalized, "file is not declared in manifest"))
            elif actual != expected:
                findings.append(ScanFinding("file-digest-mismatch", "critical", normalized, "file digest differs from manifest"))
            if _looks_textual(data):
                for code, pattern, severity, message in _SUSPICIOUS:
                    if pattern.search(data):
                        findings.append(ScanFinding(code, severity, normalized, message))
        missing = sorted(set(manifest.files) - seen)
        findings.extend(ScanFinding("missing-file", "critical", path, "manifested file missing from archive") for path in missing)
        return ScanReport(artifact_sha256, tuple(findings), len([x for x in infos if not x.is_dir()]), scanned_bytes)


def _safe_archive_path(raw: str) -> str:
    if not raw or raw.startswith(("/", "\\")) or "\\" in raw or "\x00" in raw:
        raise ArtifactRejected(f"unsafe archive path: {raw!r}")
    parts = raw.rstrip("/").split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ArtifactRejected(f"unsafe archive path: {raw!r}")
    return "/".join(parts)


def _looks_textual(data: bytes) -> bool:
    return b"\x00" not in data[:4096]
