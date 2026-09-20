from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlparse

_TOOL_ID = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$")
_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PERMISSION = re.compile(r"^[a-z][a-z0-9_.:-]{1,127}$")


class ManifestError(ValueError):
    pass


class ReviewDecision(str, Enum):
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class Provenance:
    source_url: str
    publisher: str
    artifact_sha256: str
    signature: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Provenance":
        try:
            return cls(
                source_url=str(value["source_url"]),
                publisher=str(value["publisher"]),
                artifact_sha256=str(value["artifact_sha256"]).lower(),
                signature=str(value["signature"]) if value.get("signature") else None,
            )
        except (KeyError, TypeError) as exc:
            raise ManifestError("provenance requires source_url, publisher, and artifact_sha256") from exc


@dataclass(frozen=True)
class ToolManifest:
    schema_version: int
    tool_id: str
    version: str
    entrypoint: str
    files: Mapping[str, str]
    permissions: tuple[str, ...]
    provenance: Provenance
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ToolManifest":
        if not isinstance(value, Mapping):
            raise ManifestError("manifest must be an object")
        allowed = {
            "schema_version", "tool_id", "version", "entrypoint", "files",
            "permissions", "provenance", "metadata",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ManifestError(f"unknown manifest fields: {', '.join(unknown)}")
        try:
            raw_files = value["files"]
            raw_permissions = value.get("permissions", [])
            manifest = cls(
                schema_version=int(value["schema_version"]),
                tool_id=str(value["tool_id"]),
                version=str(value["version"]),
                entrypoint=str(value["entrypoint"]),
                files={str(k): str(v).lower() for k, v in raw_files.items()},
                permissions=tuple(str(x) for x in raw_permissions),
                provenance=Provenance.from_dict(value["provenance"]),
                metadata=dict(value.get("metadata", {})),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ManifestError("manifest fields have invalid types") from exc
        manifest.validate()
        return manifest

    @classmethod
    def from_json(cls, payload: bytes | str) -> "ToolManifest":
        try:
            value = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ManifestError("manifest is not valid JSON") from exc
        return cls.from_dict(value)

    def validate(self) -> None:
        if self.schema_version != 1:
            raise ManifestError("unsupported schema_version")
        if not _TOOL_ID.fullmatch(self.tool_id):
            raise ManifestError("invalid tool_id")
        if not _VERSION.fullmatch(self.version):
            raise ManifestError("version must be semantic versioning")
        if not self.provenance.publisher.strip() or len(self.provenance.publisher) > 200:
            raise ManifestError("invalid publisher")
        parsed = urlparse(self.provenance.source_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ManifestError("source_url must be credential-free HTTPS")
        if not _SHA256.fullmatch(self.provenance.artifact_sha256):
            raise ManifestError("artifact_sha256 must be a lowercase SHA-256 digest")
        if not self.files or len(self.files) > 10_000:
            raise ManifestError("files must contain 1..10000 entries")
        normalized: set[str] = set()
        for raw_path, digest in self.files.items():
            path = _safe_relative_path(raw_path)
            if path in normalized:
                raise ManifestError(f"duplicate normalized file path: {path}")
            normalized.add(path)
            if not _SHA256.fullmatch(digest):
                raise ManifestError(f"invalid SHA-256 for {raw_path}")
        if _safe_relative_path(self.entrypoint) not in normalized:
            raise ManifestError("entrypoint is not listed in files")
        if len(set(self.permissions)) != len(self.permissions):
            raise ManifestError("permissions contain duplicates")
        for permission in self.permissions:
            if not _PERMISSION.fullmatch(permission):
                raise ManifestError(f"invalid permission: {permission}")

    def canonical_payload(self) -> bytes:
        value = {
            "schema_version": self.schema_version,
            "tool_id": self.tool_id,
            "version": self.version,
            "entrypoint": self.entrypoint,
            "files": dict(sorted(self.files.items())),
            "permissions": sorted(self.permissions),
            "provenance": {
                "source_url": self.provenance.source_url,
                "publisher": self.provenance.publisher,
                "artifact_sha256": self.provenance.artifact_sha256,
            },
            "metadata": self.metadata,
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_payload()).hexdigest()


@dataclass(frozen=True)
class ScanFinding:
    code: str
    severity: str
    path: str
    message: str


@dataclass(frozen=True)
class ScanReport:
    artifact_sha256: str
    findings: tuple[ScanFinding, ...]
    scanned_files: int
    scanned_bytes: int

    @property
    def passed(self) -> bool:
        return not any(item.severity in {"high", "critical"} for item in self.findings)


@dataclass(frozen=True)
class ReviewRecord:
    reviewer: str
    decision: ReviewDecision
    artifact_sha256: str
    manifest_digest: str
    findings_acknowledged: tuple[str, ...] = ()
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class InstallReceipt:
    operation_id: str
    tool_id: str
    version: str
    artifact_sha256: str
    manifest_digest: str
    installed_path: str
    backup_id: str | None
    installed_at: datetime


def _safe_relative_path(raw: str) -> str:
    if not raw or "\\" in raw or "\x00" in raw:
        raise ManifestError(f"unsafe path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ManifestError(f"unsafe path: {raw!r}")
    return str(path)
